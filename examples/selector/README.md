# Selector: an example design-wide weaver

`selector_weaver.py` is the worked example of `bus.on_design` (design §6.7). For each
base class marked `(* weave_select *)` it finds every concrete subclass in the design
(`d.model.subclasses_of`) and generates code that lets the testbench count them and
create one at random, weighted by `(* weave_weight = N *)`, without naming them.

It is **not** part of sv-weave. sv-weave does not keep a type registry of its own; it
works with the class library's registry (for UVM, `uvm_factory`). Random selection is
testbench-library policy, so a real version belongs in a UVM utility library, built on
`uvm_factory` rather than on the small `select_pkg.sv` registry used here.

Use it from a config:

```yaml
sv-weave:
  plugin-path: [path/to/examples/selector]
  weavers:
  - {name: "selector_weaver:SelectorWeaver"}
```

and compile `select_pkg.sv` after `reflib_pkg.sv` and before the design. Tests:
`tests/sim/test_selector.py`, `tests/unit/test_design.py`.
