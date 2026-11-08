"""Stage 5, Check: model-level checks on the woven classes (design §5, §6.3, §6.5).

- An overridden method must be virtual and not static. Reported at the user's
  declaration of the method.
- Added fields need an extension set with ``allow_state``.
- A woven class that leaves a pure virtual method unimplemented is not concrete, so it
  is not registered (a note, not an error).
"""
from typing import List

from .diag import Diag, Severity, SrcLoc
from .weave.model import MethodSlot, OrderError, WovenClass


# pre_randomize/post_randomize behave as virtual without being declared so (1800-2017 18.6.2).
IMPLICITLY_VIRTUAL = {"pre_randomize", "post_randomize"}


def _at(origin):
    return SrcLoc(origin.file, origin.line) if origin is not None and origin.file else None


def check(woven: List[WovenClass], cfg) -> List[Diag]:
    diags: List[Diag] = []
    for wc in woven:
        for slot in wc.slots.values():
            for part in (slot.decl, slot.pre, slot.post):
                try:
                    part.ordered()
                except OrderError as e:
                    diags.append(Diag(Severity.ERROR, "%s: %s" % (wc.name, e),
                                      _at(slot.first_origin)))
            m = slot.overrides
            if slot.kind in (MethodSlot.KIND_OVERRIDE, MethodSlot.KIND_FEATURE) and m is not None:
                if m.static:
                    diags.append(Diag(Severity.ERROR, "%s::%s is static; cannot weave (from %s)"
                                      % (m.owner.qname, m.name, slot.first_origin), m.loc))
                elif not m.virtual and m.name not in IMPLICITLY_VIRTUAL:
                    diags.append(Diag(Severity.ERROR,
                                      "%s::%s is not virtual; cannot weave (requested by %s). "
                                      "Declare it virtual in %s."
                                      % (m.owner.qname, m.name, slot.first_origin, m.owner.qname),
                                      m.loc))
        for f in wc.fields:
            es = f.origin.ext_set if f.origin else None
            if es is not None and not cfg.extension_sets[es].allow_state:
                diags.append(Diag(Severity.ERROR,
                                  "%s adds a field to %s, but extension set '%s' does not "
                                  "allow_state: %s" % (f.origin.contributor, wc.name, es, f.text),
                                  _at(f.origin)))
        implemented = {n for n, s in wc.slots.items()}
        missing = [m for m in wc.cls.unimplemented_pure() if m.name not in implemented]
        wc.unimplemented = [m.name for m in missing]
        wc.concrete = not missing
        if missing:
            diags.append(Diag(Severity.NOTE,
                              "%s is abstract (pure virtual %s not implemented); it is not "
                              "registered" % (wc.name, ", ".join(m.name for m in missing)),
                              wc.cls.loc))
    return diags
