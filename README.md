# sv-weave

**Factory weaving for SystemVerilog class libraries.**

You write plain SystemVerilog classes against your class library's base classes: no
macros, no generated code to merge with your own. sv-weave reads your sources with
[slang](https://github.com/MikePopoloski/slang) (through pyslang), and its plugins
generate a subclass of each matching class that implements the library's virtual hooks
(for UVM: `do_copy`, `do_compare`, `convert2string`, ...). The library's own factory
resolves your overrides as usual and then hands out the generated class wherever your
code asks for the original. Your code never names the generated code.

This is the model of .NET's [Fody](https://github.com/Fody/Fody) weavers, applied to
the SV factory.

```systemverilog
class tx extends uvm_sequence_item;    // no field macros, no do_copy by hand
  `uvm_object_utils(tx)
  rand bit [7:0]  addr;
  rand bit [31:0] data;
  ...
endclass

t = tx::type_id::create("t");          // the factory returns a Woven_tx__release
u.copy(t);                             // reaches the generated do_copy()
```

## Features

- **sv-weave is the generator.** It ships no SV runtime and no binding. A **binding**
  adapts it to one library: which base classes it claims, which virtual hooks the
  features map onto, and how woven classes register with the library's factory. The
  UVM binding belongs in the separate `sv-weave-uvm` library; `examples/uvm/` and
  `examples/reflib/` show how bindings work.
- **Weavers** decide what to generate. Built in: `copy`, `compare`, `print`, and
  `xcheck` (a debug X-check). Weavers can also query the whole
  design and generate code about sets of classes (`examples/selector/`).
- **Profiles** (release, debug, ...) generated side by side and chosen through the
  library's factory. Debug-only extension sets are checked so that they cannot change
  randomisation.
- **Verification:** the generated code is elaborated with the design by pyslang
  before anything is written, and errors point at the weaver that produced the line.
- **dv-flow-mgr task** `svweave.Weave`, a CLI, a manifest and a report of what was
  woven.

## Getting started

- Quickstart: `docs/quickstart.rst` (example in `examples/quickstart/`).
- Build the docs: `python -m sphinx -b html docs docs/_build`.
- CLI: `sv-weave gen`, `sv-weave list`, `sv-weave report`, `sv-weave schema`.

## Status

Early development (0.0.x). The core weavers work end to end on Verilator 5.054, with
the example reference library and with the example UVM binding on Verilator's UVM. Design: `docs/design/initial-design.md`. Plan and status:
`docs/plan/implementation-plan.md`.

## Development

```
ivpm update                      # dependencies into packages/
uv pip install --python packages/python/bin/python --no-deps -e .
packages/python/bin/python -m pytest              # unit, golden, Verilator sims, docs
packages/python/bin/python -m pytest -m perf -s   # timing measurements
```

## License

Apache-2.0
