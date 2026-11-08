"""``WeaveCtx`` (design §6.2) and the builder behind it.

One ``WovenClassBuilder`` exists per (target, profile). Each contributor (the binding's
``prepare``/``finalize`` and each matching weaver) gets its own ``WeaveCtx`` on that
builder; everything it adds is stamped with its ``Origin``.
"""
import contextlib
import hashlib
import re
from typing import Any, Dict, List, Optional, Tuple

from ..diag import Diag, Severity, SrcLoc, SvWeaveError
from ..frontend.model import SvClass, SvMethod, SvField, Visibility
from .model import (ClassItem, FieldDecl, MethodSig, MethodSlot, Origin, SvFragment,
                    WovenClass, call_site)
from .svhelpers import SvHelpers


def spec_hash(qname: str) -> str:
    """Short stable hash naming a specialisation (design §4.3)."""
    return hashlib.sha1(qname.encode()).hexdigest()[:5]


def _ident(text: str) -> str:
    return re.sub(r"[^A-Za-z0-9_]", "_", text)


def woven_name(cls: SvClass, profile: str) -> str:
    """``Woven_<C>[_<hash>]__<profile>`` (design D6)."""
    base = cls.name
    if cls.is_specialization:
        base = "%s_%s" % (cls.generic.name, spec_hash(cls.qname))
    return "Woven_%s__%s" % (base, _ident(profile))


def ctor_sig(cls: SvClass) -> Optional[MethodSig]:
    """A constructor that forwards to the nearest user constructor, if that one takes
    arguments (otherwise the implicit ``new()`` is enough)."""
    for c in [cls] + cls.ancestors():
        for m in c.methods:
            if m.is_constructor:
                if not m.args:
                    return None
                return MethodSig("new", args=tuple(a.declare() for a in m.args),
                                 arg_names=tuple(a.name for a in m.args))
    return None


def method_sig(m: SvMethod) -> MethodSig:
    for a in m.args:
        if not a.type.nameable:
            raise SvWeaveError([Diag(Severity.ERROR,
                                     "cannot override %s::%s: argument '%s' has a type that "
                                     "cannot be named outside its declaration (%s)"
                                     % (m.owner.qname, m.name, a.name, a.type.text), m.loc)])
    ret = None
    if m.ret is not None and m.ret.spelling != "void":
        if not m.ret.nameable:
            raise SvWeaveError([Diag(Severity.ERROR, "cannot override %s::%s: its return type "
                                     "cannot be named (%s)" % (m.owner.qname, m.name, m.ret.text),
                                     m.loc)])
        ret = str(m.ret)
    return MethodSig(m.name, task=m.kind.value == "task", ret=ret,
                     args=tuple(a.declare() for a in m.args),
                     arg_names=tuple(a.name for a in m.args))


class WovenClassBuilder:
    def __init__(self, target, profile: str, binding, cfg, model, diags: List[Diag]):
        self.target = target
        self.profile = profile
        self.binding = binding
        self.cfg = cfg
        self.model = model
        self.diags = diags
        cls = target.cls
        self.woven = WovenClass(woven_name(cls, profile), target, profile,
                                extends=cls.type_expr, ctor=ctor_sig(cls))
        self._current: Optional[Tuple[str, Optional[str]]] = None
        # Default before/after relationships per contributor (weaver class, config).
        self.relations: Dict[Tuple[str, Optional[str]], Tuple[tuple, tuple]] = {}
        self.used_names = set()
        self.member_names = set()
        for c in [cls] + cls.ancestors():
            self.member_names.update(f.name for f in c.fields)
            self.member_names.update(m.name for m in c.methods)

    @contextlib.contextmanager
    def contributor(self, name: str, ext_set: Optional[str], before=(), after=()):
        prev = self._current
        self._current = (name, ext_set)
        if before or after:
            self.relations[(name, ext_set)] = (tuple(before), tuple(after))
        try:
            yield
        finally:
            self._current = prev

    def origin_now(self) -> Optional[Origin]:
        if self._current is None:
            return None
        file, line = call_site()
        o = Origin(self._current[0], self._current[1], file, line)
        if o.key not in self.woven.contributors:
            self.woven.contributors.append(o.key)
        return o

    def new_slot(self, sig: MethodSig, kind: str, **kw) -> MethodSlot:
        if sig.name in self.woven.slots:
            return self.woven.slots[sig.name]
        slot = MethodSlot(sig, kind, **kw)
        slot._ctx_origin = self.origin_now
        slot._ctx_relations = lambda key: self.relations.get(key, ((), ()))
        if sig.ret is not None:
            slot.ret_var = self.fresh("ret")
        else:
            slot.ret_var = None
        self.woven.slots[sig.name] = slot
        return slot

    def fresh(self, name: str) -> str:
        base = "__w_" + name
        cand, i = base, 0
        while cand in self.member_names or cand in self.used_names:
            i += 1
            cand = "%s_%d" % (base, i)
        self.used_names.add(cand)
        return cand


class WeaveCtx:
    """What a weaver's handler receives (design §6.2)."""

    def __init__(self, builder: WovenClassBuilder, ext_set: Optional[str] = None,
                 options: Optional[Dict[str, Any]] = None):
        self._b = builder
        self.ext_set = ext_set
        self.options: Dict[str, Any] = dict(options or {})
        self.sv = SvHelpers(self)

    # -- context ---------------------------------------------------------------------
    @property
    def cls(self) -> SvClass:
        return self._b.target.cls

    @property
    def target(self):
        return self._b.target

    @property
    def binding(self):
        return self._b.binding

    @property
    def binding_root(self):
        return self._b.target.root

    @property
    def profile(self) -> str:
        return self._b.profile

    @property
    def model(self):
        return self._b.model

    @property
    def woven(self) -> WovenClass:
        return self._b.woven

    @property
    def config(self):
        return self._b.cfg

    @property
    def field_boundary(self):
        """The nearest ancestor that belongs to the library rather than the user: in a
        package that is not selected for weaving, or the binding root. Its fields, and
        those above it, are the library's own."""
        from ..select import package_selected
        root = self.binding_root
        for a in self.cls.ancestors():
            if a is root or not package_selected(a.package, self.config):
                return a
        return root

    def fields(self):
        """The fields a field weaver handles: those of the target and its ancestors in
        user packages, root-most first (design §6.4)."""
        return self.cls.all_fields(upto=self.field_boundary)

    # -- contribution points ---------------------------------------------------------
    def feature(self, name: str) -> MethodSlot:
        feats = self.binding.features()
        if name not in feats:
            raise self._error("binding '%s' has no feature '%s' (it has: %s)"
                              % (self.binding.name, name, ", ".join(sorted(feats)) or "none"))
        spec = feats[name]
        if spec.method in self.woven.slots:
            return self.woven.slots[spec.method]
        base = self.cls.find_method(spec.method)
        sig = MethodSig(spec.method, task=spec.task, ret=spec.ret, args=tuple(spec.args),
                        arg_names=tuple(spec.arg_names))
        call_super = spec.super_policy == "call" and base is not None and not base.pure
        return self._b.new_slot(sig, MethodSlot.KIND_FEATURE, call_super=call_super,
                                overrides=base, feature=name, rhs=spec.rhs)

    def override(self, method: str) -> MethodSlot:
        if method in self.woven.slots:
            return self.woven.slots[method]
        m = self.cls.find_method(method)
        if m is None:
            raise self._error("%s has no method '%s' to override" % (self.cls.qname, method))
        if m.is_constructor:
            raise self._error("constructors cannot be woven with override(); "
                              "the binding forwards new() itself")
        sig = method_sig(m)
        return self._b.new_slot(sig, MethodSlot.KIND_OVERRIDE, call_super=not m.pure,
                                overrides=m)

    def add_method(self, name: str, ret: Optional[str] = None, args=(), arg_names=None,
                   task: bool = False, virtual: bool = True, static: bool = False) -> MethodSlot:
        """A new method in the woven class (no ``super`` call)."""
        if name in self.woven.slots:
            raise self._error("method '%s' is already defined in %s" % (name, self.woven.name))
        if self.cls.find_method(name) is not None:
            raise self._error("%s already has a method '%s'; use override()"
                              % (self.cls.qname, name))
        if arg_names is None:
            arg_names = tuple(_arg_name(a) for a in args)
        sig = MethodSig(name, task=task, ret=ret, args=tuple(args), arg_names=tuple(arg_names),
                        static=static)
        slot = self._b.new_slot(sig, MethodSlot.KIND_NEW, call_super=False)
        slot.virtual = virtual and not static
        return slot

    def add_field(self, decl: str) -> None:
        """A non-rand class property, e.g. ``"bit __w_seen[string];"``."""
        text = decl.strip()
        if re.match(r"^(rand|randc)\b", text):
            raise self._error("add_field cannot add rand/randc fields: %s" % text)
        if not text.endswith(";"):
            text += ";"
        self.woven.fields.append(FieldDecl(text, self._b.origin_now()))

    def add_item(self, text: str) -> None:
        """Any class item no slot covers (a typedef, a constraint, a helper function)."""
        self.woven.items.append(ClassItem(SvFragment(text, self._b.origin_now())))

    def add_registration(self, reg: Any) -> None:
        self.woven.registrations.append(reg)

    # -- diagnostics -----------------------------------------------------------------
    def diag(self, msg: str, severity: Severity = Severity.WARNING, loc: Optional[SrcLoc] = None):
        o = self._b.origin_now()
        prefix = "%s: " % o.contributor if o else ""
        if loc is None and o is not None and o.file:
            loc = SrcLoc(o.file, o.line)
        self._b.diags.append(Diag(severity, prefix + msg, loc))

    def warning(self, msg: str, loc: Optional[SrcLoc] = None):
        sev = Severity.ERROR if self._b.cfg.strict else Severity.WARNING
        self.diag(msg, sev, loc)

    def error(self, msg: str, loc: Optional[SrcLoc] = None):
        self.diag(msg, Severity.ERROR, loc)

    def _error(self, msg: str) -> SvWeaveError:
        o = self._b.origin_now()
        loc = SrcLoc(o.file, o.line) if o and o.file else None
        prefix = "%s on %s: " % (o.contributor, self.cls.qname) if o else ""
        return SvWeaveError([Diag(Severity.ERROR, prefix + msg, loc)])


def _arg_name(decl: str) -> str:
    m = re.search(r"([A-Za-z_][A-Za-z0-9_$]*)\s*(\[[^\]]*\]\s*)*(=.*)?$", decl.strip())
    if m is None:
        raise ValueError("cannot find the argument name in '%s'" % decl)
    return m.group(1)
