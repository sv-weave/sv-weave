"""Stage 3, Select: which classes get woven (design §5).

A class is a target when all of these hold:
1. its package passes ``packages.include`` / ``exclude``; library and generated
   packages are always excluded;
2. exactly one binding claims it, because it derives from one of that binding's roots;
3. it is not marked ``(* weave_off *)``;
4. at least one weaver subscription matches it (``wanted``; the bus supplies this from P2).

Interface classes and classes outside any package are never targets. Every class that
is not a target gets a reason, for ``sv-weave list`` and the report.
"""
import dataclasses as dc
import fnmatch
from typing import Callable, Dict, List, Optional, Protocol, Sequence, Union

from .config import Config
from .diag import Diag, Severity, SvWeaveError
from .frontend.model import ExternRef, SvClass, SvModel

# Packages that are never woven, whatever the config says.
ALWAYS_EXCLUDED = ["std", "uvm_pkg", "sv_weave_pkg", "sv_weave_*", "*_woven"]


class RootClaim(Protocol):
    """What selection needs from a binding: its name and its root class names."""
    name: str
    roots: Sequence[str]


@dc.dataclass
class StubBinding:
    """Just a name and roots: enough for selection (tests use it)."""
    name: str
    roots: Sequence[str]


@dc.dataclass(eq=False)
class Target:
    cls: SvClass
    binding: str
    root: Union[SvClass, ExternRef]      # the binding root this class derives from

    def __repr__(self):
        return "Target(%s via %s)" % (self.cls.qname, self.binding)


@dc.dataclass
class Selection:
    targets: List[Target]
    skipped: Dict[str, str]              # class qname -> reason
    diags: List[Diag]

    def target(self, qname: str) -> Optional[Target]:
        for t in self.targets:
            if t.cls.qname == qname:
                return t
        return None


def package_selected(name: Optional[str], cfg: Config) -> bool:
    if name is None:
        return False
    if any(fnmatch.fnmatchcase(name, p) for p in ALWAYS_EXCLUDED):
        return False
    if not any(fnmatch.fnmatchcase(name, p) for p in cfg.packages.include):
        return False
    return not any(fnmatch.fnmatchcase(name, p) for p in cfg.packages.exclude)


def _root_of(cls: SvClass, roots: Sequence[str]):
    for a in cls.ancestors():
        for r in roots:
            if a.qname == r or a.name == r or (a.generic is not None and a.generic.qname == r):
                return a
    # A root outside the model (ExternRef) can still be named by qname.
    b = cls.base
    while isinstance(b, SvClass):
        b = b.base
    if isinstance(b, ExternRef) and b.qname in roots:
        return b
    return None


def select(model: SvModel, cfg: Config, bindings: Sequence[RootClaim],
           wanted: Optional[Callable[[SvClass], bool]] = None) -> Selection:
    targets: List[Target] = []
    skipped: Dict[str, str] = {}
    diags: List[Diag] = []

    for cls in model.classes():
        if not package_selected(cls.package, cfg):
            skipped[cls.qname] = ("not in a package" if cls.package is None
                                  else "package '%s' not selected" % cls.package)
            continue
        if cls.is_interface:
            skipped[cls.qname] = "interface class"
            continue
        claims = []
        for b in bindings:
            root = _root_of(cls, b.roots)
            if root is not None:
                claims.append((b, root))
        if not claims:
            skipped[cls.qname] = "no binding root among its base classes"
            continue
        if len(claims) > 1:
            diags.append(Diag(Severity.ERROR, "class '%s' is claimed by bindings %s"
                              % (cls.qname, ", ".join(b.name for b, _ in claims)), cls.loc))
            skipped[cls.qname] = "claimed by more than one binding"
            continue
        if "weave_off" in cls.attrs:
            skipped[cls.qname] = "(* weave_off *)"
            continue
        if wanted is not None and not wanted(cls):
            skipped[cls.qname] = "no weaver subscription matches"
            continue
        b, root = claims[0]
        targets.append(Target(cls, b.name, root))

    errs = [d for d in diags if d.severity == Severity.ERROR]
    if errs:
        raise SvWeaveError(errs, "target selection failed")
    return Selection(targets, skipped, diags)
