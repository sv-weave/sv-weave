"""``xcheck``: a debug weaver that reports X/Z values in four-state fields.

Checks run in ``post_randomize`` (rand fields) and after ``copy`` (every four-state
field copied). Meant for a debug extension set, such as ``debug.xcheck``: it neither
randomises, allocates, forks nor adds state, so it passes the rand-safety rules with
every flag off.

Options: ``on_x``: ``error`` (default), ``warning`` or ``fatal``.
Field attribute: ``(* weave_noxcheck *)`` skips a field.
"""
from ..frontend.types import TypeCat
from ..match import extends_root, has_field
from ..plugin import Weaver

_SEVERITY = {"error": "$error", "warning": "$warning", "fatal": "$fatal(1, "}


def _checkable(f) -> bool:
    return (f.type.cat in (TypeCat.INTEGRAL, TypeCat.ENUM) and f.type.four_state
            and not f.static and "weave_noxcheck" not in f.attrs)


class XCheckWeaver(Weaver):
    name = "xcheck"
    version = "0.1"
    order = -10          # outermost: its checks run after the other weavers' code

    def subscribe(self, bus):
        bus.on(extends_root() & has_field(_checkable), self.weave)

    def _check(self, w, f, when: str) -> str:
        sev = self.options.get("on_x", "error")
        if sev not in _SEVERITY:
            w.error("xcheck: on_x must be error, warning or fatal, not '%s'" % sev)
            sev = "error"
        call = _SEVERITY[sev]
        msg = '"sv-weave xcheck: %s.%s is X/Z after %s: %%0b", this.%s' % (
            w.cls.qname, f.name, when, f.name)
        if call.endswith("("):
            return "if ($isunknown(this.%s)) %s%s);" % (f.name, call, msg)
        return "if ($isunknown(this.%s)) %s(%s);" % (f.name, call, msg)

    def weave(self, w):
        fields = [f for f in w.fields()
                  if _checkable(f) and w.sv.accessible(f, report=False)]
        rand_fields = [f for f in fields if f.rand.value != "none"]
        if rand_fields:
            if w.cls.find_method("post_randomize") is not None:
                slot = w.override("post_randomize")
            else:
                slot = w.add_method("post_randomize", virtual=False)
            for f in rand_fields:
                slot.post.add(self._check(w, f, "randomize"))
        if "copy" in w.binding.features():
            slot = w.feature("copy")
            for f in fields:
                if "weave_nocopy" not in f.attrs:
                    slot.post.add(self._check(w, f, "copy"))
