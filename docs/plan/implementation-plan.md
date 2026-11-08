# sv-weave: implementation, test and documentation plan

Design: `docs/design/initial-design.md`. Section numbers (§) below refer to that document.
This file holds both the plan and its running status. Update the status table as each
step finishes, so that a fresh session can pick up from this file alone.

## Status

| Phase | State | Note |
|---|---|---|
| P0 Skeleton and toolchain smoke | done | 7 tests green; Verilator 5.054 smoke passes. See P0 notes. |
| P1 Front end and model | done | 83 unit tests; `sv-weave list` works. See P1 notes. |
| P2 Weave core and render | done | 123 tests incl. 4 golden cases; `sv-weave gen`/`report`. See P2 notes. |
| P3 Runtime, plain binding, dfm tasks | done | 6 Verilator sims pass; D2 evidence recorded; xezim blocked by an xezim bug. See P3 notes. |
| P4 Verify | done | full/syntax/off, rand-safety rules, cache; D9 measured: `full` is cheap. See P4 notes. |
| P5 Core weavers | done | copy, compare, print, method-order; 5 Verilator sims. See P5 notes. |
| P6 Extension sets and profiles | done | Dedupe, runtime selection, `+weave_report`, `xcheck`; seed reproducible across profiles. See P6 notes. |
| P7 Design-wide queries and selector | done (revised) | `on_design`, `DesignCtx` in the core; selector and its registry moved to `examples/selector/` after review. See P7 notes. |
| P8 Docs and report polish | done | Generated config and dfm references, glossary, README, report summary. See P8 notes. |
| P9+ UVM binding, fw binding | later | Outline only |

**Next action:** restructure R is done. Next: user review, then sv-weave-uvm
(the UVM binding as its own library, starting from `examples/uvm/`).

### Placement within sections (user direction, 2026-11-08): done

"We'll need to express relationships: also (append), first (prepend). This generator's
content must come before or after another generator's."
- `Contributions.add(text, first=, before=, after=)`, plus `append` and `prepend`
  (`weave/model.py`). A stable topological sort runs over (band, contributor) nodes:
  `first` before append; dispatch order within a band (reversed in `post`);
  `before`/`after` constraints are textual in every section and override band and
  default order.
- Relationships per fragment, per weaver (`Weaver.before`/`after`), or per config
  entry (`before:`/`after:`). Contradictions are a Check error naming the weavers.
- Tests: `tests/unit/test_placement.py` (8). Docs: `authoring/weavers.rst`,
  `user/config.rst`; design §6.3 updated.

### Restructure R (user direction, 2026-11-08)

"Too much in the base. Making this work depends on having virtual APIs defined by the
library base class that can be implemented." "The UVM bindings really belong in an
independent library, sv-weave-uvm. For now, use UVM extension generators as examples."

| Step | Work | State |
|---|---|---|
| R1 | **Core ships no SV runtime and no binding.** Remove `share/sv/sv_weave_pkg.sv`, the built-in `plain` binding and `rt-path`. Woven packages import only the user package and the binding's imports. `__register()` holds only binding statements. The init package calls `sv_weave_init()` from `sv_weave_init_m`'s static initialiser (no hook). `binding:` becomes required. | done |
| R2 | **Reference library as an example:** `examples/reflib/` holds `reflib_pkg.sv` (the old runtime, renamed `ref_*`: a minimal library whose base class `ref_object` declares virtual hooks, plus a small factory with profiles) and `reflib_binding.py`. Tests and the quickstart use it. | done |
| R3 | **UVM as an example:** `examples/uvm/uvm_binding.py`. Features map onto `uvm_object`'s virtual hooks (`do_copy`, `do_compare`, `convert2string`); woven classes register with `uvm_factory` as type overrides, chosen per profile by plusarg. Sims on Verilator's bundled UVM. The real binding goes to `sv-weave-uvm`. | done |
| R4 | Docs, design and plan updated to match. | done |

**R notes (done 2026-11-08)**
- **Core:** `bindings.BUILTIN` and `share/` are empty, and `binding:` is required (an
  error if missing). Woven packages import the user package plus the binding's
  `imports()`. New `Binding.preamble()` (file-level lines, e.g.
  `` `include "uvm_macros.svh" ``). `__register()` holds only binding statements.
  `sv_weave_init_m` calls `sv_weave_init()` from a static initialiser (no hook).
  `rt-path` is removed; `-b/--binding` was added to the CLI. `svweave.Runtime`
  outputs only what bindings declare in `sv_runtime_files()`.
- **Field boundary:** `WeaveCtx.fields()` stops at the first ancestor outside the
  selected packages, or at the binding root. Found with UVM: walking to `uvm_object`
  copied and printed UVM's own fields (`begin_event`, `m_sequencer`, ...). The
  built-in weavers use it.
- **Rand-safety rules:** tokens from macro expansions now count at the line of the
  macro use; tokens outside the woven file are ignored. Without this, UVM macro
  bodies would have been attributed to woven fragments.
- **`examples/reflib/`:** the old runtime renamed `ref_*`, plus `reflib_binding.py`.
  The tests register it in-process as `reflib` (`tests/conftest.py`). The quickstart
  uses it through `plugin-path`. The golden changes were renames only.
- **`examples/uvm/uvm_binding.py`:** `do_copy`, `do_compare`, `convert2string`;
  `` `uvm_object_utils `` on woven classes; `uvm_factory` type overrides per
  `+weave_profile` with `replace=0`. `tests/sim/test_uvm_example.py` passes on
  Verilator's UVM (SimLibUVM → Weave → SimImage), including a user override
  resolving to its woven class.
- **Suite:** 207 passed and 3 xfailed (xezim).

**Open questions for the user** (decisions taken during implementation)
1. **Resolved:** design-wide queries are a capability generators need (confirmed).
2. **Resolved:** "calling recognised methods in order" (handoff) means ordering and
   grouping contributions within a generated method, which `MethodSlot`
   (decl/pre/post) already does. The `method-order` weaver was a misreading and has
   been removed.
3. **Resolved:** no parallel type registry in sv-weave; work with the library's
   registry (e.g. `uvm_factory`). The selector moved to `examples/selector/`.
3a. **Resolved:** restructure R (core = generator; bindings work with the library).
3b. **Resolved:** the UVM example now uses a factory subclass,
   `examples/uvm/sv_weave_uvm_pkg.sv`. It overrides `find_override_by_type` and
   `find_override_by_name` (virtual in UVM 1800.2-2020): `super` resolves the user's
   overrides, then the woven class of the resolved type is substituted for the
   active profile. No `set_type_override` calls. Tested with type and instance
   overrides set after registration.
   The woven map is keyed by the resolved type's `uvm_object_wrapper`, not its name
   (user review: "overrides should be by type"). The test also covers a different
   class registered under the same UVM type name.
4. D2: keep explicit as the default, with static as the zero-touch option (evidence:
   `docs/design/notes/registration-trigger.md`).
5. D9: keep `full` as the default (evidence: `docs/design/notes/verify-cost.md`).
6. xezim 0.11.3 has a parameterised-class specialisation bug that blocks it
   (reproducer: `docs/design/notes/repro/xezim_param_spec.sv`). It should be reported
   upstream.
7. Profile fallback ends at the config default, not a fixed `release` (P6 notes).

### Assumptions this plan makes

The design's pending decisions are taken as proposed. If any is overridden, update
this list and the affected phases.
- **D2:** explicit registration through an init hook, static as opt-in. P3 evidence
  supports this: `docs/design/notes/registration-trigger.md`.
- **D3:** a profile is the runtime unit.
- **D4:** flatten fields into each woven class.
- **D5:** one repo for now.
- **D6:** `Woven_<C>[_<hash>]__<profile>` naming.
- **D8:** the plain binding first; fw comes after.
- **D9:** `full` verification with caching. P4 measured it at 0.27 s on a UVM env,
  less than Load: `docs/design/notes/verify-cost.md`.
- **Not decided yet:** D7 (where the fw pieces live) is not needed before P9.

---

## Conventions (all phases)

**Python**
- Package `sv_weave` under `src/`, Python ≥ 3.10, dataclasses for the model.
- pydantic v2 for the config schema; its JSON Schema also feeds the docs.
- The public API is re-exported from `sv_weave.api` and carries `API_VERSION`. Anything
  that is not re-exported is internal.
- Deterministic output: sort everything that gets emitted, and never write timestamps.

**SV**
- Runtime package `sv_weave_pkg`, in `src/sv_weave/share/sv/sv_weave_pkg.sv`.
- Generated packages are `<P>_woven` and `sv_weave_init_pkg`. The init module is
  `sv_weave_init_m`.

**Logs**
- Build and sim logs go to files under the test rundir, not to the terminal.
- When a test fails, its message includes the log path plus the matching error lines.

**Commits**
- The user commits and pushes. Each step below ends at a point where the code is
  green and could be committed.

---

## Test strategy

Five layers, chosen with pytest markers (`pyproject.toml` `[tool.pytest.ini_options]`):

| Layer | Marker | What | Tools | Where |
|---|---|---|---|---|
| Unit | (none) | Model, match, config, slots, render, helpers, and every pure function | pytest; pyslang `SyntaxTree.fromText` on inline SV | `tests/unit/` |
| Golden | (none) | Rendered `<P>_woven.sv` for fixture designs, compared with checked-in files | pytest; `--update-golden` option in `conftest.py` | `tests/golden/<case>/{in/*.sv, sv-weave.yaml, expect/*.sv}` |
| Verify | (none) | The Verify stage on good and bad woven code: elaboration errors, rand-safety violations, diagnostics mapped back to the contribution | pytest + pyslang | `tests/unit/verify/` |
| Sim | `sim` | End-to-end: weave, compile and run on Verilator; the SV testbench checks itself | **pytest-dfm** `dvflow` fixture → `svweave.Runtime` / `svweave.Weave` → `hdlsim.vlt.SimImage` → `hdlsim.vlt.SimRun` | `tests/sim/<case>/` |
| Perf | `perf` | Load and Verify timings on a small fixture and on a full UVM testbench (D9) | pytest, timing only, no sim | `tests/perf/` |

- **Fast loop:** `pytest -m "not sim and not perf"`.
- **Full run:** `pytest`. Perf runs only on request with `-m perf`.

### Sim test pattern (pytest-dfm with Verilator)

```python
# tests/sim/conftest.py provides: weave_sim(dvflow, case_dir, top="tb", plusargs=(), config="sv-weave.yaml")
def weave_sim(dvflow, case_dir, top="tb", plusargs=(), config="sv-weave.yaml"):
    src   = dvflow.mkTask("std.FileSet", name="src", type="systemVerilogSource",
                          base=case_dir, include="*.sv")
    rt    = dvflow.mkTask("svweave.Runtime", name="rt")
    woven = dvflow.mkTask("svweave.Weave", name="woven", needs=[src],
                          config=os.path.join(case_dir, config))
    img   = dvflow.mkTask("hdlsim.vlt.SimImage", name="img", top=[top],
                          needs=[rt, src, woven])
    run   = dvflow.mkTask("hdlsim.vlt.SimRun", name="run", needs=[img],
                          plusargs=list(plusargs))
    status, out = dvflow.runTask(run)
    return SimResult(status, out, log=find_sim_log(out))   # helper parses the log

def test_factory_returns_woven(dvflow):
    r = weave_sim(dvflow, data("factory_basic"))
    r.assert_pass()          # status == 0, "SV_WEAVE_TEST: PASS" seen, no "FAIL"/$fatal
```

- **Testbench convention:** every sim case has a `tb` module that prints
  `SV_WEAVE_TEST: PASS` at the end, and calls `$fatal(1, "SV_WEAVE_TEST: FAIL ...")` on
  any check that fails. `tests/sim/sv/check_pkg.sv` provides `` `CHECK_EQ `` style
  helpers.
- **Package registration:** `svweave` is registered through its entry point
  (an editable install). If the entry point is not visible in a test,
  `dvflow.addPackage("svweave", <flow.dv>)` is the fallback.
- **Simulators:** sim tests target Verilator only. xezim is used only for the D2
  registration-trigger comparison, with tests marked `xezim` and skipped when xezim is
  not on the path.

### Doc strategy

- **Product docs:** Sphinx in `docs/` (`sphinx-dv-flow` and `sphinx-jsonschema` are
  already in `packages/`). Design and plan notes stay Markdown under `docs/design/` and
  `docs/plan/`.
- **Each phase ends with its doc step.** The docs grow alongside the code, and P8 only
  ties them together and polishes them.
- **Doc build:** `sphinx-build -W -b html docs docs/_build`, run as a test
  (`tests/docs/test_docs_build.py`, marker `docs`), so a warning fails the build.

Doc tree:

```
docs/
  index.rst
  overview.rst            # what weaving is, the factory precondition, pipeline picture
  quickstart.rst          # plain-binding example end to end (P3)
  concepts.rst            # targets, bindings, features, weavers, sets, profiles (P2/P6)
  user/
    config.rst            # sv-weave.yaml reference, generated from pydantic JSON Schema
    attributes.rst        # (* weave_off *), weave_nocopy, weave_deep, weave_weight (P5/P7)
    profiles.rst          # compile-time vs runtime selection, plusargs (P6)
    report.rst            # manifest and report, diagnostics (P2/P4)
    dvflow.rst            # svweave.Runtime / svweave.Weave (sphinx-dv-flow) (P3)
    cli.rst               # sv-weave gen/list/report/rt-path (P1–P3)
  authoring/
    weavers.rst           # Weaver API, WeaveCtx, MethodSlot, w.sv, on_design (P2/P5/P7)
    bindings.rst          # Binding API, features, registration, runtime files (P3)
    verify-rules.rst      # what Verify enforces per set (P4)
  reference/
    api.rst               # autodoc of sv_weave.api
    sv-runtime.rst        # sv_weave_pkg classes and functions (P3/P7)
  design/                 # existing Markdown design notes, linked from index
```

---

## P0: Skeleton and toolchain smoke

**Goal:** an installable package, a pytest setup, and evidence that pytest-dfm can drive
Verilator on SV class code.

| Step | Work | Files |
|---|---|---|
| P0.1 | Add `pyproject.toml`: name `sv-weave`, setuptools with `src/` layout, deps `pyslang>=12.1`, `pydantic>=2`, `pyyaml`. Extras `[dev]`: `pytest`, `pytest-dfm`, `dv-flow-mgr`, `dv-flow-libhdlsim`. Entry points `console_scripts: sv-weave`, `dv_flow.mgr: svweave = sv_weave.dfm.__ext__`, and the groups `sv_weave.weavers` / `sv_weave.bindings`, left empty for now. Package-data `**/*.sv`, `**/flow.dv`. | `pyproject.toml`, `src/sv_weave/__init__.py`, `__version__.py`, `api.py` |
| P0.2 | Update `ivpm.yaml`: add `pyyaml` and `pydantic` (pypi) to `use`, and `pytest` to `dev`. Install `sv-weave` editable into `packages/python`. Check that `pytest-dfm` and `dv-flow-libhdlsim` come from `sim-rtl-tools` and add them if they do not. | `ivpm.yaml` |
| P0.3 | `tests/conftest.py`: markers, the `--update-golden` option, and `data()` path helpers. | `tests/conftest.py` |
| P0.4 | **Toolchain smoke (sim).** A hand-written SV file with a class, a subclass, a virtual method, a parameterised class, `$cast` and a static class member initialiser, run with `std.FileSet → hdlsim.vlt.SimImage → SimRun` through `dvflow`. Record the Verilator version and flags in the test docstring. | `tests/sim/smoke/{tb.sv}`, `tests/sim/test_smoke.py`, `tests/sim/conftest.py` (`weave_sim` starts without the svweave tasks), `tests/sim/sv/check_pkg.sv` |
| P0.5 | Docs skeleton: `docs/conf.py`, `index.rst`, `overview.rst`; `test_docs_build.py`. | `docs/` |

**Exit:** `pytest` passes and the smoke sim prints PASS on Verilator.

**P0 notes (done 2026-11-08)**
- Installed editable with `uv pip install --python packages/python/bin/python --no-deps -e .`
  (the ivpm venv has no pip). Rerun this after `ivpm update`.
- pytest-dfm has no `pytest11` entry point, so `tests/conftest.py` sets
  `pytest_plugins = ["pytest_dfm"]`.
- A failed `SimRun` emits no `simRunDir` output; `run_sim` falls back to
  `<tmpdir>/run/sim.log`. `test_harness_detects_fail` proves that a failing check is caught.
- The `svweave` dfm package is registered with an empty task list until P3.
- Sphinx: `docs/design/` and `docs/plan/` are excluded from the build (there is no
  myst-parser in the env). The product docs link to them in text only.
- Run everything: `packages/python/bin/python -m pytest` (about 6 s).

---

## P1: Front end and model (§4, §5)

**Goal:** `sv-weave list` shows the target classes of a design, with correct
inheritance, members and specialisations.

| Step | Work | Files |
|---|---|---|
| P1.1 | **Config:** a pydantic model for `sv-weave.yaml` (§9) and its loader. Expand filelists with `-f`, `+incdir+` and `+define+`, resolving paths relative to the file. Errors are reported with a file and line. | `config.py`, `filelist.py` |
| P1.2 | **Loader:** `load(sources) -> Loaded(compilation, trees, source_manager)`. Fail on any diagnostic of error severity, formatted as `file:line:col: msg`. | `frontend/loader.py`, `diag.py` |
| P1.3 | **SvType:** convert slang types to `SvType`: category, width and sign, element type, the class reference, and the SV spelling qualified for use from another package. | `frontend/types.py` |
| P1.4 | **Model:** `SvModel`, `SvPackage`, `SvClass`, `SvField`, `SvMethod`, `SvArg`, `SrcLoc`, plus attributes read through `getAttributes`. Ancestor walk, `all_fields(upto)` and `find_method`. | `frontend/model.py` |
| P1.5 | **Specialisations:** a design-wide visitor collects `ClassType` objects with `genericClass` set and dedupes them by parameter values. Stable short hash. Check what the visitor sees in package scope, class members, subroutine locals, typedefs, `extends` clauses and nested specialisations. | `frontend/specialize.py` |
| P1.6 | **Match predicates:** `extends`, `implements`, `has_method`, `has_attr`, `has_field`, `in_package`, `&`, `\|`, `~`, and a small string parser for config rules. | `match.py` |
| P1.7 | **Selection:** package filter, then binding roots (a stub binding interface for now), then `weave_off`, giving the list of targets. Design-wide queries (`subclasses_of`, `implementors_of`, `classes`) go on `SvModel` here, because P7 builds on them. | `select.py`, `frontend/model.py` |
| P1.8 | **CLI:** `sv-weave list --targets` (with `--json`). | `cli.py` |
| P1.9 | **Docs:** `user/cli.rst` (list), the start of `concepts.rst`. | `docs/` |

**Tests (unit, inline SV):**
- **Inheritance:** a 3-level chain, classes across packages, an extern base from a
  stub `uvm_pkg`.
- **Members:** `rand` and `randc`, static, `local` and `protected` fields; virtual,
  pure, static and non-virtual methods; argument directions and default values; tasks
  versus functions.
- **Interfaces:** interface classes and `implements`.
- **Attributes** on classes and fields.
- **Specialisations:** of `A#(W)` used in two widths and with a type parameter; a
  specialisation used only in `extends`; nested `A#(B#(8))`.
- **Queries:** `subclasses_of(concrete=True)` excludes abstract classes and includes
  specialisations.
- **Predicates:** each predicate, and the string parser, including a round trip and
  errors.
- **Config:** validation errors, filelist expansion, and the error on a bad source.

**P1 notes (done 2026-11-08)**
- Code: `config.py`, `filelist.py`, `diag.py`, `frontend/{loader,types,model,specialize}.py`,
  `match.py`, `select.py`, `cli.py` (`list`). pyslang findings and specialisation
  coverage are in `docs/design/notes/specialisations.md`.
- **Selection uses a stub binding:** `select.StubBinding`, with `BUILTIN_ROOTS`
  `{"plain": ["sv_weave_pkg::weave_object"]}`. P2.1 replaces it with real `Binding`
  plugins, which have the same `name`/`roots` shape.
- `share/sv/sv_weave_pkg.sv` holds only `weave_object` so far; P3 fills it in. The CLI
  adds the runtime ahead of user sources (`--no-runtime` turns this off).
- **Model choices:**
  - `extends(N)` is strict (N itself does not match); `is_a(N)` includes N.
  - A generic class name matches all its specialisations.
  - `SvClass.qname` of a specialisation is its SV spelling, e.g. `p::G#(16, int)`.
  - `$unit` classes are modelled but never targets.
- **Config:** cross-reference errors (unknown set or profile) are reported at the
  offending key's line.

**Risk to watch:** the pyslang 12.1 stubs do not list specialisations. If the P1.5
visitor misses cases, record them in `docs/design/notes/specialisations.md` as known
limits, and add a diagnostic for specialisations created by the factory that have no
woven subclass.

---

## P2: Weave core and render (§6.1–6.5, §7.1–7.2, §7.4)

**Goal:** weavers contribute to slots, and the framework renders deterministic
`<P>_woven.sv`, a manifest and a report. Bindings and the runtime are still stubs here.

| Step | Work | Files |
|---|---|---|
| P2.1 | **Plugin system:** `Weaver`/`Binding` base classes, entry-point discovery, an `api` range check against `API_VERSION`, and in-process registration for tests (`register_weaver(cls)`). | `plugin.py`, `api.py` |
| P2.2 | **Bus:** `on(predicate, handler)`. Dispatch order: binding `prepare`, then weavers (config `order`, then name), then binding `finalize`. One run per (target, profile), limited to the sets that profile includes. A single `release=[core]` profile until P6. | `bus.py` |
| P2.3 | **Woven model:** `WovenPackage`, `WovenClass`, `MethodSlot` (`decl`/`pre`/`post`/`body`/`replace_super`), `FieldDecl`, `ClassItem`, and `SvFragment(text, origin)`. `origin` captures the weaver, the set and the caller's file and line through `inspect`. | `weave/model.py`, `weave/slot.py` |
| P2.4 | **WeaveCtx:** `feature`, `override` (signature copied from `SvMethod`), `add_method`, `add_field`, `add_item`, `add_registration`, `diag`. | `weave/ctx.py`, `weave/builder.py` |
| P2.5 | **`w.sv` helpers:** `fresh`, `type_of`, `cast_rhs`. The field helpers come in P5. | `weave/svhelpers.py` |
| P2.6 | **Check (model level):** the overridden method must be virtual (§6.3); `replace_super` conflicts; a pure method left unimplemented in a class that is to be registered; reaching a `local` field (a helper reports it). | `check.py` |
| P2.7 | **Render:** packages, imports, classes, slot skeletons (§6.3 ordering: `pre` in contributor order, `post` in reverse), re-indented fragments, `endfunction : name` labels, and a line map from woven line to origin. | `render.py` |
| P2.8 | **Write:** only rewrite files whose content changed. `sv_weave.f` in compile order. `weave-manifest.json` with a schema version, plus the input and output hashes. `weave-report.md`. | `write.py`, `report.py` |
| P2.9 | **Wiring:** `run(config) -> RunResult`; `sv-weave gen`; `sv-weave report`. | `run.py`, `cli.py` |
| P2.10 | **Docs:** `authoring/weavers.rst` (bus, ctx, slots, fragments), `user/report.rst`, `concepts.rst`. | `docs/` |

**Tests:**
- **Unit:** slot composition order; `replace_super` exclusivity; a non-virtual override
  is diagnosed at the user's source line; fragment re-indentation; `fresh` avoids user
  member names; the plugin `api` range is rejected cleanly; dispatch order is
  deterministic across runs (hash of output).
- **Golden:**
  - `golden/override_one/`: a test weaver adds `pre`/`post` to `build()`;
  - `golden/two_weavers_same_slot/`;
  - `golden/two_packages/`;
  - `golden/specialized/`: the `A#(8)` and `A#(16)` woven names and the report
    mapping.
  - Every golden output is also parsed by pyslang in the test, so it at least parses
    before P4 exists.

**P2 notes (done 2026-11-08)**
- Code: `plugin.py`, `api_version.py`, `bus.py`, `weave/{model,ctx,svhelpers}.py`,
  `check.py`, `render.py`, `write.py`, `report.py`, `run.py`, `bindings/plain.py`
  (roots and features only), `cli.py` (`gen`, `report`). Test weavers:
  `tests/test_weavers.py`, registered by the `test_weavers` fixture.
- **Two filelists instead of one** (design §7.4 updated): `sv_weave_rt.f` goes before
  the user's sources, `sv_weave.f` (woven, then init) after them.
- **Empty woven classes are not emitted.** A (target, profile) pair that no weaver
  contributed to gets no woven class; the runtime falls back as §8.1 says.
- **Return values:** a non-void slot always declares `slot.ret_var`. It holds super's
  result when super is called; contributors can assign it or call `set_result()`.
- **Features:** if the target's ancestry has no method for a feature, the slot
  introduces it without a `super` call. The plain features (`copy`, `compare`,
  `sprint`) become real overrides once P3 adds them to `weave_object`, which will
  change the golden files (expected; regenerate with `--update-golden`).
- **Constructors:** the woven class forwards the nearest user constructor's arguments,
  defaults included. Implicit conversions hide default-value syntax in pyslang; the
  model unwraps them.
- **Deferred:** deduplication of identical woven classes across profiles goes to
  P6.1. Verify is reported as "not implemented" in the manifest until P4.
- Golden tests also elaborate their output with pyslang, as the plan asked.

---

## P3: Runtime, plain binding and dfm tasks (§8, §11): first end-to-end on Verilator

**Goal:** `weave_factory#(A)::create()` returns the woven class in a Verilator run,
driven from pytest through pytest-dfm.

| Step | Work | Files |
|---|---|---|
| P3.1 | **`sv_weave_pkg`:** `weave_creator`, `weave_impl#(T)`, `weave_type#(T)`, `weave_registry`, `weave_profiles` (plusarg parsing, glob match on type and instance), `weave_factory#(T)`, `weave_initializer` and `weave_init_hook`. Verilator lint clean (`--lint-only -Wall`). | `share/sv/sv_weave_pkg.sv` |
| P3.2 | **Plain binding:** root `weave_object` (in `sv_weave_pkg`); features `copy`, `compare`, `print` mapped to `copy(weave_object)` and so on; the create signature; registration rendering (`__register()` per package); `sv_weave_init_pkg` plus `sv_weave_init_m`. `registration: static` emits the holder-class static initialiser instead. | `bindings/plain.py`, `share/sv/` |
| P3.3 | **dfm package `svweave`:** `flow.dv` with `Runtime` and `Weave`. `Weave` is a pytask: inputs are the upstream `systemVerilogSource` FileSets in order; it calls `run()` and produces a FileSet of woven and init sources in compile order, plus a `jsonManifest` FileSet. `changed=False` when the manifest hashes are unchanged. Markers carry the diagnostics with their locations. | `dfm/__ext__.py`, `dfm/flow.dv`, `dfm/tasks.py` |
| P3.4 | **`sv-weave rt-path`.** | `cli.py` |
| P3.5 | **Docs:** `quickstart.rst` (the plain example end to end, with both CLI and dfm), `user/dvflow.rst`, `authoring/bindings.rst`, `reference/sv-runtime.rst`. | `docs/` |

**Sim tests (Verilator, pytest-dfm):**
- `sim/factory_basic`: creating `A` gives `Woven_A__release` (check with `$typename`, and
  that the woven override ran).
- `sim/factory_unwoven_fallback`: a type with no contributions gives a plain `T::new()`.
- `sim/override_forwarding`: the user overrides A → MyA through the plain factory's
  override API, and gets `Woven_MyA` (this tests the handoff's override decision).
- `sim/registration_explicit` and `sim/registration_static`: both register on Verilator.
  The result is written to `docs/design/notes/registration-trigger.md` (risk 2, D2). The
  same cases marked `xezim` run there when xezim is available.
- `sim/incremental`: a second `Weave` run with unchanged inputs reports
  `changed=False`, and the files' mtimes do not change.

**Exit:** all of the above pass, and D2 has evidence for Verilator.

**P3 notes (done 2026-11-08)**
- Code: `share/sv/sv_weave_pkg.sv` (Verilator `-Wall` lint clean, apart from two
  marked false positives), `bindings/plain.py` (registration, `weave_impl_name()`
  override, no-argument `new()` check), `render.render_init` (`sv_weave_init.sv`),
  `dfm/{flow.dv,tasks.py}`, `cli.py` (`rt-path`). Example: `examples/quickstart/`, run
  by `tests/sim/test_examples.py`.
- **Weave needs `consumes: all`.** With `consumes: none`, dv-flow does not hand the
  task its inputs. `passthrough: all` still forwards them, ahead of the woven
  FileSets, so `SimImage` needs only `[rt, woven]`.
- **Load-time init stub.** A testbench may instantiate `sv_weave_init_m` or call
  `sv_weave_init_pkg::sv_weave_init()` before anything is generated. `run()` loads an
  in-memory stub of `sv_weave_init.sv` unless the sources already contain one.
- **Default profile priority** is `+weave_profile`, then `set_default()`, then the
  config default (set by `__register()` through `set_config_default`). Several
  `+weave_impl` rules go in one comma-separated plusarg. Design §8.1 is updated.
- **`weave_creator.type_name()`** was added. `weave_object` declares the plain
  features (`copy`, `compare`, `sprint`) and `weave_impl_name()`.
- **Weavers by `module:Class`** in the config, imported from the config's directory,
  so a quickstart does not need a packaged plugin.
- **Report:** the "Not woven" table leaves out classes in unselected packages (UVM,
  sv-weave's own); the manifest still lists them.
- **D2 evidence** (`docs/design/notes/registration-trigger.md`):
  - Verilator: all three registration paths work.
  - xezim 0.11.3: both triggers fire (the unreferenced-class initialiser runs twice,
    which the `__register` guard makes harmless), but an xezim bug gives
    `P#(a_pkg::A)` and `P#(A)` separate static storage, so the factory never finds
    the woven class. Reproducer: `docs/design/notes/repro/xezim_param_spec.sv`.
  - The xezim tests are `xfail(strict=True)`.
- Sim tests run in about 15 s.

---

## P4: Verify (§7.3, §6.6)

| Step | Work | Files |
|---|---|---|
| P4.1 | `full`: re-elaborate the user trees (reused) plus the runtime and the woven buffers built from text. Map diagnostics in woven buffers back to their origin through the line map. | `verify.py` |
| P4.2 | `syntax`: parse the woven buffers alone. | `verify.py` |
| P4.3 | Rand-safety rules on the syntax tree, scoped to each fragment's set through the line map. The flags are `allow_rand`, `allow_state`, `allow_alloc` and `allow_threads`. | `verify_rules.py` |
| P4.4 | Structural checks under `full`: woven methods override virtuals with matching signatures; registered classes are concrete; constructors match the binding's `create`. | `verify.py` |
| P4.5 | Cache: skip when both hashes match the last `full` pass, recorded in the manifest. `.failed/` output when verification fails. `--verify=` and the config key. | `verify.py`, `run.py` |
| P4.6 | **Perf (D9):** time Load and Verify on (a) a small fixture and (b) a UVM testbench made of the bundled UVM sources (from xezim's bundled UVM or the libhdlsim tarball) plus a small env. Write `docs/design/notes/verify-cost.md` and propose the D9 default. | `tests/perf/` |
| P4.7 | **Docs:** `authoring/verify-rules.rst`, and the levels in `user/config.rst`. | `docs/` |

**Tests:**
- **Verify:** each rule has a fragment that violates it and one that does not, in
  `core` versus `debug`. An elaboration error in a fragment is reported at the
  weaver's call site. The `syntax` level catches rule violations but not type errors.
  A cache hit skips the work.
- **Golden:** every golden case also runs `full` verification.

**P4 notes (done 2026-11-08)**
- Code: `verify.py`, `verify_rules.py`, wired into `run.py`. `--verify` on
  `sv-weave gen`; `verify` parameter on `svweave.Weave`. Tests:
  `tests/unit/verify/test_verify.py` (40 cases), `tests/perf/test_verify_cost.py`.
- **Verify found a real bug immediately:** a woven subclass of an abstract class that
  leaves a pure method unimplemented must be declared `virtual class`. Render does
  that now.
- **`full`** reuses the user's syntax trees from Load. It swaps the Load-time init
  stub for the real `sv_weave_init.sv`, and maps errors in woven buffers to the
  contributing weaver's call site, with the woven file and line in the message.
- **Rand-safety rules** run at both levels, on tokens plus `ClassPropertyDeclaration`
  nodes. A `rand` property trips both `allow_rand` and `allow_state`.
- **`core` defaults to all flags on**, as design §6.6 says; other sets default to
  off. The config validator fills this in from `model_fields_set`.
- **YAML reads a bare `off` as false**; `verify` accepts booleans.
- **Cache:** the manifest's `verified` holds level and hashes. On a cache hit the
  manifest still says `verify: full`, so it is byte-identical between runs; only the
  CLI reports `cached`. A cache hit skips any level.
- **Failure:** nothing in `out_dir` changes; the output goes to `.failed/`, which the
  next good run removes.
- **D9:** `docs/design/notes/verify-cost.md`. Model building (0.69 s, every UVM class
  modelled) is the largest stage on UVM; lazy modelling of unselected packages is a
  later optimisation.

---

## P5: Core weavers (§6.4, §7.2)

| Step | Work | Files |
|---|---|---|
| P5.1 | `w.sv` field helpers: `copy_field`, `compare_field`, `print_field`, covering every `SvType` category: scalar, enum, string, real, class handle (shallow, or deep when `weave_deep`), fixed, dynamic, queue and associative arrays, and arrays of class handles. | `weave/svhelpers.py` |
| P5.2 | `copy` weaver, flattening to the binding root, honouring `weave_nocopy`; local fields give a warning, or an error when `strict`. | `weavers/copy.py` |
| P5.3 | `compare` weaver: field-wise, first mismatch reported through the binding's report hook; `weave_nocompare`. | `weavers/compare.py` |
| P5.4 | `print` weaver, using the binding's `super_policy`. | `weavers/print.py` |
| P5.5 | `method-order` weaver: calls the recognised methods in their configured order. | `weavers/method_order.py` |
| P5.6 | **Docs:** `user/attributes.rst`, the weaver authoring examples (copy as a worked example). | `docs/` |

**Tests:**
- **Golden:** per weaver, and per field category.
- **Sim:**
  - `sim/copy_hier3`: a 3-level hierarchy across 2 packages. Copy then compare equals;
    mutating a grandparent field makes compare fail.
  - `sim/copy_arrays`: every array kind, plus nested class handles in shallow and deep
    mode.
  - `sim/copy_param`: two specialisations of the same generic class.
  - `sim/print_basic`: compares the output lines in the log.
  - `sim/user_do_copy_coexists`: a hand-written `copy` in a parent is still called
    through `super`.
- **Unit:** a `local` field produces the diagnostic, and `strict` turns it into an
  error.

**P5 notes (done 2026-11-08)**
- Code: `weavers/{copy,compare,print,method_order}.py`, field helpers in
  `weave/svhelpers.py`. Tests: goldens `fields_all` and `method_order`,
  `tests/unit/test_core_weavers.py`, `tests/sim/test_weavers_sim.py` (copy_hier3,
  copy_arrays, copy_param, print_basic, user_do_copy_coexists), with shared sources in
  `tests/sim/lib_tx/`.
- **Binding API additions:**
  - `create_expr(cls)`: deep copies create through the binding's factory, so the
    copy is woven too;
  - `miscompare_stmt(cls, field)`: the plain binding calls
    `sv_weave_pkg::weave_miscompare`, which records `weave_last_miscompare` and
    prints when `+weave_compare_verbose` is given.
- **Compare** reports only the first difference: each check runs only while the
  result is still 1. Deep handles, and arrays of them, compare through the binding's
  `compare`. Unpacked structs are skipped with a warning, because SV cannot compare
  them.
- **Copy** skips events, because assigning one aliases it.
- **`method-order` is my interpretation** of the handoff's "calling recognised
  methods in order". It needs `options.target`, a user virtual method whose woven
  override calls the matched methods (`options.methods`, names or globs) after
  `super`. With no target there is nothing user code could call through a base
  handle. Needs the user's confirmation.
- Dispatch order with no `order` set is by weaver name, so slots come out as
  compare, copy, print.
- **Found in the sims:** a counter that the user's own `copy()` increments gets
  overwritten by the woven copy unless it is `weave_nocopy`. That is the documented
  double-handling behaviour (§6.4) and is now in `user/attributes.rst`.

---

## P6: Extension sets and profiles (§6.6, §8.1, §9)

| Step | Work | Files |
|---|---|---|
| P6.1 | Config: `extension-sets` with flags, `profiles` with set globs, `build-profiles` and `default-profile`. Validate that every weaver's set exists. | `config.py` |
| P6.2 | Bus: run weavers per profile; dedupe identical woven classes across profiles by content hash; register one implementation under several profile names. | `bus.py`, `render.py` |
| P6.3 | Runtime: `+weave_profile=`, `+weave_impl=prof:type[@inst]`, the precedence rules, falling back to `release` then to unwoven; `+weave_report` dumps the resolutions. | `sv_weave_pkg.sv` |
| P6.4 | An example debug weaver, `xcheck`: `$isunknown` checks on integral fields in `post_randomize` and copy, belonging to `debug.xcheck`. It has to pass Verify's rand-safety rules. | `weavers/xcheck.py` |
| P6.5 | **Docs:** `user/profiles.rst`, `concepts.rst` (sets and profiles). | `docs/` |

**Tests:**
- **Sim:**
  - `sim/profile_runtime`: both profiles built; `+weave_profile=debug` selects the
    debug class; `+weave_impl=debug:pkt` affects only that type; an instance glob.
  - `sim/profile_compiletime`: `build-profiles: [release]` means no debug class in the
    output (a grep of the generated file plus a `$typename` check).
  - `sim/debug_seed_repro`: the same seed in release and debug gives the same
    randomised values. **Verilator caveat:** its constrained randomisation support is
    partial. If a needed construct is missing, keep constraints simple, and mark any
    case that needs more as `xezim`.
- **Verify:** an `xcheck` variant that adds a `rand` field is rejected.

**P6 notes (done 2026-11-08)**
- Code: dedupe in `run.py` (`render.content_key`, `WovenClass.also_profiles`);
  `weavers/xcheck.py`; runtime fallback and `+weave_report` in `sv_weave_pkg.sv`;
  `Weaver.order` default. Tests: `tests/sim/test_profiles.py` (profile_runtime with 4
  plusarg runs from one image, profile_compiletime, debug_seed_repro),
  `tests/sim/test_runtime_lint.py`, `tests/unit/test_core_weavers.py`. Shared sources in
  `tests/sim/lib_prof/`. The helper `weave_sim_runs` builds once and runs many times.
- **Dedupe:** a woven class is compared with the earlier profile's by its rendered
  text, with name and profile normalised. Duplicates are dropped and the kept class
  is registered under every profile (`weave_impl` now takes its profile in `new()`).
  It is named after the first profile, so `Woven_A__release` may serve `debug`.
- **Fallback differs from the plan:** active profile, then the default
  (`+weave_profile`/`set_default`), then the *config* default, then unwoven, rather
  than a fixed `release`. Found by profile_compiletime: `+weave_profile=debug` on a
  release-only build used to give unwoven classes.
- **`xcheck`** has `order = -10`, so its `post` checks run after `copy`'s
  assignments (post code runs in reverse contributor order). It adds
  `post_randomize` without `virtual`. Check exempts `pre_randomize`/`post_randomize`
  from the must-be-virtual rule (1800-2017 18.6.2).
- **Seed reproducibility on Verilator:** `obj.srandom()` plus constrained
  `randomize()` worked; release and debug gave identical values over 4 calls. No
  xezim fallback was needed.

---

## P7: Design-wide queries and the selector (§6.7)

| Step | Work | Files |
|---|---|---|
| P7.1 | `bus.on_design`, `DesignCtx`, `add_class`, `feature_of` / `override_of`, aggregate registration. | `bus.py`, `weave/ctx.py` |
| P7.2 | Package placement: aggregate code goes into `<pkg(T)>_woven`, adding the imports it needs; detect cycles and fall back to `sv_weave_gen_pkg`. | `render.py` |
| P7.3 | Runtime: `sv_weave_types#(T)` with `all`, `count` and `create(idx, inst)`. Creation goes through the factory, so overrides and weaving apply. | `sv_weave_pkg.sv` |
| P7.4 | `selector` weaver: `Woven_T::create_any()`, random selection weighted by `weave_weight`, in `core`. | `weavers/selector.py` |
| P7.5 | **Docs:** the `on_design` section in `authoring/weavers.rst`, plus `reference/sv-runtime.rst`. | `docs/` |

**Tests:**
- **Unit:** query results and their ordering; the cycle fallback.
- **Sim:**
  - `sim/selector_basic`: across 1000 draws, every concrete subclass appears at least
    once and abstract ones never do.
  - `sim/selector_weights`: a weight of 0 never appears.
  - `sim/selector_respects_override`: an override on a subclass is honoured.
  - `sim/selector_param`: specialisations are included.

**P7 notes (done 2026-11-08)**
- Code: `weave/design.py` (`DesignCtx`, `Aggregate`, `gen_package_cycles`), three-phase
  dispatch in `bus.py`, aggregate placement in `run.py`, `sv_weave_types#(T)` in the
  runtime, `weavers/selector.py`. Tests: `tests/unit/test_design.py`,
  `tests/sim/test_selector.py` (selector_basic, selector_weights,
  selector_respects_override, selector_param) with shared sources in
  `tests/sim/lib_sel/`.
- **Dispatch is now three phases per profile:** per-class (prepare and weavers), then
  `on_design` handlers, then `finalize` for contributed classes. So a design handler
  can contribute to a woven class, and finalize sees it.
- **Registration moved into the core.** `render.register_items` writes every woven
  package's `__register()` (guard, config default, statements).
  `Binding.package_items` now returns the binding's statements, so aggregate-only
  packages and several bindings work.
- **Design deviation (§6.7 updated):** the weighted pick is
  `sv_weave_types#(T)::create_random()` in the runtime, not a static
  `Woven_T::create_any()`. User code never names woven classes, and the woven code
  draws no random numbers.
- **Selector bases:** classes with `(* weave_select *)`, plus `options.bases` (class or
  generic names). Each entry creates through `binding.create_expr(cls, inst)`, which
  now takes an instance path. Entries need `allow_alloc`, so the selector belongs in
  `core`.
- **When any design handler is configured, every claimed class becomes a target**
  (`Bus.wanted`), so `feature_of` can reach any of them. Only contributed classes are
  emitted.
- **Cycle fallback:** only code that declares `uses_woven` can create woven-to-woven
  imports. Packages in such a cycle move their aggregate code to `sv_weave_gen_pkg`,
  compiled last before init.
- **Weights observed** over 4000 draws: weight 3 about 1490, weight 1 about 500 each,
  weight 0 never.

**P7 revision (2026-11-08, after review)**
- **User direction:** "we don't want to set up a parallel type registry in sv_weave. We
  work *with* the library registry, e.g. `uvm_factory`."
- **What moved:** the `selector` weaver and `sv_weave_types#(T)` are now
  `examples/selector/{selector_weaver.py,select_pkg.sv}` (`select_pkg::select_types`).
  `sv_weave_pkg` no longer has them. The sims and unit tests load the example through
  the new `plugin-path` config key, so `on_design` stays covered end to end.
- **What stayed:** `on_design`, `DesignCtx`, design-wide model queries, aggregate
  placement and the `sv_weave_gen_pkg` fallback.
- **Open question for the user:** the core still has its own implementation map,
  `weave_type#(T)` and `weave_registry` (design §8.1). The plain binding's factory is
  built on it, and the UVM adapter (§8.3) was planned to look up woven classes there
  after `uvm_factory` resolution. The alternative, in line with the direction above,
  is for each binding to register woven classes in the library's own factory (UVM:
  per-profile type overrides or a factory subclass) and to drop the core map. Decide
  before P9.
- **Follow-up direction from the user:** "I feel like you're putting too much in the
  base. Making this work depends on having virtual APIs defined by the library base
  class that can be implemented." Proposed restructuring, awaiting confirmation:
  - The core is generator only: front end, model and queries, selection, bus, slots
    and features, render, verify, write. It ships **no SV runtime**.
  - A binding maps features onto the library base class's virtual APIs (UVM:
    `do_copy`, `do_compare`, `do_print`, `convert2string`, ...) and registers woven
    classes with the library's own factory. Profiles become per-binding registration
    choices (UVM: which woven class overrides which type, by plusarg).
  - `weave_object`, `weave_factory`, `weave_type`, `weave_registry`,
    `weave_profiles` and the init hook leave `sv_weave_pkg`. A minimal reference
    library (base class with virtual hooks, plus a tiny factory) moves to
    `tests/`/`examples/`, as the test fixture for the generator, the way the selector
    did.
  - Next binding to build: UVM (P9), against `uvm_object`'s virtual hooks and
    `uvm_factory`.

---

## P8: Docs and report polish

- Tie the doc tree together: overview, a glossary, and cross-links to the design notes.
- Generate the config reference from the pydantic JSON Schema (`sphinx-jsonschema`) and
  the dfm task reference with `sphinx-dv-flow`.
- `weave-report.md`: a per-target table, per-profile classes, diagnostics, and the
  specialisation hash map.
- README: the pitch (factory weaving, the Fody analogy), a quickstart link, and the
  status.
- Run the docs build test with `-W`.

**P8 notes (done 2026-11-08)**
- **Config reference:** generated from the pydantic model. `config.json_schema()`
  (also `sv-weave schema`) is written to `docs/_generated/` by `docs/conf.py` and
  rendered by `sphinx-jsonschema` (`docs/reference/config-schema.rst`). Field
  descriptions live on the model.
- **dv-flow task reference:** generated by `sphinx-dv-flow` from
  `src/sv_weave/dfm/flow.dv` (`.. dvf:autopackage:: svweave`).
- **Added:** `docs/glossary.rst`, "where to go next" in the overview (with pointers to
  the design notes), the README, and a summary line at the top of the report.
- `.gitignore` gained `docs/_generated/`.
- **Whole suite:** 206 passed and 3 xfailed (xezim) in about 60 s. The docs build
  with `-W` is part of it.

---

## P9+ (outline only, to be planned separately)

**UVM binding**
- First check `uvm_factory.svh` behaviour (risk 4).
- Then `sv_weave_uvm_pkg` with the `weave_uvm_factory` adapter, and features `do_copy`,
  `do_compare`, `do_print`, `do_pack`, `do_unpack`.
- Run on Verilator UVM through `hdlsim.vlt` (libhdlsim has `vlt_sim_lib_uvm`) and on
  xezim.
- Benchmark against `uvm_field_*`.

**fw binding**
- Needs the fw-hdl source and D7.
- The `fw_factory::create` hook, and a weaver that replaces `FW_*_IMP`.

---

## Risks tracked by this plan

| Risk | Where it's tested | Fallback |
|---|---|---|
| Specialisation discovery gaps in pyslang 12.1 (§4.3) | P1.5 unit tests | Document the limits; diagnostic at runtime |
| Static initialiser order on Verilator (risk 2) | P3 `registration_*` | Explicit init is the default anyway |
| Verilator class or randomisation feature gaps | P0.4 smoke, P6 seed test | Simplify the testbench, or mark the case `xezim` |
| Verify cost (D9) | P4.6 | `syntax` default, `full` in CI |
| pytest-dfm package discovery of `svweave` | P3.3 | `dvflow.addPackage` in conftest |
