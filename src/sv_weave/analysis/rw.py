"""Read/write sets of a class method, as member paths (plan-sync-rtl E5).

``analyze(sub)`` walks the bound body of a pyslang ``SubroutineSymbol`` and returns
the member paths it reads and writes, relative to ``this``:

- a path is a field name followed by ``.member`` and ``[<const>]`` steps
  (``in.valid``, ``q.skid_valid``, ``arr[2].a``). A path covers everything below it;
- a static property is named by its lexical path (``p::C::count``);
- a whole-struct read or write expands to every field, recursively
  (``out.data`` of a struct type gives ``out.data.a``, ``out.data.b``);
- a variable index covers the whole array (``arr[i]`` gives ``arr``);
- a field written on any path counts as written; both branches of every ``if``
  are walked, so a constant-parameter ``if`` gives a superset;
- calls to methods of the same class and to static functions are followed
  transitively, with cycle detection. A call through a member handle
  (``in.get_valid()``) is followed with the handle's path as prefix; the static
  target is used, virtual dispatch is not resolved;
- a call that cannot be followed (a pure virtual or interface-class method, a
  method of a handle that is not a member path, such as ``port.t.x()``) is
  reported in ``opaque`` as ``<receiver path>.<method>``.

Locals and arguments are not members and are not reported. The pyslang AST lives only
as long as its compilation: keep the model alive while analysing.
"""
import dataclasses as dc
from typing import Callable, Dict, FrozenSet, List, Optional, Set, Tuple

from pyslang import ast as A

EK = A.ExpressionKind
SK = A.SymbolKind
_INCDEC = {A.UnaryOperator.Preincrement, A.UnaryOperator.Predecrement,
           A.UnaryOperator.Postincrement, A.UnaryOperator.Postdecrement}


@dc.dataclass(frozen=True)
class RwSets:
    reads: FrozenSet[str]
    writes: FrozenSet[str]
    opaque: FrozenSet[str]

    def prefixed(self, prefix: str) -> "RwSets":
        return RwSets(*(frozenset(_join(prefix, p) for p in s)
                        for s in (self.reads, self.writes, self.opaque)))


_EMPTY = RwSets(frozenset(), frozenset(), frozenset())


def _join(prefix: str, path: str) -> str:
    if not prefix or "::" in path:
        return path
    return prefix + "." + path


def analyze(sub, summary: Optional[Callable[[object], Optional[RwSets]]] = None) -> RwSets:
    """Read/write sets of the pyslang ``SubroutineSymbol`` ``sub``.

    ``summary(callee)``, when given, is asked before a callee is followed; a
    returned ``RwSets`` stands for the callee's body (prefixed with the receiver
    path like a followed call), and ``None`` follows it as usual. A weaver uses it
    to stop at a library boundary whose effects it knows by other means."""
    return _Walker({}, {}, summary).sub(sub)


def analyze_stmts(sub, summary: Optional[Callable[[object], Optional[RwSets]]] = None
                  ) -> Optional[List[RwSets]]:
    """Read/write sets of each top-level statement of ``sub``'s body (sequential
    blocks are flattened), for per-output dependences. None if the body declares
    a local, which can carry a value from one statement to another."""
    if _is_opaque(sub):
        return None
    has_local = []

    def cb(n):
        if isinstance(n, A.VariableDeclStatement):
            has_local.append(n)
        return A.VisitAction.Advance
    sub.body.visit(cb)
    if has_local:
        return None
    stmts = []

    def flat(s):
        if s.kind == A.StatementKind.List:
            for x in s.list:
                flat(x)
        elif s.kind == A.StatementKind.Block and s.blockKind == A.StatementBlockKind.Sequential:
            flat(s.body)
        elif s.kind != A.StatementKind.Empty:
            stmts.append(s)
    flat(sub.body)
    memo: Dict[int, Tuple[object, RwSets]] = {}
    out = []
    for s in stmts:
        w = _Walker(memo, {_key(sub): sub}, summary)
        w.stmt(s)
        out.append(RwSets(frozenset(w.r), frozenset(w.w), frozenset(w.o)))
    return out


class _Walker:
    def __init__(self, memo: Dict[int, Tuple[object, RwSets]], active: Dict[int, object],
                 summary=None):
        self.memo = memo           # finished callees, keyed by symbol address
        self.active = active       # callees on the call stack (cycle detection)
        self.summary = summary
        self.r: Set[str] = set()
        self.w: Set[str] = set()
        self.o: Set[str] = set()

    # -- subroutines --------------------------------------------------------
    def sub(self, sub) -> RwSets:
        key = _key(sub)
        if key in self.memo:
            return self.memo[key][1]
        if key in self.active:
            return _EMPTY
        self.active[key] = sub
        w = _Walker(self.memo, self.active, self.summary)
        w.stmt(sub.body)
        del self.active[key]
        res = RwSets(frozenset(w.r), frozenset(w.w), frozenset(w.o))
        self.memo[key] = (sub, res)
        return res

    def stmt(self, s):
        def cb(n):
            if isinstance(n, A.Expression):
                self.read(n)
                return A.VisitAction.Skip
            if isinstance(n, A.VariableDeclStatement):
                init = n.symbol.initializer
                if init is not None:
                    self.read(init)
            return A.VisitAction.Advance
        s.visit(cb)

    # -- paths --------------------------------------------------------------
    def path(self, e) -> Optional[str]:
        """The member path ``e`` names, or None. Reads its variable indices."""
        k = e.kind
        if k == EK.NamedValue:
            sym = e.symbol
            if sym.kind == SK.Variable and sym.name == "this":
                return ""
            if sym.kind != SK.ClassProperty:
                return None
            if sym.lifetime == A.VariableLifetime.Static:
                return sym.lexicalPath
            return sym.name
        if k == EK.MemberAccess:
            m = e.member
            if m.kind == SK.ClassProperty and m.lifetime == A.VariableLifetime.Static:
                return m.lexicalPath
            base = self.path(e.value)
            if base is None:
                return None
            return _join(base, m.name)
        if k == EK.ElementSelect:
            base = self.path(e.value)
            if base is None:
                return None
            c = e.selector.constant
            if c is not None and base:
                return "%s[%s]" % (base, c)
            self.read(e.selector)
            return base
        if k == EK.RangeSelect:
            base = self.path(e.value)
            if base is None:
                return None
            self.read(e.left)
            self.read(e.right)
            return base
        return None

    def _leaves(self, path: str, typ) -> Set[str]:
        out: Set[str] = set()
        _expand(path, typ, out, 0)
        return out

    # -- reads and writes ---------------------------------------------------
    def read(self, e):
        p = self.path(e)
        if p is not None:
            if p:
                self.r |= self._leaves(p, e.type)
            return
        k = e.kind
        if k == EK.Assignment:
            self.write(e.left)
            if e.isCompound:
                self.read(e.left)
            self.read(e.right)
        elif k == EK.UnaryOp and e.op in _INCDEC:
            self.read(e.operand)
            self.write(e.operand)
        elif k == EK.Call:
            self.call(e)
        else:
            self.children(e)

    def write(self, e):
        p = self.path(e)
        if p is not None:
            if p:
                self.w |= self._leaves(p, e.type)
            return
        if e.kind in (EK.Concatenation, EK.SimpleAssignmentPattern):
            for op in e.operands if e.kind == EK.Concatenation else e.elements:
                self.write(op)
        else:
            self.children(e)

    def children(self, e):
        root = [True]

        def cb(n):
            if root[0]:
                root[0] = False
                return A.VisitAction.Advance
            if isinstance(n, A.Expression):
                self.read(n)
                return A.VisitAction.Skip
            return A.VisitAction.Advance
        e.visit(cb)

    def call(self, e):
        callee = e.subroutine
        if e.isSystemCall:
            for a in e.arguments:
                self.read(a)
            return
        formals = list(callee.arguments)
        for i, a in enumerate(e.arguments):
            d = formals[i].direction if i < len(formals) else A.ArgumentDirection.In
            self.read(a)
            if d == A.ArgumentDirection.Ref:
                self.write(a)
        recv = e.thisClass
        prefix = ""
        if recv is not None:
            prefix = self.path(recv)     # reading the handle itself is not reported
            if prefix is None:
                self.read(recv)
                rs = str(recv.syntax).strip() if recv.syntax is not None else "?"
                self.o.add("%s.%s" % (rs, callee.name))
                return
        res = self.summary(callee) if self.summary is not None else None
        if res is None:
            if _is_opaque(callee):
                self.o.add(_join(prefix, callee.name))
                return
            res = self.sub(callee)
        if prefix:
            res = res.prefixed(prefix)
        self.r |= res.reads
        self.w |= res.writes
        self.o |= res.opaque


def _key(sym) -> int:
    # pybind11 hands back one wrapper per C++ symbol while it is alive; the memo
    # and the active set keep the wrappers alive, so id() is stable.
    return id(sym)


def _is_opaque(sub) -> bool:
    return A.MethodFlags.Pure in sub.flags or sub.body is None


def _expand(path: str, typ, out: Set[str], depth: int):
    t = typ.canonicalType
    if depth < 16 and t.isStruct:
        fields = [m for m in t if m.kind == SK.Field]
        if fields:
            for f in fields:
                _expand(path + "." + f.name, f.type, out, depth + 1)
            return
    out.add(path)
