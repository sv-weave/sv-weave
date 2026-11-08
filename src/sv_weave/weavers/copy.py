"""``copy``: copies every field, up to the binding root, through the binding's ``copy``
feature (design §6.4)."""
from ..match import extends_root, has_attr
from ..plugin import Weaver


def copyable(w, f, skip_attr: str) -> bool:
    """Fields a field weaver handles: not static, not const, not opted out, reachable."""
    if f.static or f.const or skip_attr in f.attrs:
        return False
    return w.sv.accessible(f)


class CopyWeaver(Weaver):
    name = "copy"
    version = "0.1"

    def subscribe(self, bus):
        bus.on(extends_root() & ~has_attr("weave_nocopy"), self.weave)

    def weave(self, w):
        slot = w.feature("copy")
        rhs = w.sv.cast_rhs(slot)
        for f in w.fields():
            if copyable(w, f, "weave_nocopy"):
                text = w.sv.copy_field(f, rhs)
                if text:
                    slot.body.add(text)
