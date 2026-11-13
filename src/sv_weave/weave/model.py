"""The woven model (design §7.1): structure in dataclasses, bodies as SV text.

``SvFragment`` records where each piece of text came from (``Origin``): the
contributing weaver or binding, its extension set and the Python call site. The
renderer keeps a line map from woven lines back to these origins.
"""
import dataclasses as dc
import os
import sys
import textwrap
from typing import Any, Dict, List, Optional, Sequence, Tuple

from ..diag import SrcLoc, SvWeaveError, Diag, Severity

_FRAMEWORK_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


@dc.dataclass(frozen=True)
class Origin:
    contributor: str                  # weaver or binding name
    ext_set: Optional[str]            # None for bindings and the framework
    file: str = ""
    line: int = 0
    py_file: str = ""                 # text from a template: the Python call of render()
    py_line: int = 0

    def __str__(self):
        where = " at %s:%d" % (self.file, self.line) if self.file else ""
        if self.py_file:
            where += " (rendered at %s:%d)" % (self.py_file, self.py_line)
        what = self.contributor + ("[%s]" % self.ext_set if self.ext_set else "")
        return what + where

    def for_text(self, text) -> "Origin":
        """This origin, moved to the template ``text`` was rendered from (if any)."""
        tpl = getattr(text, "template", "")
        if not tpl:
            return self
        return dc.replace(self, file=tpl, line=1, py_file=text.py_file, py_line=text.py_line)

    @property
    def key(self) -> Tuple[str, Optional[str]]:
        return (self.contributor, self.ext_set)


def call_site() -> Tuple[str, int]:
    """File and line of the nearest caller outside the sv_weave framework.

    Built-in weavers and bindings live inside the package; their own frames count."""
    f = sys._getframe(1)
    while f is not None:
        fn = os.path.abspath(f.f_code.co_filename)
        inside = fn.startswith(_FRAMEWORK_DIR + os.sep)
        plugin = inside and (os.sep + "weavers" + os.sep in fn or os.sep + "bindings" + os.sep in fn)
        if not inside or plugin:
            return fn, f.f_lineno
        f = f.f_back
    return "", 0


@dc.dataclass
class SvFragment:
    text: str
    origin: Optional[Origin]

    def lines(self) -> List[str]:
        text = textwrap.dedent(self.text).strip("\n")
        return text.split("\n") if text else []


@dc.dataclass
class _Entry:
    frag: SvFragment
    key: Tuple[str, Optional[str]]       # (contributor, ext_set)
    first: bool
    before: Tuple[str, ...]
    after: Tuple[str, ...]


class OrderError(Exception):
    pass


class Contributions:
    """One section of a method (decl, pre or post): fragments from many contributors.

    Placement (design §6.3):
    - **band:** fragments added with ``first=True`` (or ``prepend``) come ahead of
      appended ones;
    - **default order** within a band: contributor (dispatch) order; reversed in the
      ``post`` section, so that one contributor's pre/post wrap another's;
    - **relationships:** ``before=[names]`` / ``after=[names]`` put a contributor's
      fragments textually before/after those of the named contributors (weavers or
      bindings), in this section. A contributor's own defaults (weaver class
      attributes, config) apply to every fragment it adds.
    Fragments of one contributor in one band stay in the order they were added.
    """

    def __init__(self, owner: "MethodSlot", part: str, reverse: bool = False):
        self._owner = owner
        self._part = part
        self._reverse = reverse
        self._entries: List[_Entry] = []

    def add(self, text: str, first: bool = False, before: Sequence[str] = (),
            after: Sequence[str] = ()) -> "Contributions":
        origin = self._owner._origin()
        key = origin.key if origin else ("", None)
        d_before, d_after = self._owner._relations(key)
        if origin is not None:
            origin = origin.for_text(text)
        self._entries.append(_Entry(SvFragment(text, origin), key, bool(first),
                                    tuple(d_before) + tuple(before),
                                    tuple(d_after) + tuple(after)))
        return self

    append = add

    def prepend(self, text: str, before: Sequence[str] = (),
                after: Sequence[str] = ()) -> "Contributions":
        return self.add(text, first=True, before=before, after=after)

    def __iadd__(self, text: str):
        return self.add(text)

    @property
    def groups(self) -> List[Tuple[Tuple[str, Optional[str]], List[SvFragment]]]:
        """Fragments grouped by contributor, in first-contribution order."""
        out: List = []
        for e in self._entries:
            for k, frags in out:
                if k == e.key:
                    frags.append(e.frag)
                    break
            else:
                out.append((e.key, [e.frag]))
        return out

    def ordered(self) -> List[SvFragment]:
        """The fragments in final order. Raises OrderError on contradictory
        relationships."""
        if not self._entries:
            return []
        contributors: List[Tuple[str, Optional[str]]] = []
        for e in self._entries:
            if e.key not in contributors:
                contributors.append(e.key)
        if self._reverse:
            contributors.reverse()
        # Nodes: (band, contributor), default-ordered.
        nodes: List[Tuple[int, Tuple]] = []
        for band in (0, 1):
            for k in contributors:
                if any(e.key == k and (0 if e.first else 1) == band for e in self._entries):
                    nodes.append((band, k))
        rank = {n: i for i, n in enumerate(nodes)}
        edges = {n: set() for n in nodes}       # n -> nodes that must come after n
        for e in self._entries:
            n = (0 if e.first else 1, e.key)
            for other in nodes:
                if other[1] == e.key:
                    continue
                if other[1][0] in e.before:
                    edges[n].add(other)
                if other[1][0] in e.after:
                    edges[other].add(n)
        # Band order is a default, not a constraint; relationships may cross it.
        indeg = {n: 0 for n in nodes}
        for n in nodes:
            for m in edges[n]:
                indeg[m] += 1
        ready = sorted([n for n in nodes if indeg[n] == 0], key=rank.get)
        order: List = []
        while ready:
            n = ready.pop(0)
            order.append(n)
            for m in edges[n]:
                indeg[m] -= 1
                if indeg[m] == 0:
                    ready.append(m)
            ready.sort(key=rank.get)
        if len(order) != len(nodes):
            stuck = sorted({n[1][0] for n in nodes if n not in order})
            raise OrderError("contradictory before/after relationships in %s.%s between %s"
                             % (self._owner.name, self._part, ", ".join(stuck)))
        out: List[SvFragment] = []
        for band, k in order:
            out.extend(e.frag for e in self._entries
                       if e.key == k and (0 if e.first else 1) == band)
        return out

    def __bool__(self):
        return bool(self._entries)


@dc.dataclass
class MethodSig:
    """A method signature as SV text pieces."""
    name: str
    task: bool = False
    ret: Optional[str] = None         # None: void (or task)
    args: Tuple[str, ...] = ()        # full declarations, e.g. "input int x = 3"
    arg_names: Tuple[str, ...] = ()
    static: bool = False

    def header(self, virtual: bool = True) -> str:
        quals = ("static " if self.static else "") + ("virtual " if virtual and not self.static else "")
        if self.task:
            return "%stask %s(%s);" % (quals, self.name, ", ".join(self.args))
        return "%sfunction %s %s(%s);" % (quals, self.ret or "void", self.name, ", ".join(self.args))


class MethodSlot:
    """One method of a woven class, composed from contributions (design §6.3)::

        <header>
          <decl>    all contributors, in order
          <pre>     contributor order
          super.<name>(<args>);   unless replaced, or the base method is pure
          <post>    reverse contributor order
          return <result>;        functions with a return value only
        <end> : <name>
    """
    KIND_FEATURE = "feature"
    KIND_OVERRIDE = "override"
    KIND_NEW = "new"

    def __init__(self, sig: MethodSig, kind: str, call_super: bool = True,
                 overrides=None, feature: Optional[str] = None, rhs: Optional[str] = None):
        self.sig = sig
        self.kind = kind
        self.feature = feature
        self.rhs = rhs                     # name of the argument weavers read from, if any
        self.overrides = overrides         # the SvMethod being overridden, if any
        self.call_super = call_super
        self.decl = Contributions(self, "decl")
        self.pre = Contributions(self, "pre")
        self.post = Contributions(self, "post", reverse=True)
        self.replace_super_by: Optional[Origin] = None
        self.result: Optional[str] = None  # expression returned, when not super's result
        self.result_by: Optional[Origin] = None
        self._ctx_origin = None            # set by the builder: returns the current Origin
        self._ctx_relations = None         # set by the builder: key -> (before, after)
        self.virtual = True
        self.ret_var: Optional[str] = None # local holding super's result (functions only)
        self.first_origin: Optional[Origin] = None

    @property
    def name(self) -> str:
        return self.sig.name

    @property
    def body(self) -> Contributions:
        """Alias for ``post``: the usual place for feature code."""
        return self.post

    def _relations(self, key) -> Tuple[Tuple[str, ...], Tuple[str, ...]]:
        return self._ctx_relations(key) if self._ctx_relations else ((), ())

    def _origin(self) -> Optional[Origin]:
        o = self._ctx_origin() if self._ctx_origin else None
        if o is not None and self.first_origin is None:
            self.first_origin = o
        return o

    def replace_super(self) -> None:
        """Do not call ``super``. Only one contributor may do this."""
        o = self._origin()
        if self.replace_super_by is not None and self.replace_super_by.key != (o.key if o else None):
            raise SvWeaveError([Diag(
                Severity.ERROR,
                "%s: replace_super already set by %s; also requested by %s"
                % (self.name, self.replace_super_by, o),
                SrcLoc(o.file, o.line) if o and o.file else None)])
        self.replace_super_by = o

    def set_result(self, expr: str) -> None:
        """The value the function returns, instead of super's result."""
        o = self._origin()
        if self.result_by is not None and self.result_by.key != (o.key if o else None):
            raise SvWeaveError([Diag(
                Severity.ERROR, "%s: result already set by %s; also set by %s"
                % (self.name, self.result_by, o),
                SrcLoc(o.file, o.line) if o and o.file else None)])
        self.result = expr
        self.result_by = o

    @property
    def has_super_call(self) -> bool:
        return self.call_super and self.replace_super_by is None

    def contributors(self) -> List[Tuple[str, Optional[str]]]:
        seen = []
        for part in (self.decl, self.pre, self.post):
            for k, frags in part.groups:
                if frags and k not in seen:
                    seen.append(k)
        return seen


@dc.dataclass
class FieldDecl:
    text: str                          # full declaration, e.g. "bit __w_read[string];"
    origin: Optional[Origin]


@dc.dataclass
class ClassItem:
    frag: SvFragment


@dc.dataclass(eq=False)
class WovenClass:
    name: str
    target: Any                        # select.Target
    profile: str
    extends: str                       # the user class's SV spelling
    ctor: Optional[MethodSig] = None   # explicit constructor forwarding to super.new
    slots: Dict[str, MethodSlot] = dc.field(default_factory=dict)
    fields: List[FieldDecl] = dc.field(default_factory=list)
    items: List[ClassItem] = dc.field(default_factory=list)
    registrations: List[Any] = dc.field(default_factory=list)
    contributors: List[Tuple[str, Optional[str]]] = dc.field(default_factory=list)
    concrete: bool = True
    unimplemented: List[str] = dc.field(default_factory=list)
    # Other profiles whose woven class came out identical: this class is registered
    # for them too (design §9, deduplication).
    also_profiles: List[str] = dc.field(default_factory=list)

    @property
    def profiles(self) -> List[str]:
        return [self.profile] + self.also_profiles

    @property
    def cls(self):
        return self.target.cls

    @property
    def contributed(self) -> bool:
        """True if any weaver (not just the binding) added something."""
        return any(s is not None for _, s in self.contributors)


@dc.dataclass(eq=False)
class WovenPackage:
    name: str
    user_pkg: str
    imports: List[str] = dc.field(default_factory=list)
    classes: List[WovenClass] = dc.field(default_factory=list)
    items: List[SvFragment] = dc.field(default_factory=list)   # package-level items
    preamble: List[str] = dc.field(default_factory=list)       # lines before `package`
