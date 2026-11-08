from sv_weave import plugin
from sv_weave.match import extends_root


class PrintFields(plugin.Weaver):
    """Implements the 'print' feature: one name=value line per field."""
    name = "print-fields"

    def subscribe(self, bus):
        bus.on(extends_root(), self.weave)

    def weave(self, w):
        p = w.feature("print")
        for f in w.fields():
            if f.static or not w.sv.accessible(f):
                continue
            p.body.add('%s = {%s, $sformatf("%s=%%0h\\n", %s)};'
                       % (p.ret_var, p.ret_var, f.name, f.name))
