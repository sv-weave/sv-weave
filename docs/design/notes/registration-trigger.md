# Registration trigger (risk 2, decision D2): evidence

Measured 2026-11-08 in P3 with Verilator 5.054 and xezim 0.11.3 (git 058f2bba).
Design reference: §8.4. Tests: `tests/sim/test_factory.py`.

## Question

Woven implementations register from generated code. Does that code run without the
user doing anything special? Two mechanisms:

- **explicit** (default): `sv_weave_init_m`, instantiated by the testbench, runs
  `sv_weave_init_pkg::install()` from a module-level static initialiser. That installs
  `sv_weave_pkg::weave_init_hook`, and the first factory call runs `sv_weave_init()`.
  Alternatively the testbench calls `sv_weave_init_pkg::sv_weave_init()` itself.
- **static** (`registration: static`): each woven package has a class that nothing
  references, with `static bit m_done = __register_static();`.

## Results

| Mechanism | Verilator 5.054 | xezim 0.11.3 |
|---|---|---|
| Module static initialiser runs before `initial` blocks (`sv_weave_init_m`) | yes (`test_factory_basic`) | yes, once (`repro/static_init_trigger.sv`) |
| Explicit `sv_weave_init()` call | yes (`test_registration_explicit`) | – (blocked, see below) |
| Static initialiser of an unreferenced package class | yes, once (`test_registration_static`) | yes, but **twice** (`repro/static_init_trigger.sv`) |
| End-to-end factory returns the woven class | yes, all three mechanisms | **no**, for any mechanism |

The double run on xezim is harmless: `__register()` is guarded by
`__sv_weave_registered` and does its work once.

## xezim blocker: specialisation chosen by spelling

xezim 0.11.3 picks the specialisation of a parameterised class by how its type
argument is *spelled*, not by the type it resolves to. `weave_type #(a_pkg::A)`
(written by the generated `__register`) and `weave_type #(A)` (reached from the
testbench through `weave_factory #(A)` after `import a_pkg::*`) become two classes
with separate static storage. A typedef alias is split off too. Conversely, two
different classes with the same bare name in different packages share storage.
IEEE 1800-2017 §8.25 requires identical type parameter values to give the same
specialisation.

Minimal reproducer: `repro/xezim_param_spec.sv` (xezim prints `FAIL`, Verilator
`PASS`):

```
xezim --compile -o r.xzb docs/design/notes/repro/xezim_param_spec.sv -s tb && xezim r.xzb
```

There is no robust workaround in the runtime: a key from `$typename` or a `$cast`
search hits the same spelling split. Generating the unqualified spelling would only
move the problem (typedefs, same-named classes in two packages). This should be fixed
in xezim. The xezim sim tests are marked `xfail(strict=True)`, so they will report an
unexpected pass once xezim is fixed.

## Recommendation for D2

- Keep **explicit** as the default. It works on Verilator, and its trigger (a module
  static initialiser) also works on xezim.
- **static** works on Verilator and its trigger fires on xezim. Offer it as the
  zero-touch option, documented as simulator-dependent.
- Re-check xezim when its specialisation bug is fixed. Commercial simulators are not
  available here and remain unmeasured.
