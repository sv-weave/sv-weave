"""``compare``: field-by-field comparison through the binding's ``compare`` feature.
The first differing field is reported through the binding's miscompare hook."""
from ..match import extends_root, has_attr
from ..plugin import Weaver
from .copy import copyable


class CompareWeaver(Weaver):
    name = "compare"
    version = "0.1"

    def subscribe(self, bus):
        bus.on(extends_root() & ~has_attr("weave_nocompare"), self.weave)

    def weave(self, w):
        slot = w.feature("compare")
        rhs = w.sv.cast_rhs(slot)
        if slot.ret_var is None:
            w.error("binding '%s': the compare feature must return a value" % w.binding.name)
            return
        for f in w.fields():
            if not copyable(w, f, "weave_nocompare"):
                continue
            text = w.sv.compare_field(f, rhs, slot.ret_var,
                                      w.binding.miscompare_stmt(w.cls, f.name))
            if text:
                slot.body.add(text)
