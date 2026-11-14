"""Stage 2, Model: ``SvModel``, a stable façade over the pyslang compilation (design §4.2).

Weavers see only these objects. Each one keeps the pyslang symbol it came from in
``.slang``. That attribute is an escape hatch whose shape may change with pyslang.

The model covers every class declared in a package or in ``$unit``, plus every
specialisation of a parameterised class that the design elaborates (§4.3). Classes
declared inside modules are not modelled: no other package can name them.
"""
import dataclasses as dc
import enum
import fnmatch
from typing import Any, Callable, Dict, Iterator, List, Optional, Union

from pyslang import ast as A

from ..diag import Diag, Severity, SrcLoc, SvWeaveError
from .loader import Loaded, slang_loc
from .types import SvType, TypeConverter, VOID

_UNSET = object()     # cache sentinel where None is a valid result

SK = A.SymbolKind


class Visibility(enum.Enum):
    PUBLIC = "public"
    PROTECTED = "protected"
    LOCAL = "local"


class RandMode(enum.Enum):
    NONE = "none"
    RAND = "rand"
    RANDC = "randc"


class MethodKind(enum.Enum):
    FUNCTION = "function"
    TASK = "task"


class ArgDir(enum.Enum):
    INPUT = "input"
    OUTPUT = "output"
    INOUT = "inout"
    REF = "ref"
    CONST_REF = "const ref"


Attrs = Dict[str, Any]


@dc.dataclass(eq=False)
class SvArg:
    name: str
    dir: ArgDir
    type: SvType
    default: Optional[str] = None     # source text of the default value

    def declare(self) -> str:
        text = "%s %s" % (self.dir.value, self.type.declare(self.name))
        if self.default is not None:
            text += " = %s" % self.default
        return text


@dc.dataclass(eq=False)
class SvField:
    name: str
    type: SvType
    rand: RandMode
    static: bool
    const: bool
    visibility: Visibility
    attrs: Attrs
    owner: "SvClass"
    loc: Optional[SrcLoc]
    slang: Any = dc.field(default=None, repr=False)

    def __repr__(self):
        return "SvField(%s.%s: %s)" % (self.owner.qname, self.name, self.type)


@dc.dataclass(eq=False)
class SvMethod:
    name: str
    kind: MethodKind
    virtual: bool
    pure: bool
    static: bool
    is_constructor: bool
    args: List[SvArg]
    ret: Optional[SvType]             # None for tasks and constructors
    visibility: Visibility
    attrs: Attrs
    owner: "SvClass"
    loc: Optional[SrcLoc]
    slang: Any = dc.field(default=None, repr=False)

    _rw: Any = dc.field(default=None, init=False, repr=False)
    _stmt_rw: Any = dc.field(default=_UNSET, init=False, repr=False)

    def __repr__(self):
        return "SvMethod(%s::%s)" % (self.owner.qname, self.name)

    @property
    def rw(self):
        """Read/write sets of the body as member paths (``analysis.rw.RwSets``);
        computed on first use and cached."""
        if self._rw is None:
            from ..analysis.rw import analyze
            self._rw = analyze(self.slang)
        return self._rw

    @property
    def stmt_rw(self):
        """Read/write sets of each top-level statement of the body
        (``analysis.rw.analyze_stmts``); None if the body declares a local.
        Computed on first use and cached."""
        if self._stmt_rw is _UNSET:
            from ..analysis.rw import analyze_stmts
            self._stmt_rw = analyze_stmts(self.slang)
        return self._stmt_rw

    @property
    def reads(self):
        return self.rw.reads

    @property
    def writes(self):
        return self.rw.writes


@dc.dataclass(eq=False)
class ExternRef:
    """A base class or interface outside the model (for example declared in a module)."""
    qname: str
    slang: Any = dc.field(default=None, repr=False)


@dc.dataclass(eq=False)
class SvGenericClass:
    """A parameterised class declaration. Its specialisations are ``SvClass`` objects."""
    name: str
    package: Optional[str]
    qname: str
    attrs: Attrs
    loc: Optional[SrcLoc]
    specializations: List["SvClass"] = dc.field(default_factory=list)
    slang: Any = dc.field(default=None, repr=False)

    def __repr__(self):
        return "SvGenericClass(%s)" % self.qname

    @property
    def decl(self):
        """The declaration as written (``frontend.decl.SvDecl``)."""
        return _decl_of(self)


@dc.dataclass(eq=False)
class SvClass:
    name: str
    package: Optional[str]
    qname: str                        # "p::A", or "p::G#(16, int)" for a specialisation
    type_expr: Optional[str]          # the SV spelling used to extend or name the class
    is_abstract: bool
    is_interface: bool
    params: Dict[str, str]            # empty unless this is a specialisation
    generic: Optional[SvGenericClass]
    attrs: Attrs
    loc: Optional[SrcLoc]
    base: Union["SvClass", ExternRef, None] = None
    implements: List[Union["SvClass", ExternRef]] = dc.field(default_factory=list)
    fields: List[SvField] = dc.field(default_factory=list)      # declared in this class only
    methods: List[SvMethod] = dc.field(default_factory=list)    # declared in this class only
    slang: Any = dc.field(default=None, repr=False)

    def __repr__(self):
        return "SvClass(%s)" % self.qname

    @property
    def is_specialization(self) -> bool:
        return self.generic is not None

    @property
    def decl(self):
        """The declaration as written (``frontend.decl.SvDecl``); for a
        specialisation, its generic class's declaration."""
        if self.generic is not None:
            return self.generic.decl
        return _decl_of(self)

    def ancestors(self) -> List["SvClass"]:
        """Base classes in the model, nearest first."""
        out, b = [], self.base
        while isinstance(b, SvClass):
            out.append(b)
            b = b.base
        return out

    def all_fields(self, upto: Optional["SvClass"] = None) -> List[SvField]:
        """Fields of this class and its ancestors, root-most first. With ``upto``,
        stop below that class (its fields are not included)."""
        chain = [self] + self.ancestors()
        if upto is not None and upto in chain:
            chain = chain[:chain.index(upto)]
        out = []
        for c in reversed(chain):
            out.extend(c.fields)
        return out

    def find_method(self, name: str) -> Optional[SvMethod]:
        """The nearest declaration of ``name``, walking up the base classes."""
        for c in [self] + self.ancestors():
            for m in c.methods:
                if m.name == name:
                    return m
        return None

    def is_a(self, name: str) -> bool:
        """True if this class is, or derives from, ``name``. ``name`` may be qualified
        (``p::A``) or not (``A``); a generic class name matches all its specialisations."""
        for c in [self] + self.ancestors():
            if _name_matches(c, name):
                return True
        return False

    def all_interfaces(self) -> List[Union["SvClass", ExternRef]]:
        """Interface classes implemented by this class or any ancestor, transitively."""
        out: List = []

        def add(i):
            if i in out:
                return
            out.append(i)
            if isinstance(i, SvClass):
                if isinstance(i.base, SvClass):
                    add(i.base)
                for j in i.implements:
                    add(j)
        for c in [self] + self.ancestors():
            for i in c.implements:
                add(i)
        return out

    def implements_iface(self, name: str) -> bool:
        for i in self.all_interfaces():
            if isinstance(i, SvClass) and _name_matches(i, name):
                return True
            if isinstance(i, ExternRef) and (i.qname == name or i.qname.split("::")[-1] == name):
                return True
        return False

    def unimplemented_pure(self) -> List[SvMethod]:
        """Pure virtual methods with no implementation in this class or above it."""
        seen, out = set(), []
        for c in [self] + self.ancestors():
            for m in c.methods:
                if m.name in seen:
                    continue
                seen.add(m.name)
                if m.pure:
                    out.append(m)
        return out


def _decl_of(obj):
    d = obj.__dict__.get("_decl")
    if d is None and obj.slang is not None:
        from .decl import build_decl
        d = build_decl(obj.slang.syntax)
        obj.__dict__["_decl"] = d
    return d


def _name_matches(c: SvClass, name: str) -> bool:
    if c.qname == name or c.name == name:
        return True
    if c.generic is not None and (c.generic.qname == name or c.generic.name == name):
        return True
    return False


@dc.dataclass(eq=False)
class SvPackage:
    name: str
    loc: Optional[SrcLoc]
    classes: List[SvClass] = dc.field(default_factory=list)
    generics: List[SvGenericClass] = dc.field(default_factory=list)
    imports: List[str] = dc.field(default_factory=list)   # wildcard imports (p::*), in order
    slang: Any = dc.field(default=None, repr=False)

    def __repr__(self):
        return "SvPackage(%s)" % self.name


class SvModel:
    """The class model of one design, plus design-wide queries (§6.7)."""

    def __init__(self, loaded: Loaded):
        self.loaded = loaded
        self._packages: Dict[str, SvPackage] = {}
        self._classes: Dict[str, SvClass] = {}
        self._generics: Dict[str, SvGenericClass] = {}
        self.diags: List[Diag] = []

    # -- design-wide queries -----------------------------------------------------
    def packages(self) -> List[SvPackage]:
        return list(self._packages.values())

    def package(self, name: str) -> Optional[SvPackage]:
        return self._packages.get(name)

    def classes(self, match: Optional[Callable[[SvClass], bool]] = None) -> List[SvClass]:
        """Every modelled class (specialisations included, generic declarations not),
        in a deterministic order, optionally filtered by a predicate (§5.1)."""
        out = [c for c in self._classes.values() if match is None or match(c)]
        return out

    def find_class(self, name: str) -> Optional[SvClass]:
        """By qualified name, or by bare name if that is unique."""
        if name in self._classes:
            return self._classes[name]
        hits = [c for c in self._classes.values() if c.name == name and not c.is_specialization]
        return hits[0] if len(hits) == 1 else None

    def generic(self, name: str) -> Optional[SvGenericClass]:
        if name in self._generics:
            return self._generics[name]
        hits = [g for g in self._generics.values() if g.name == name]
        return hits[0] if len(hits) == 1 else None

    def subclasses_of(self, base: Union[SvClass, str], concrete: bool = True,
                      transitive: bool = True) -> List[SvClass]:
        """Classes derived from ``base`` (not ``base`` itself). ``base`` may name a
        generic class, which matches all its specialisations."""
        def is_sub(c: SvClass) -> bool:
            if isinstance(base, SvClass):
                anc = c.ancestors() if transitive else ([c.base] if isinstance(c.base, SvClass) else [])
                return base in anc
            anc = c.ancestors() if transitive else ([c.base] if isinstance(c.base, SvClass) else [])
            return any(_name_matches(a, base) for a in anc)
        return [c for c in self._classes.values()
                if not c.is_interface and is_sub(c) and not (concrete and c.is_abstract)]

    def implementors_of(self, iface: Union[SvClass, str], concrete: bool = True) -> List[SvClass]:
        name = iface.qname if isinstance(iface, SvClass) else iface
        return [c for c in self._classes.values()
                if not c.is_interface and c.implements_iface(name)
                and not (concrete and c.is_abstract)]

    def _add_class(self, cls: SvClass):
        self._classes[cls.qname] = cls


class ModelBuilder:
    def __init__(self, loaded: Loaded):
        self.loaded = loaded
        self.comp = loaded.compilation
        self.sm = loaded.source_manager
        self.model = SvModel(loaded)
        pkgs = frozenset(p.name for p in self.comp.getPackages())
        self.types = TypeConverter(pkgs)
        self._building: Dict[str, SvClass] = {}
        self._keep: List[Any] = []        # keeps pyslang wrappers alive (see specialize.py)

    def loc(self, sym) -> Optional[SrcLoc]:
        return slang_loc(self.sm, sym.location)

    def error(self, msg: str, sym=None):
        self.model.diags.append(Diag(Severity.ERROR, msg, self.loc(sym) if sym is not None else None))

    # -- attributes --------------------------------------------------------------
    def attrs_of(self, sym) -> Attrs:
        out: Attrs = {}
        try:
            for at in self.comp.getAttributes(sym):
                out[at.name] = _attr_value(at.syntax)
        except Exception:
            pass
        if not out:
            syn = sym.syntax
            for al in getattr(syn, "attributes", None) or []:
                for spec in al.specs:
                    if hasattr(spec, "name") and not isinstance(spec.name, str):
                        out[spec.name.valueText] = _attr_value(spec)
        return out

    # -- classes ------------------------------------------------------------------
    def build(self) -> SvModel:
        from .specialize import find_specializations

        pkgs = [p for p in self.comp.getPackages() if p.name != "std"]
        pkgs.sort(key=lambda p: (p.location.buffer.id, p.location.offset))
        for pkg in pkgs:
            sp = SvPackage(pkg.name, self.loc(pkg), slang=pkg)
            self.model._packages[pkg.name] = sp
            self._keep.append(pkg)
            for m in pkg:
                if m.kind == SK.WildcardImport:
                    if m.packageName not in sp.imports:
                        sp.imports.append(m.packageName)
                elif isinstance(m, A.ClassType):
                    sp.classes.append(self.class_for(m))
                elif m.kind == SK.GenericClassDef:
                    sp.generics.append(self.generic_for(m))

        for unit in self.comp.getCompilationUnits():
            self._keep.append(unit)
            for m in unit:
                if isinstance(m, A.ClassType):
                    self.class_for(m)
                elif m.kind == SK.GenericClassDef:
                    self.generic_for(m)

        for spec in find_specializations(self.loaded):
            self.class_for(spec)

        # Deterministic order: by package (declaration order), then qualified name.
        pkg_order = {name: i for i, name in enumerate(self.model._packages)}
        ordered = sorted(self.model._classes.values(),
                         key=lambda c: (pkg_order.get(c.package, len(pkg_order)), c.qname))
        self.model._classes = {c.qname: c for c in ordered}
        for g in self.model._generics.values():
            g.specializations.sort(key=lambda c: c.qname)

        errs = [d for d in self.model.diags if d.severity == Severity.ERROR]
        if errs:
            raise SvWeaveError(errs, "the class model could not be built")
        return self.model

    def generic_for(self, gsym) -> SvGenericClass:
        qname = gsym.lexicalPath or gsym.name
        g = self.model._generics.get(qname)
        if g is None:
            self._keep.append(gsym)
            g = SvGenericClass(gsym.name, _package_of(qname, self.types.packages), qname,
                               self.attrs_of(gsym), self.loc(gsym), slang=gsym)
            self.model._generics[qname] = g
        return g

    def class_key(self, ct) -> str:
        return self.types.class_spelling(ct) or self.types.class_qname(ct)

    def class_for(self, ct) -> Union[SvClass, ExternRef]:
        key = self.class_key(ct)
        if key in self.model._classes:
            return self.model._classes[key]
        if key in self._building:
            return self._building[key]

        generic = None
        params: Dict[str, str] = {}
        if ct.genericClass is not None:
            gpath = ct.genericClass.lexicalPath or ct.genericClass.name
            if _package_of(gpath, self.types.packages) is None and "::" not in gpath and "." in gpath:
                return ExternRef(key, slang=ct)
            generic = self.generic_for(ct.genericClass)
            for m in ct:
                if m.kind == SK.Parameter and m.isPortParam:
                    params[m.name] = str(m.value)
                elif m.kind == SK.TypeParameter and m.isPortParam:
                    params[m.name] = str(self.types.convert(m.targetType.type))
            attrs = dict(generic.attrs)
        else:
            path = ct.lexicalPath or ct.name
            if "." in path:
                return ExternRef(key, slang=ct)      # declared inside a module
            attrs = self.attrs_of(ct)

        self._keep.append(ct)
        qname = key
        name = ct.genericClass.name if generic is not None else ct.name
        cls = SvClass(name=name, package=_package_of(qname, self.types.packages), qname=qname,
                      type_expr=self.types.class_spelling(ct),
                      is_abstract=bool(ct.isAbstract) or bool(ct.isInterface),
                      is_interface=bool(ct.isInterface),
                      params=params, generic=generic, attrs=attrs,
                      loc=self.loc(ct.genericClass if generic is not None else ct), slang=ct)
        self._building[key] = cls

        base = ct.baseClass
        if base is not None:
            if base.isError:
                self.error("base class of '%s' could not be resolved" % qname, ct)
            elif isinstance(base.canonicalType, A.ClassType):
                cls.base = self.class_for(base.canonicalType)
        for itf in ct.implementedInterfaces or []:
            if isinstance(itf.canonicalType, A.ClassType):
                cls.implements.append(self.class_for(itf.canonicalType))

        for m in ct:
            k = m.kind
            if k == SK.ClassProperty:
                cls.fields.append(self.field_for(m, cls))
            elif k in (SK.Subroutine, SK.MethodPrototype):
                if int(m.flags) & int(A.MethodFlags.BuiltIn):
                    continue
                cls.methods.append(self.method_for(m, cls))

        del self._building[key]
        self.model._add_class(cls)
        if generic is not None and cls not in generic.specializations:
            generic.specializations.append(cls)
        return cls

    def field_for(self, m, owner: SvClass) -> SvField:
        rm = {A.RandMode.Rand: RandMode.RAND, A.RandMode.RandC: RandMode.RANDC}.get(m.randMode, RandMode.NONE)
        return SvField(
            name=m.name, type=self.types.convert(m.type), rand=rm,
            static=m.lifetime == A.VariableLifetime.Static,
            const=bool(int(m.flags) & int(A.VariableFlags.Const)),
            visibility=_visibility(m.visibility), attrs=self.attrs_of(m),
            owner=owner, loc=self.loc(m), slang=m)

    def method_for(self, m, owner: SvClass) -> SvMethod:
        flags = int(m.flags)
        is_ctor = bool(flags & int(A.MethodFlags.Constructor))
        kind = MethodKind.TASK if m.subroutineKind == A.SubroutineKind.Task else MethodKind.FUNCTION
        args = []
        for a in m.arguments:
            d = _ARG_DIR[a.direction]
            if d == ArgDir.REF and int(a.flags) & int(A.VariableFlags.Const):
                d = ArgDir.CONST_REF
            default = None
            dv = a.defaultValue
            # Implicit conversions have no syntax of their own; use the operand's.
            while dv is not None and dv.syntax is None and hasattr(dv, "operand"):
                dv = dv.operand
            if dv is not None and dv.syntax is not None:
                default = str(dv.syntax).strip()
            args.append(SvArg(a.name, d, self.types.convert(a.type), default))
        ret = None
        if kind == MethodKind.FUNCTION and not is_ctor:
            ret = self.types.convert(m.returnType)
        return SvMethod(
            name=m.name, kind=kind,
            virtual=bool(m.isVirtual) or bool(flags & int(A.MethodFlags.Virtual)),
            pure=bool(flags & int(A.MethodFlags.Pure)),
            static=bool(flags & int(A.MethodFlags.Static)),
            is_constructor=is_ctor, args=args, ret=ret,
            visibility=_visibility(m.visibility), attrs=self.attrs_of(m),
            owner=owner, loc=self.loc(m), slang=m)


_ARG_DIR = {
    A.ArgumentDirection.In: ArgDir.INPUT,
    A.ArgumentDirection.Out: ArgDir.OUTPUT,
    A.ArgumentDirection.InOut: ArgDir.INOUT,
    A.ArgumentDirection.Ref: ArgDir.REF,
}


def _visibility(v) -> Visibility:
    if v == A.Visibility.Local:
        return Visibility.LOCAL
    if v == A.Visibility.Protected:
        return Visibility.PROTECTED
    return Visibility.PUBLIC


def _package_of(qname: str, packages) -> Optional[str]:
    head = qname.split("::", 1)[0]
    return head if "::" in qname and head in packages else None


def _attr_value(spec) -> Any:
    """``(* a *)`` -> True; ``(* a = 3 *)`` -> 3; ``(* a = "x" *)`` -> "x";
    anything else -> the expression's source text."""
    if spec is None or spec.value is None:
        return True
    text = str(spec.value.expr).strip()
    if len(text) >= 2 and text[0] == '"' and text[-1] == '"':
        return text[1:-1]
    try:
        return int(text.replace("_", ""), 10)
    except ValueError:
        return text


def build_model(loaded: Loaded) -> SvModel:
    return ModelBuilder(loaded).build()
