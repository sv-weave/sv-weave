"""``print``: one ``name: value`` line per field, through the binding's ``print``
feature."""
from ..match import extends_root, has_attr
from ..plugin import Weaver
from .copy import copyable


class PrintWeaver(Weaver):
    name = "print"
    version = "0.1"

    def subscribe(self, bus):
        bus.on(extends_root() & ~has_attr("weave_noprint"), self.weave)

    def weave(self, w):
        slot = w.feature("print")
        if slot.ret_var is None:
            w.error("binding '%s': the print feature must return a string" % w.binding.name)
            return
        for f in w.fields():
            if not copyable(w, f, "weave_noprint"):
                continue
            text = w.sv.print_field(f, slot.ret_var)
            if text:
                slot.body.add(text)
