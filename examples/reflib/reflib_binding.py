"""Binding for the reference library ``reflib_pkg`` (``reflib_pkg.sv`` in this
directory). An example of a binding, not part of sv-weave.

User classes derive from ``reflib_pkg::ref_object`` and are created with
``ref_factory#(T)::create()``. The features map onto ``ref_object``'s virtual
methods. Each woven package gets, per registered woven class,
a ``ref_impl#(T)`` subclass that creates it; the statements returned by
``package_items`` add them to the runtime from the package's ``__register()``
(design §8.2).
"""
from typing import Dict

import os

from sv_weave.plugin import Binding, FeatureSpec
from sv_weave.weave.model import Origin, SvFragment

HERE = os.path.dirname(os.path.abspath(__file__))


def _q(s: str) -> str:
    return '"%s"' % s.replace("\\", "\\\\").replace('"', '\\"')


class ReflibBinding(Binding):
    name = "reflib"
    version = "0.1"
    roots = ("reflib_pkg::ref_object",)

    def features(self) -> Dict[str, FeatureSpec]:
        return {
            "copy": FeatureSpec("copy", "copy", args=("reflib_pkg::ref_object rhs",), arg_names=("rhs",),
                                rhs="rhs"),
            "compare": FeatureSpec("compare", "compare", args=("reflib_pkg::ref_object rhs",),
                                   arg_names=("rhs",), ret="bit", rhs="rhs"),
            "print": FeatureSpec("print", "sprint", ret="string"),
        }

    def imports(self):
        return ["reflib_pkg"]

    def sv_runtime_files(self):
        return [os.path.join(HERE, "reflib_pkg.sv")]

    def create_expr(self, cls, inst: str = ""):
        if cls.is_a("reflib_pkg::ref_object") and cls.type_expr:
            return "reflib_pkg::ref_factory #(%s)::create(%s)" % (cls.type_expr, inst)
        return None

    def miscompare_stmt(self, cls, field: str) -> str:
        return "reflib_pkg::ref_miscompare(%s, %s);" % (_q(cls.qname), _q(field))

    def finalize(self, w) -> None:
        # ref_factory calls new() with no arguments.
        for c in [w.cls] + w.cls.ancestors():
            ctor = next((m for m in c.methods if m.is_constructor), None)
            if ctor is not None:
                required = [a.name for a in ctor.args if a.default is None]
                if required:
                    w.error("%s cannot be created by ref_factory: its constructor "
                            "has arguments without defaults (%s)"
                            % (w.cls.qname, ", ".join(required)), ctor.loc)
                break
        s = w.override("ref_impl_name")
        s.replace_super()
        s.set_result(_q(w.woven.name))

    def package_items(self, wpkg, cfg):
        origin = Origin(self.name, None)
        regs = []
        for wc in wpkg.classes:
            if not wc.concrete or wc.target.binding != self.name:
                continue
            t = wc.cls.type_expr
            impl = wc.name + "__impl"
            wpkg.items.append(SvFragment("""
                class %(impl)s extends reflib_pkg::ref_impl #(%(t)s);
                  local string m_profile;
                  function new(string profile);
                    m_profile = profile;
                  endfunction
                  virtual function string impl_name();
                    return %(name)s;
                  endfunction
                  virtual function string profile();
                    return m_profile;
                  endfunction
                  virtual function string type_name();
                    return %(tname)s;
                  endfunction
                  virtual function %(t)s create();
                    %(cls)s o = new();
                    return o;
                  endfunction
                endclass : %(impl)s""" % dict(impl=impl, t=t, name=_q(wc.name),
                                               tname=_q(wc.cls.qname), cls=wc.name), origin))
            regs.append((impl, t, wc))
        stmts = ["reflib_pkg::ref_profiles::set_config_default(%s);" % _q(cfg.default_profile)]
        for impl, t, wc in regs:
            for prof in wc.profiles:
                var = "i_" + wc.name
                stmts += ["begin",
                          "  %s %s = new(%s);" % (impl, var, _q(prof)),
                          "  reflib_pkg::ref_type #(%s)::add(%s, %s);" % (t, _q(prof), var),
                          "  reflib_pkg::ref_registry::inst().add_type(%s, %s);"
                          % (_q(wc.cls.qname), var),
                          "end"]
        return stmts
