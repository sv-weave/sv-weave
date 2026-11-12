"""The event bus (design §6.1, §6.7): subscriptions and deterministic dispatch.

Dispatch order, per profile:
1. for each target: the binding's ``prepare``, then matching weaver subscriptions, by
   ``order``, then weaver name, then the order the weaver subscribed in;
2. ``on_design`` handlers, in the same order;
3. for each target that a weaver contributed to: the binding's ``finalize``.

A subscription runs only for profiles that include its weaver's extension set.
"""
import dataclasses as dc
import traceback
from typing import Any, Callable, Dict, List, Optional, Sequence

from .diag import Diag, Severity, SrcLoc, SvWeaveError
from .frontend.model import SvClass
from .match import Pred, parse
from .plugin import Weaver
from .weave.ctx import WeaveCtx, WovenClassBuilder
from .weave.model import WovenClass, WovenPackage


@dc.dataclass
class Subscription:
    weaver: str
    ext_set: str
    order: int
    seq: int
    pred: Callable[[SvClass], bool]
    handler: Callable[[WeaveCtx], None]
    options: Dict[str, Any]
    before: tuple = ()
    after: tuple = ()


@dc.dataclass
class _Active:
    weaver: Weaver
    ext_set: str
    order: int
    match: Optional[Pred]
    before: tuple = ()
    after: tuple = ()


class Bus:
    def __init__(self):
        self.subs: List[Subscription] = []
        self.design_subs: List[Subscription] = []
        self._active: Optional[_Active] = None
        self._seq = 0

    # -- weaver side -----------------------------------------------------------------
    def on(self, pred: Callable[[SvClass], bool], handler: Callable[[WeaveCtx], None]) -> None:
        """Calls ``handler(w)`` for every target (and profile) that ``pred`` matches."""
        a = self._require_active("on")
        if a.match is not None:
            pred = (pred & a.match) if isinstance(pred, Pred) else _and(pred, a.match)
        self.subs.append(Subscription(a.weaver.name, a.ext_set, a.order, self._next(),
                                      pred, handler, a.weaver.options, a.before, a.after))

    def on_design(self, handler: Callable[[Any], None]) -> None:
        """Calls ``handler(d)`` once per profile, after all per-class handlers (§6.7)."""
        a = self._require_active("on_design")
        self.design_subs.append(Subscription(a.weaver.name, a.ext_set, a.order, self._next(),
                                             lambda c: True, handler, a.weaver.options,
                                             a.before, a.after))

    def _next(self) -> int:
        self._seq += 1
        return self._seq

    def _require_active(self, what: str) -> _Active:
        if self._active is None:
            raise RuntimeError("Bus.%s() may only be called from Weaver.subscribe()" % what)
        return self._active

    # -- framework side --------------------------------------------------------------
    def subscribe(self, weaver: Weaver, ext_set: str, order: int = 0,
                  match: Optional[str] = None, where: str = "",
                  before=(), after=()) -> None:
        self._active = _Active(weaver, ext_set, order, parse(match, where) if match else None,
                               tuple(getattr(weaver, "before", ())) + tuple(before),
                               tuple(getattr(weaver, "after", ())) + tuple(after))
        try:
            weaver.subscribe(self)
        finally:
            self._active = None

    def ordered(self) -> List[Subscription]:
        return sorted(self.subs, key=lambda s: (s.order, s.weaver, s.seq))

    def wanted(self, cls: SvClass) -> bool:
        """Whether a class can receive contributions. Design handlers may contribute to
        any class, so with one subscribed every claimed class qualifies."""
        return bool(self.design_subs) or any(s.pred(cls) for s in self.subs)

    def dispatch(self, targets: Sequence, profiles: Sequence[str], profile_sets: Callable,
                 bindings: Dict[str, Any], cfg, model, aggregates=None, files=None):
        """Runs every handler. Per profile: bindings' ``prepare`` and the weavers for
        each target, then the ``on_design`` handlers, then bindings' ``finalize`` for
        each target some weaver contributed to. Returns (woven classes, diagnostics);
        design-handler package code collects in ``aggregates``, whole files in
        ``files``."""
        from .weave.design import DesignCtx
        diags: List[Diag] = []
        out: List[WovenClass] = []
        aggregates = {} if aggregates is None else aggregates
        subs = self.ordered()
        dsubs = sorted(self.design_subs, key=lambda s: (s.order, s.weaver, s.seq))
        for profile in profiles:
            sets = set(profile_sets(profile))
            builders: Dict[int, WovenClassBuilder] = {}
            for t in targets:
                binding = bindings[t.binding]
                b = WovenClassBuilder(t, profile, binding, cfg, model, diags)
                builders[id(t.cls)] = b
                with b.contributor(binding.name, None):
                    _call(binding.prepare, WeaveCtx(b), binding.name, t, diags)
                for s in subs:
                    if s.ext_set not in sets or not s.pred(t.cls):
                        continue
                    with b.contributor(s.weaver, s.ext_set, s.before, s.after):
                        _call(s.handler, WeaveCtx(b, s.ext_set, s.options), s.weaver, t, diags)
            for s in dsubs:
                if s.ext_set not in sets:
                    continue
                d = DesignCtx(model, profile, s.ext_set, s.options, s.weaver, builders,
                              bindings, aggregates, diags, files)
                d._relations = (s.before, s.after)
                try:
                    _call(s.handler, d, s.weaver, None, diags)
                finally:
                    d._release()
            for t in targets:
                b = builders[id(t.cls)]
                if not b.woven.contributed:
                    continue
                with b.contributor(b.binding.name, None):
                    _call(b.binding.finalize, WeaveCtx(b), b.binding.name, t, diags)
                out.append(b.woven)
        return out, diags


def _and(a, b):
    return lambda c: a(c) and b(c)


def _call(fn, ctx, who: str, target, diags: List[Diag]) -> None:
    try:
        fn(ctx)
    except SvWeaveError as e:
        diags.extend(e.diags)
    except Exception as e:
        tb = traceback.extract_tb(e.__traceback__)
        frame = tb[-1] if tb else None
        loc = SrcLoc(frame.filename, frame.lineno) if frame else None
        on = (" on %s" % target.cls.qname) if target is not None else ""
        diags.append(Diag(Severity.ERROR, "%s failed%s: %s: %s"
                          % (who, on, type(e).__name__, e), loc))
