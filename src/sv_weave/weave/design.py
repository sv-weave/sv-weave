"""``DesignCtx``: what an ``on_design`` handler receives (design §6.7).

An ``on_design`` handler runs once per profile, after every per-class handler and
before the bindings' ``finalize``. It sees the whole model and can:
- contribute to a target's woven class (``feature_of``, ``override_of``);
- add package-level code (``add_item``, ``add_class``) to ``<pkg>_woven``;
- add registration statements to that package's ``__register()``.

Aggregate code about a class ``T`` usually goes to ``T``'s package. Woven packages
compile after every user package, so importing user packages from there is always
legal. Code that names *woven* classes of other packages must say so (``uses_woven``);
if that creates an import cycle between woven packages, the code moves to
``sv_weave_gen_pkg``, which compiles after all of them.
"""
import dataclasses as dc
from typing import Any, Dict, List, Optional, Sequence, Set, Tuple

from ..diag import Diag, Severity, SrcLoc, SvWeaveError
from ..frontend.model import SvClass
from .ctx import WeaveCtx, WovenClassBuilder
from .model import Origin, SvFragment, call_site

GEN_PKG = "sv_weave_gen_pkg"


@dc.dataclass
class Aggregate:
    """Package-level contributions from design handlers, per user package."""
    items: List[SvFragment] = dc.field(default_factory=list)
    registrations: List[str] = dc.field(default_factory=list)
    imports: List[str] = dc.field(default_factory=list)
    uses_woven: Set[str] = dc.field(default_factory=set)


class DesignCtx:
    def __init__(self, model, profile: str, ext_set: str, options: Dict[str, Any],
                 weaver: str, builders: Dict[int, WovenClassBuilder], bindings: Dict[str, Any],
                 aggregates: Dict[str, Aggregate], diags: List[Diag]):
        self.model = model
        self.profile = profile
        self.ext_set = ext_set
        self.options = dict(options or {})
        self.bindings = bindings
        self._weaver = weaver
        self._builders = builders
        self._aggregates = aggregates
        self._diags = diags
        self._touched: List[WovenClassBuilder] = []

    # -- woven classes ---------------------------------------------------------------
    def woven(self, cls: SvClass):
        """The woven class of a target in this profile, or None."""
        b = self._builders.get(id(cls))
        return b.woven if b is not None and b.woven.contributed else None

    def _ctx_for(self, cls: SvClass) -> WeaveCtx:
        b = self._builders.get(id(cls))
        if b is None:
            raise self._error("%s is not a target class, so it has no woven class to "
                              "contribute to" % cls.qname)
        if b not in self._touched:
            b._current = (self._weaver, self.ext_set)
            rel = getattr(self, "_relations", ((), ()))
            if rel[0] or rel[1]:
                b.relations[(self._weaver, self.ext_set)] = rel
            self._touched.append(b)
        return WeaveCtx(b, self.ext_set, self.options)

    def feature_of(self, cls: SvClass, name: str):
        return self._ctx_for(cls).feature(name)

    def override_of(self, cls: SvClass, method: str):
        return self._ctx_for(cls).override(method)

    def binding_of(self, cls: SvClass):
        """The binding whose root ``cls`` derives from, or None."""
        for b in self.bindings.values():
            for r in b.roots:
                if cls.is_a(r):
                    return b
        return None

    # -- package-level code ----------------------------------------------------------
    def _agg(self, pkg: str) -> Aggregate:
        return self._aggregates.setdefault(pkg, Aggregate())

    def _origin(self) -> Origin:
        f, l = call_site()
        return Origin(self._weaver, self.ext_set, f, l)

    def add_item(self, pkg: str, text: str, imports: Sequence[str] = (),
                 uses_woven: Sequence[str] = ()) -> None:
        """Package-level code in ``<pkg>_woven``. ``imports``: user packages it needs;
        ``uses_woven``: user packages whose *woven* package it references. The same
        text added twice (for example by two profiles) is kept once."""
        a = self._agg(pkg)
        if any(f.text == text for f in a.items):
            return
        a.items.append(SvFragment(text, self._origin()))
        for i in imports:
            if i != pkg and i not in a.imports:
                a.imports.append(i)
        a.uses_woven.update(u for u in uses_woven if u != pkg)

    add_class = add_item

    def add_registration(self, pkg: str, stmt: str) -> None:
        """An SV statement for ``<pkg>_woven``'s ``__register()``. Kept once."""
        a = self._agg(pkg)
        if stmt not in a.registrations:
            a.registrations.append(stmt)

    # -- diagnostics -----------------------------------------------------------------
    def warning(self, msg: str, loc: Optional[SrcLoc] = None):
        self._diags.append(Diag(Severity.WARNING, "%s: %s" % (self._weaver, msg), loc))

    def error(self, msg: str, loc: Optional[SrcLoc] = None):
        self._diags.append(Diag(Severity.ERROR, "%s: %s" % (self._weaver, msg), loc))

    def _error(self, msg: str) -> SvWeaveError:
        f, l = call_site()
        return SvWeaveError([Diag(Severity.ERROR, "%s: %s" % (self._weaver, msg),
                                  SrcLoc(f, l) if f else None)])

    def _release(self):
        for b in self._touched:
            b._current = None
        self._touched = []


def gen_package_cycles(aggregates: Dict[str, Aggregate]) -> Set[str]:
    """User packages whose aggregate code takes part in a cycle of woven-package
    references; their code moves to sv_weave_gen_pkg."""
    graph = {p: set(a.uses_woven) for p, a in aggregates.items()}
    in_cycle: Set[str] = set()
    for start in graph:
        stack, seen = [(start, [start])], set()
        while stack:
            node, path = stack.pop()
            for nxt in graph.get(node, ()):
                if nxt == start:
                    in_cycle.update(path)
                elif nxt not in seen:
                    seen.add(nxt)
                    stack.append((nxt, path + [nxt]))
    return in_cycle
