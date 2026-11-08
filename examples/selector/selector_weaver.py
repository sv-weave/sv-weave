"""Example design-wide weaver: lets code enumerate and randomly create the concrete
subclasses of a base class, without naming them (design §6.7).

Not part of sv-weave's built-in weavers: random selection is testbench-library
policy. It is kept as the worked example of ``bus.on_design``. Its runtime is
``select_pkg.sv`` in this directory, compiled after reflib_pkg.

For each base ``T`` (``options.bases``, and every class marked ``(* weave_select *)``),
it registers one ``select_entry#(T)`` per concrete subclass with
``select_pkg::select_types#(T)``:

    p = select_types #(pkt)::create_random("env.gen");   // weighted random pick
    n = select_types #(pkt)::count();
    p = select_types #(pkt)::create(i, "env.gen");

Each entry creates its subclass through the binding's factory, so overrides and woven
implementations apply. ``(* weave_weight = N *)`` on a subclass sets its weight
(default 1; 0 means never picked by ``create_random``, though still listed).

Options: ``bases`` (class names), ``include_base`` (also list ``T`` itself when it is
concrete; default false). The generated code allocates, so the weaver belongs in an
extension set with ``allow_alloc`` (``core`` has it).
"""
from sv_weave.match import has_attr
from sv_weave.plugin import Weaver
from sv_weave.weave.ctx import spec_hash


def _q(s: str) -> str:
    return '"%s"' % s.replace('"', '\\"')


class SelectorWeaver(Weaver):
    name = "selector"
    version = "0.1"

    def subscribe(self, bus):
        bus.on_design(self.design)

    def _bases(self, d):
        out = []
        for name in self.options.get("bases", []):
            c = d.model.find_class(name)
            if c is not None:
                out.append(c)
                continue
            g = d.model.generic(name)
            if g is not None:
                out.extend(g.specializations)
                continue
            d.error("selector: no class named '%s'" % name)
        for c in d.model.classes(has_attr("weave_select")):
            if c not in out:
                out.append(c)
        return out

    def design(self, d):
        for base in self._bases(d):
            if base.package is None or base.type_expr is None:
                d.error("selector: %s is not in a package; it cannot be a selector base"
                        % base.qname, base.loc)
                continue
            subs = d.model.subclasses_of(base, concrete=True)
            if self.options.get("include_base") and not base.is_abstract:
                subs = [base] + subs
            for sub in subs:
                self._entry(d, base, sub)

    def _entry(self, d, base, sub):
        if sub.package is None or sub.type_expr is None:
            d.warning("selector: %s cannot be named from a package; not selectable" % sub.qname,
                      sub.loc)
            return
        weight = sub.attrs.get("weave_weight", 1)
        if isinstance(weight, bool) or not isinstance(weight, int) or weight < 0:
            d.error("selector: weave_weight on %s must be a non-negative integer, not %r"
                    % (sub.qname, weight), sub.loc)
            return
        binding = d.binding_of(sub)
        create = binding.create_expr(sub, "inst_path") if binding is not None else None
        if create is None:
            ctor = sub.find_method("new")
            if ctor is not None and any(a.default is None for a in ctor.args):
                d.warning("selector: %s needs constructor arguments; not selectable" % sub.qname,
                          sub.loc)
                return
            create = "new()"
        name = "__sv_weave_sel_%s" % spec_hash(base.qname + "|" + sub.qname)
        t, s = base.type_expr, sub.type_expr
        if create == "new()":
            body = "%s o = new();" % s
        else:
            body = "%s o = %s;" % (s, create)
        d.add_item(base.package, """
            // selector entry: %(sq)s as a %(tq)s
            class %(name)s extends select_pkg::select_entry #(%(t)s);
              virtual function string type_name();
                return %(sname)s;
              endfunction
              virtual function int unsigned weight();
                return %(w)d;
              endfunction
              virtual function %(t)s create(string inst_path);
                %(body)s
                return o;
              endfunction
            endclass : %(name)s""" % dict(sq=sub.qname, tq=base.qname, name=name, t=t,
                                          sname=_q(sub.qname), w=weight, body=body),
                   imports=[sub.package])
        d.add_registration(base.package, "begin\n  %s e = new();\n  "
                           "select_pkg::select_types #(%s)::add(e);\nend" % (name, t))
