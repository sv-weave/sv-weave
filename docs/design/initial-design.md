# sv-weave: initial design of the generator framework and SV library

Status: **draft for review**, 2026-11-08.
Inputs: `sv-weave-handoff.md` (concept, decisions, risks) and `sv-weave-approach.md` (working notes).
Surveyed: pyslang 12.1.0 and dv-flow-mgr 1.20.0, under `packages/`.

**Principle: independent and pyslang-centric.** sv-weave depends on nothing but
pyslang, plus small utilities such as pyyaml and pydantic. It does not use the Zuspec
IR or backends. slang is the single source of truth:
- it is the front end;
- it is the checker of what sv-weave generates, which it re-parses (§7.3);
- it is the reference for SV semantics.

Any tool downstream, the fw-hdl SV-class → Zuspec synthesis path included, reads the
woven output as ordinary SV.

This document covers:
- the Python generator framework (`sv_weave`);
- the SV runtime library (`sv_weave_pkg`);
- the plugin contracts between them and weaver authors.

Decisions that need an owner are marked **[D#]** and collected in §12.

---

## 1. Goals and non-goals

**Goals**
- Users write plain SV classes against plain base classes. Nothing in their code
  refers to generated code.
- One generator run produces, for each user package `P`:
  - a `P_woven` package of subclasses;
  - the registrations that make the factory hand out those subclasses.
- Weaving is extended through plugins: **weavers** (what to generate) and **bindings**
  (how a given library or factory expects it).
- **Profiles** (release, debug, ...) can be chosen at compile time or at runtime.
- When the weavers say so, the output stays inside the synthesizable class subset, for
  the fw-hdl path. It is plain SV, so no backend gets special treatment.
- Generated code can be checked by slang together with the user's code before sv-weave
  reports success. How much checking runs is configurable (§7.3).

**Non-goals for now**
- Objects built with `new()` (out of scope by definition).
- Weaving modules or interfaces. Only classes are woven.
- Editing user source in place.

---

## 2. Terminology

| Term | Meaning |
|---|---|
| **Target class** | A user class selected for weaving. If it is parameterised, each elaborated specialisation is a separate target. |
| **Woven class** | A generated subclass of a target class: `Woven_<C>__<profile>`. |
| **Binding** | A plugin for one class library or factory (plain, UVM, fw). It says which base classes count as roots, which hook methods exist and what they look like, how to register woven classes, and which runtime adapter to use. Called a "category generator" in the notes. |
| **Feature** | A named contribution point that a binding defines, such as `copy`, `compare`, `print`, `pack` or `post_build`. Each feature maps to one hook method in that library, for example `copy` → `do_copy(uvm_object rhs)` in UVM. |
| **Weaver** | A plugin that subscribes to class patterns and contributes code: either to features, or directly to methods, fields and registrations. Called a "sub-generator" in the notes. |
| **Extension set** | A named group of contributions, such as `core`, `debug.xcheck` or `debug.trace`. Weavers are assigned to sets in the config. |
| **Profile** | A named list of extension sets, such as `release = [core]` or `debug = [core, debug.*]`. This is the unit that gets selected, at build time or at runtime. |

Weavers are not limited to the class they are weaving. Every weaver can query the whole
class model, for example *all concrete subclasses of T*. Design-wide weavers generate
code that spans many classes, such as a class selector. See §6.7.

Splitting **weaver** from **binding** is the main structural choice. A `copy` weaver is
written once and walks fields. The UVM binding turns its output into `do_copy` with a
`$cast`. The fw binding turns it into fw's own copy hook. The plain binding turns it
into a `copy()` method. Weavers never hard-code a library's method signatures.

---

## 3. Pipeline

```
 config (sv-weave.yaml) ─┐
 SV sources / filelist ──┼─► 1 Load    pyslang: SyntaxTree.fromFiles → Compilation
 plugins (entry points) ─┘      │
                                ▼
                         2 Model   SvModel: packages, classes, specialisations,
                                │          fields, methods, attributes (pyslang hidden)
                                ▼
                         3 Select  package filter → binding root match → config rules
                                │          → attribute opt-outs  ⇒ targets
                                ▼
                         4 Weave   event bus: one WovenClassBuilder per (target, profile).
                                │          Bindings declare features, weavers contribute.
                                ▼
                         5 Check   model-level: virtual-hook check, local-field access,
                                │          slot conflicts ⇒ diagnostics
                                ▼
                         6 Render  woven model → SV text (sv-weave's own small emitter;
                                │          bodies are SV fragments from weavers)
                                ▼
                         7 Verify  pyslang re-parses user sources + woven packages:
                                │          must elaborate cleanly; rand-safety rules run
                                │          on the woven AST, per extension set
                                ▼
                         8 Write   P_woven.sv per package, sv_weave_init_{pkg,m}.sv,
                                           weave-manifest.json, weave-report.md
```

Verify is configurable, because its cost is not yet known (§7.3). When it runs, nothing is
written to `out_dir` unless it passes. If it fails, the rendered text
goes to `out_dir/.failed/` so it can be inspected. Diagnostics point at the woven line
*and* at the contribution that produced it (§7.1, §7.3).

Each stage is a plain Python function over plain data, so it can be tested on its own.
The CLI and the dv-flow task are thin wrappers around `sv_weave.run(config)`.

---

## 4. Front end and model (stages 1–2)

### 4.1 Loading
- Sources come from a `-f` filelist, a list in the config, or a dfm FileSet.
- Include dirs and defines pass through to pyslang.
- Parsing uses `pyslang.SyntaxTree.fromFiles`, then `Compilation.addSyntaxTree` and
  `getRoot()`.
- Any error from `getAllDiagnostics()` stops the run. Woven code is only generated
  against source that elaborates cleanly.

### 4.2 `SvModel`: a stable façade over pyslang

The notes worry about handing weavers the raw front end. The design answers that:
weavers see only `sv_weave.model` objects. Each object also has a `.slang` escape hatch,
which is documented as unstable.

```python
@dataclass
class SvClass:
    name: str                 # "A"
    package: str | None       # "foo_pkg"
    qname: str                # "foo_pkg::A"
    type_expr: str            # "foo_pkg::A#(.W(8))": the SV type to extend/name
    base: SvClass | ExternRef | None
    implements: list[SvClassRef]
    is_abstract: bool
    params: dict[str, ParamValue]   # empty unless this is a specialisation
    generic: SvGenericClass | None
    fields: list[SvField]           # declared in *this* class only
    methods: list[SvMethod]         # declared in *this* class only
    attrs: dict[str, object]        # (* weave_* *) attributes
    loc: SrcLoc

    def ancestors(self) -> list["SvClass"]: ...
    def all_fields(self, upto: "SvClass|None" = None) -> list["SvField"]: ...
    def find_method(self, name) -> "SvMethod|None": ...   # nearest, walking up
    def is_a(self, qname) -> bool: ...

@dataclass
class SvField:   name, type: SvType, rand: RandMode, static: bool,
                 visibility: Visibility, attrs, owner: SvClass, loc
@dataclass
class SvMethod:  name, kind: Function|Task, virtual, pure, static,
                 args: list[SvArg], ret: SvType|None, visibility, owner, loc
```

How each piece maps onto pyslang:

| Model item | pyslang source |
|---|---|
| `base` | `ClassType.baseClass` |
| `implements` | `implementedInterfaces` |
| `is_abstract` | `isAbstract` |
| `fields` | `ClassPropertySymbol` members (`randMode`, `lifetime`, `visibility`) |
| `methods` | `SubroutineSymbol` (`subroutineKind`, `flags & MethodFlags.Virtual/Pure/Static`, `arguments[].direction`) |
| `attrs` | `Compilation.getAttributes(sym)` |
| `loc` | `SourceManager.getFileName/getLineNumber` |

`SvType` holds the SV spelling of the type, used when emitting. It also has a coarse
category (`integral(width, signed)`, `enum`, `string`, `real`, `class_handle(SvClass)`,
`array(kind, elem)`, `struct`, `other`), so that field weavers can choose a strategy
without looking at slang types.

### 4.3 Specialisations of parameterised classes

pyslang has no API that lists every specialisation of a generic class. Instead:
1. Visit the whole elaborated design: package and class members, subroutine locals,
   typedefs, base-class clauses, and type parameters of other specialisations.
2. Collect every `ClassType` whose `genericClass` is set.
3. Deduplicate them by `(genericClass, parameter values)`, reading the values from
   each specialisation's `ParameterSymbol` / `TypeParameterSymbol` members.

Each one becomes its own `SvClass`, with `params` filled in and a `type_expr` such as
`A#(.W(8))`. The woven name gets a short stable hash, `Woven_A_p3f9c__debug`, and the
report maps that hash back to the parameter values.

Limitation: a specialisation the design never elaborates gets no woven subclass. If such
a specialisation is created through the factory at runtime, the factory falls back to
the unwoven class and logs a warning (§8.3). This needs a test on each simulator.

---

## 5. Selection (stage 3)

A class is a target if **all** of these hold:
1. Its package passes the config's `packages.include`/`exclude` globs. Library
   packages such as `uvm_pkg` are always excluded.
2. A **binding claims it**: the class is derived from one of the binding's root classes
   (`uvm_object`, `fw_component`, `weave_object`, ...). A class that two bindings claim
   is an error.
3. It is not `(* weave_off *)`.
4. At least one weaver subscription matches it. A class nothing contributes to gets
   no woven class and no registration.

Abstract classes *are* targets. Weaving a concrete subclass of an abstract class is the
Verification Gentleman pattern: the woven class can implement pure virtuals that a
weaver provides. A woven class is only registered if it ends up concrete; the Check
stage reports any pure method still left unimplemented.

### 5.1 Match predicates

Predicates compose with `&`, `|` and `~`, and are evaluated against `SvClass`:

```python
from sv_weave.match import extends, implements, has_method, has_attr, in_package, has_field

extends("uvm_sequence_item")          # transitive; qualified or unqualified name
implements("put_if")
has_method("build", virtual=True)
has_attr("weave_trace")
in_package("eth_*")
has_field(lambda f: f.rand)           # any field matching
```

Config rules can use the same predicates as strings, for example
`match: "extends(uvm_sequence_item) & ~has_attr(weave_nocopy)"`. This lets users widen
or narrow where a weaver applies without editing Python.

---

## 6. Weaving and the contribution model (stage 4)

### 6.1 The event bus

```python
class Weaver(sv_weave.Weaver):
    name = "copy"
    api = ">=0.1,<0.2"           # contribution-API version range (see §10)

    def subscribe(self, bus: Bus):
        bus.on(extends_root() & ~has_attr("weave_nocopy"), self.weave)

    def weave(self, w: WeaveCtx):
        copy = w.feature("copy")                    # declared by the active binding
        for f in w.cls.all_fields(upto=w.binding_root):
            if f.static or f.attrs.get("weave_nocopy"):
                continue
            copy.body.add(f"this.{f.name} = {copy.rhs}.{f.name};")
            # or, for anything shape-dependent:  copy.body.add(w.sv.copy_field(f, copy.rhs))
```

The bus calls handlers in a fixed order, so the output is the same on every run:
1. bindings' `prepare`, which declares features;
2. weavers, by config `order`, then by plugin name;
3. bindings' `finalize`, which adds registration and default bodies.

A handler runs once per **(target, profile)**, but only for profiles that include the
weaver's extension set. A weaver therefore never needs to know which profile it is in.

### 6.2 `WeaveCtx` and `WovenClassBuilder`

`WeaveCtx` exposes:
- `cls` (the `SvClass`), `binding`, `binding_root`, `profile`, `ext_set`, `options`
  (weaver options from config), and `diag` (for errors and warnings at a source
  location);
- `feature(name)`, which returns the feature's `MethodSlot`. It is an error if the
  binding does not define that feature;
- `override(method_name)`, which returns a `MethodSlot` that overrides a user or
  library virtual method directly (approach notes: *skeletons*);
- `add_method(...)`, `add_field(...)`, `add_registration(...)` and `add_item(text)`.
  `add_item` adds an arbitrary class item that no slot covers;
- `sv`, a set of helpers that produce SV fragments (§7.2).

### 6.3 Method slots: the override skeleton

The approach notes ask for overrides of the form `<decl> ; <pre-super> ; <post-super>`.
The handoff's "calling recognised methods in order" means the same thing: the order
and grouping of every weaver's contributions inside one generated method. (A
`method-order` weaver built in P5 on another reading was removed.)
Every overridden method is a `MethodSlot`:

```
virtual function <ret> <name>(<args>);    // signature copied from the base method
  <decl>          // local declarations, from all contributors, in order
  <pre>           // pre-super code, contributor order
  super.<name>(<args>);   // unless some contributor sets replace_super (exclusive)
  <post>          // post-super code, reverse contributor order (nests like wrappers)
  <ret-stmt>      // only when the function returns a value: return the super result or a contributor's
endfunction
```

`MethodSlot` has the fields `decl`, `pre`, `post`, `body` and `replace_super`. `body` is
an alias for `post`, the usual place for feature code.

**Placement (added after P8, user direction).** Each section orders its fragments
with:
- **a band:** `first` (prepend) ahead of append, the default;
- **default order within a band:** contributor (dispatch) order, reversed in `post`;
- **relationships:** `before`/`after` naming other weavers or bindings. These are
  textual within the section (in `post` too) and override the band and default
  order. They can be given per fragment (`add(text, before=..., after=...)`), as
  weaver class defaults, or in the config entry. Check reports contradictions.

Rules:
- **The target must be virtual.** If the nearest declaration of the method in the
  ancestry is not `virtual`, Check stops with an error such as `A::build is not
  virtual; cannot weave`. This is the "flag base not being declared virtual" item
  from the notes.
- **Signature:** the binding supplies it for features. For direct overrides it is
  copied from `SvMethod`, keeping argument directions and default values.
- **Tasks** get the same slots. A `fork` in a contribution is allowed only in
  extension sets marked `allow_threads` (see §6.6).

### 6.4 Inheritance chains (risk 1): flatten into each woven class

The problem: if both `A` and `B extends A` are woven, `Woven_B extends B` does not
inherit from `Woven_A`.

The handoff offered two fixes. Fix (b), helpers the chain calls, does not work for
`protected` fields. A static helper in another class cannot access `A`'s protected
members. Only subclasses of `A` can, and `Woven_B` is one.

**Decision proposed:** flatten. Each woven class covers every field and every
recognised method from the target up to the binding root, inline:
- `w.cls.all_fields(upto=binding_root)` is the standard iterator that does this.
- `Woven_B::do_copy` calls `super.do_copy(rhs)`, which runs any user-written `do_copy`
  in `B` or `A`, and then copies all of `A`'s and `B`'s fields.
- **Cost:** duplicated code, roughly linear in depth. That is acceptable for typical
  transaction hierarchies of 1–4 levels.
- **`local` fields** of any ancestor cannot be reached from a subclass at all. A
  weaver that needs one gets a diagnostic: warn and skip by default, or fail when
  `strict: true`. The user can make the field `protected` or mark it
  `(* weave_nocopy *)`.
- **Double handling:** if user code in `A::do_copy` already copies field `x` by hand,
  the woven code copies it again. That is harmless for copy and compare. For print and
  pack, the binding's feature declares `super_policy: call|skip`. UVM `pack` uses
  `skip` plus a check that warns when a user `do_pack` exists.

### 6.5 Fields, registration and other contributions
- `add_field` is limited to non-`rand` fields, and only in extension sets marked
  `allow_state`. Use it for things like "has this been read" bitmaps in debug.
- `add_registration` takes a binding-specific registration object. The binding's
  `finalize` renders it to SV (§8).

### 6.6 Extension-set safety (DV hazard)

Each extension set carries flags in the config. Their defaults are:

| Set | `allow_rand` | `allow_state` | `allow_threads` | `allow_alloc` |
|---|---|---|---|---|
| `core` | true | true | true | true |
| any other set | false | false | false | false |

The Verify stage (§7.3) re-parses the woven output with pyslang. For each fragment
that a non-core set contributed, it walks the slang syntax and semantic tree and
rejects any of the following, unless the set's flag allows it:
- `rand` and `randc` fields, and constraints (`allow_rand`);
- calls to `randomize`, `$urandom`, `$random` or `std::randomize`, and `srandom`
  (`allow_rand`);
- added class properties (`allow_state`);
- `new` and calls to factory `create` (`allow_alloc`);
- `fork` (`allow_threads`).

The rules run on what was actually generated, so a fragment that bypasses the helpers
is checked in the same way as one built with them. This turns "debug must not perturb
randomisation" from a convention into something the tool checks.

### 6.7 Design-wide queries and aggregate weavers

Some automation is about the *set* of classes, not about one class. The motivating
example is a **class selector**: given a base `T`, find every concrete subclass the
design contains and generate code that picks among them and creates the choice through
the factory. That way user overrides and weaving still apply to the selected class.
SystemVerilog has no reflection, so this has to be generated.

**Queries.** `w.model` is available to every weaver. It provides:
- `subclasses_of(T, concrete=True, transitive=True)`;
- `implementors_of(I)`;
- `classes(match)`, where `match` is any predicate from §5.1;
- `packages()`.

Results include every specialisation that was found (§4.3), sorted for determinism.
Selection rules (§5) do not filter queries: a selector usually wants every subclass,
woven or not.

**Aggregate subscriptions.** `bus.on_design(handler)` runs once per profile, after all
per-class handlers. Its context `DesignCtx` provides `model`, `profile`,
`woven(cls)` (the woven class for a target, if there is one) and these contribution
points:
- `add_class(pkg, WovenClass)`: a new generated class, not a subclass of a target;
- `feature_of(T, name)` / `override_of(T, method)`: contribute to the woven class of
  `T` itself. For example, a selector gives `Woven_T` a static `create_any()`;
- `add_registration(...)`: register with the runtime's type-enumeration table (below).

**Where aggregate code lives.** Code about `T` goes into `<pkg(T)>_woven`. That package
imports every user package that holds a subclass. This is always legal, because all
woven packages compile after all user packages (§7.4). If the dependencies form a cycle
across woven packages, the code goes into a single design-wide package,
`sv_weave_gen_pkg`, which compiles last.

**Runtime support (`sv_weave_pkg`).**
- `sv_weave_types #(T)` holds a statically typed list of the creators of `T`'s
  concrete subclasses. The generated code fills it, and through the factory adapter it
  hands out each subclass's *factory-resolved* implementation.
- `sv_weave_types #(T)::all()`, `::count()` and `::create(idx, inst)` let users and
  generated selectors enumerate the subclasses without naming them. A built-in
  `selector` weaver adds random selection, weighted by a `(* weave_weight = N *)`
  attribute.
- **Revised after P7 (user review):** sv-weave does not set up a parallel type
  registry; it works *with* the library's registry (for UVM, `uvm_factory`). So
  `sv_weave_types#(T)` and the `selector` weaver are not part of sv-weave. They live
  in `examples/selector/` as the worked example of a design-wide weaver; a real
  selector belongs in a UVM utility library, built on `uvm_factory`. sv-weave keeps the
  generator capability: design-wide queries (`w.model`, `d.model`) and `on_design`.
- Under the rand-safety rules (§6.6), a selector that randomises must belong to
  `core`.

---

## 7. Code generation and verification (stages 6–8)

### 7.1 Representation

No IR is shared with any other project. The model has two layers:

- **Structure** is held in sv-weave's own small dataclasses:
  - `WovenPackage(name, imports, classes, items)`;
  - `WovenClass(name, extends, members)`;
  - `MethodSlot` (§6.3);
  - `FieldDecl` and `ClassItem`.

  These exist because the framework must *reason* about them. It merges slots,
  dedupes classes across profiles, checks signatures against the `SvMethod` it
  overrides, and orders registrations.
- **Bodies** are SV text fragments: `SvFragment(text, origin)`. `origin` records the
  weaver, the extension set and the Python call site. Weaver authors write SV, the
  language they already know, and the framework does not try to model SV statements or
  expressions.

The renderer, `render.py`, is about 200 lines of sv-weave's own code. It:
- emits packages, classes and method skeletons;
- re-indents fragments;
- emits `endfunction : name` labels;
- keeps a line map from each woven-file line back to its `SvFragment.origin`.

### 7.2 `w.sv` helpers

The helpers deal with names, hygiene and indentation. They do not model SV:
- `w.sv.cast_rhs(cls, arg)` emits the `$cast` prologue and returns the name of the
  local handle;
- `w.sv.copy_field(f, rhs)` / `compare_field(f, rhs, result)` / `print_field(f, printer)`
  emit the right form for the field's type category: scalars, enums, strings, class
  handles (shallow, or deep when `weave_deep` is set), and fixed, dynamic, queue and
  associative arrays, each with `foreach` as needed;
- `w.sv.fresh(name)` returns a local name guaranteed not to collide with the user's
  members (`__w_<name>`);
- `w.sv.type_of(f)` gives the SV spelling of a field's type, already qualified for use
  from inside `<P>_woven`.

The helpers hold the type knowledge, built on `SvType` (§4.2), that every field weaver
needs. Third-party weavers reuse them instead of re-deriving it.

### 7.3 Verify: re-elaborate with pyslang

The same pyslang setup that loaded the user's sources is run again. It takes the
user's files plus `sv_weave_pkg`, the binding runtime and the rendered woven packages,
all held in memory with `SyntaxTree.fromText`. Then:
1. **Elaboration.** Every diagnostic from `getAllDiagnostics()` that falls in a woven
   buffer is an error. It is reported at the woven line, and through the line map at
   the contributing weaver, set and call site. Diagnostics in user buffers would
   already have stopped the run at Load.
2. **Rand-safety rules** (§6.6) run over the woven classes' syntax and semantic trees,
   scoped by fragment origin to each extension set.
3. **Structural cross-checks** that only the elaborated design can settle:
   - each woven method really overrides a virtual method, with an identical
     signature;
   - each woven class that gets registered is concrete;
   - each woven class's constructor matches the `create` signature the binding
     declared.

#### Verify levels

Full verification costs one more pyslang elaboration of the whole design on every run.
On a large UVM testbench that could take seconds or tens of seconds, which is too slow
for an edit-and-run loop. So verification has levels, set by `verify:` in the config
or `--verify=` on the CLI:

| Level | What runs | Cost |
|---|---|---|
| `full` | Steps 1–3 above. | One extra elaboration of the whole design |
| `syntax` | Woven buffers only, parsed alone with `SyntaxTree.fromText` and no elaboration. Parse errors, plus the rand-safety rules from §6.6 run on the syntax tree. | Proportional to the woven output only; expected to be negligible |
| `off` | Nothing. The rendered output is written directly. | – |

- **Syntax covers rand safety.** The rand-safety rules are keyword- and call-level:
  `rand`, `constraint`, `randomize`, `$urandom`, `new`, `fork` and added class
  properties. Running them on the syntax tree loses almost nothing. Two things need
  `full`: name resolution, such as a fragment calling a user helper that calls
  `randomize`, which is not caught at any level; and the structural cross-checks of
  step 3.
- **Caching.** The manifest records two hashes: one over the inputs (user sources,
  config and plugin versions) and one over the woven output. When both match the last
  run that passed `full`, Verify is skipped and reports `cached`. In practice `full`
  only runs when something actually changed.
- **Default.** Pending the M1 measurement, the default is `full` with caching. The
  intended steady state is `syntax` for local and dfm runs and `full` in CI, but only if
  M1 shows that `full` is slow (**[D9]**).
- **Reuse.** The Load compilation cannot be reused for Verify, because a pyslang
  `Compilation` is frozen once elaborated. The parsed user `SyntaxTree` objects *can* be
  reused, which saves the parse but not the elaboration. To be confirmed in M1.

### 7.4 Outputs (per run, into `out_dir`)

| File | Contents |
|---|---|
| `<P>_woven.sv` | `package <P>_woven; import sv_weave_pkg::*; import <P>::*; <binding imports>`, followed by woven classes and per-class registration. |
| `sv_weave_init_pkg.sv`, `sv_weave_init_m.sv` | `package sv_weave_init_pkg;` with `function automatic void sv_weave_init();`, which calls each `<P>_woven::__register()`; and `module sv_weave_init_m`, which calls it at static initialisation. One declaration per file (Verilator DECLFILENAME); until 0.2 both were in `sv_weave_init.sv`. See §8.4. |
| `sv_weave_rt.f`, `sv_weave.f` | Filelists. The runtime (`sv_weave_rt.f`: `sv_weave_pkg` and the binding runtime) must compile *before* the user's sources, and the generated code (`sv_weave.f`: woven packages, then init) *after* them, so one list cannot hold both. (Changed in P2; the draft had a single `sv_weave.f`.) |
| `weave-manifest.json` | Machine-readable list of target → woven class per profile, specialisation hashes, weavers and sets applied, and diagnostics. dfm and the report both use it. |
| `weave-report.md` | Human-readable view of the same (risk 3: "see what was woven"). |

Output is deterministic: sorted iteration, no timestamps in the files. The emitter skips
rewriting files whose content has not changed, so incremental sim builds stay warm.

---

## 8. SV runtime library: `sv_weave_pkg`

> **Superseded by restructure R (2026-11-08, user direction).** sv-weave ships no SV
> runtime and sets up no type registry of its own. It works *with* the library: the
> library's base class defines the virtual hooks that woven classes implement, and the
> library's factory (for UVM, `uvm_factory`) decides what gets created. Bindings map
> features onto those hooks and register woven classes with that factory; profile
> selection at run time is the binding's job. The UVM binding belongs in the separate
> `sv-weave-uvm` library. What this section describes now lives on as the example
> reference library `examples/reflib/` (renamed `ref_*`), and the UVM approach as
> `examples/uvm/`. The generated `sv_weave_init_pkg` and `sv_weave_init_m` remain:
> `sv_weave_init()` calls each woven package's `__register()`, and the module runs it
> from a static initialiser.
>
> The UVM adapter of §8.3 is built in `examples/uvm/sv_weave_uvm_pkg.sv` without a
> separate registry map: a `uvm_default_factory` subclass overrides
> `find_override_by_type`/`find_override_by_name`, lets UVM resolve overrides via
> `super`, then substitutes the resolved type's woven class for the active profile.

The runtime is factory-agnostic. It holds the **implementation map** and **profile
selection**. Factory adapters call into it after the factory's own override resolution.

### 8.1 Core types

```systemverilog
package sv_weave_pkg;

  // Creates one woven implementation. Generated per woven class.
  virtual class weave_creator;
    pure virtual function string impl_name();   // "Woven_A__debug"
    pure virtual function string profile();     // "debug"
    pure virtual function string type_name();   // "foo_pkg::A" (added in P3)
  endclass

  // Per-user-type implementation slot, statically typed (no string keys on the hot path).
  class weave_type #(type T = int);
    static weave_impl #(T) impls[string];       // profile -> creator
    static function void add(string profile, weave_impl #(T) c);
    // Return the woven object for the active profile of (T, inst_path), or null.
    static function T create(string inst_path = "");
  endclass

  virtual class weave_impl #(type T = int) extends weave_creator;
    pure virtual function T create();
  endclass

  // String-keyed view of the same map, for adapters that only know type names
  // (UVM create_*_by_name) and for reporting.
  class weave_registry;
    static function weave_registry inst();
    function void          add_type(string type_name, weave_creator c);
    function weave_creator lookup(string type_name, string inst_path);
    function void          dump();   // +weave_report: print every resolution
  endclass

  // Profile selection.
  class weave_profiles;
    static function void   set_default(string profile);
    static function void   select(string profile, string type_glob = "*",
                                  string inst_glob = "*");
    static function string active(string type_name, string inst_path);
    static function void   from_plusargs();   // +weave_profile=debug
                                              // +weave_impl=debug:pkt_txn[@inst_glob]
  endclass
endpackage
```

As built in P3 (see `src/sv_weave/share/sv/sv_weave_pkg.sv` and
`docs/reference/sv-runtime.rst`): the default profile has three sources, in priority
order `+weave_profile`, `set_default()`, then `set_config_default()` called by the
generated `__register()`; several `+weave_impl` rules go in one comma-separated
plusarg, because simulators return only the first match of a repeated plusarg.

Resolution:
1. `active(type, inst)` returns the most specific matching `select` rule. Ties go to
   the last rule declared.
2. Otherwise, the default profile from the config, which the init code bakes in and
   `+weave_profile` overrides.
3. If the chosen profile has no implementation for this type, use the `release`
   implementation if one exists, else none. The factory then makes the user's class
   unchanged.

### 8.2 What a woven package looks like (plain binding, `copy` weaver)

```systemverilog
package foo_pkg_woven;
  import sv_weave_pkg::*;
  import foo_pkg::*;

  class Woven_B__release extends B;
    virtual function void copy(weave_object rhs);
      B _rhs;
      super.copy(rhs);
      if (!$cast(_rhs, rhs)) begin $fatal(1, "copy: type mismatch"); end
      this.a_fld = _rhs.a_fld;     // from A, flattened (§6.4)
      this.b_fld = _rhs.b_fld;
    endfunction
  endclass

  class Woven_B__release__impl extends weave_impl #(B);
    virtual function string impl_name(); return "Woven_B__release"; endfunction
    virtual function string profile();   return "release";          endfunction
    virtual function B create(); Woven_B__release o = new(); return o; endfunction
  endclass

  function automatic void __register();
    Woven_B__release__impl i = new();
    weave_type #(B)::add("release", i);
    weave_registry::inst().add_type("foo_pkg::B", i);
  endfunction
endpackage
```

Constructor arguments: UVM components take `(name, parent)`. The binding supplies the
signature of `create` and of the woven class's `new`, and the woven `new` forwards to
`super.new(...)`.

### 8.3 Factory adapters (one per binding)

| Binding | Adapter |
|---|---|
| **plain** | `sv_weave_pkg` itself is the factory: `weave_factory#(T)::create(inst)` is `weave_type#(T)::create(inst)`, and if that returns null it does `T::new()`. Users write `weave_factory#(A)::create()`. |
| **uvm** | `weave_uvm_factory extends uvm_default_factory`, installed with `uvm_factory::set()`. `create_object_by_type`/`by_name` first resolve through `super` to the overridden type, then call `weave_registry::lookup(resolved_name, path)`. Each woven UVM class is also registered as a `uvm_object_registry #(Woven_X)` so that `create()` works. Done by subclassing the factory, not by `set_type_override`, because overrides depend on registration order (handoff decision). The UVM factory's behaviour has not been checked against `uvm_factory.svh` yet (risk 4); the uvm-binding milestone checks it first. |
| **fw** | One call after `ctx.resolve(...)` in `fw_factory::create`. It lives in fw-hdl, or in `weavers-fw` (Q1). fw-hdl source is not in this workspace, so this design only fixes the contract: *adapter gets the resolved type name and instance path, and asks `weave_registry`*. |

**Views versus profiles:** fw's view picks the realisation, and `weave_profiles` picks
what is woven into it. They are separate inputs to resolution, in that order. The plain
and UVM adapters have no views.

### 8.4 Registration trigger (risk 2)

Static initialisers in a package that nothing references may never run, depending on
the simulator. So the **primary mechanism is explicit** and the static one is an
optional extra:
- **Explicit (default):** the generated `sv_weave_init_pkg::sv_weave_init()` calls
  every `__register()`. Each binding's adapter calls it once, guarded by a static
  flag, the first time the factory is used:
  - UVM: when the adapter factory is installed;
  - fw: on the first `fw_factory::create`;
  - plain: on the first `weave_factory::create`.

  The adapter is compiled *before* the generated init package, so it reaches it
  through a hook: `sv_weave_pkg::weave_init_hook`, a `weave_initializer` handle. The
  init package sets the hook from a static initialiser in a module, `sv_weave_init_m`,
  which the user's top instantiates, or which the dfm flow adds as an extra top.
- **Static (opt-in, `registration: static`):** each woven package also has
  `static bit __r = __register_once();` in a holder class. This is only for simulators
  shown to run it.

**[D2]** Is an extra top module (`sv_weave_init_m`) acceptable, or does every flow need
a zero-touch path? The spike (M1) measures what Verilator and xezim actually do, then
we decide.

---

## 9. Configuration (`sv-weave.yaml`)

```yaml
sv-weave:
  version: 1
  sources:                    # optional when invoked from dfm (FileSet supplies them)
    filelists: [rtl/files.f]
    incdirs: [rtl/include]
    defines: {SIM: 1}
  packages:
    include: ["eth_*", "foo_pkg"]
    exclude: ["*_tb_pkg"]
  binding: uvm                # or: plain, fw; or a list when mixing libraries
  out_dir: build/woven
  registration: explicit      # explicit | static
  strict: false               # make warnings (e.g. unreachable local fields) errors
  verify: full                # full | syntax | off  (§7.3); cached when inputs+output unchanged

  extension-sets:
    core:          {}
    debug.xcheck:  {}                         # defaults: no rand/state/threads/alloc
    debug.readset: {allow_state: true}
    debug.trace:   {allow_alloc: true}

  weavers:
  - name: copy                # entry-point name
    set: core
  - name: compare
    set: core
  - name: xcheck
    set: debug.xcheck
    match: "extends(uvm_sequence_item)"      # narrows the weaver's own subscription
    options: {on_x: error}

  profiles:
    release: [core]
    debug:   [core, "debug.*"]
  build-profiles: [release, debug]   # which to generate; [release] = compile-time choice
  default-profile: release
```

**Compile-time vs runtime selection:**
- **Compile-time:** set `build-profiles` to a single profile. Only that profile's
  woven classes exist, and the release build contains no debug code.
- **Runtime:** list several profiles and select with plusargs (§8.1).
- **Deduplication:** where two profiles end up with identical contributions for a class,
  only one woven class is emitted, and both profile entries register it.

**[D3]** The notes say "on plusarg, activate *set*", which suggests set-level runtime
switching. This design switches whole **profiles**: each one is a separate woven class,
with no runtime guards in the code. The alternative is one woven class with
`if (sv_weave_pkg::set_on(ID))` guards:
- **For guards:** any combination of sets can be chosen at runtime.
- **Against guards:** debug code stays in release builds, every call pays for the
  checks, and for fw-hdl it is not zero-cost.

Proposal: profiles now. Add `mode: guarded` as a per-profile option later if users ask
for arbitrary combinations.

---

## 10. Plugins, discovery and versioning

Entry-point groups, found through `importlib.metadata`:

| Group | Object | Contract |
|---|---|---|
| `sv_weave.weavers` | `Weaver` subclass | `name`, `api`, `subscribe(bus)`, `options_schema` (optional) |
| `sv_weave.bindings` | `Binding` subclass | `name`, `api`, `roots`, `features()`, `prepare/finalize(w)`, `sv_runtime_files()`, `create_signature(cls)` |

Versioning:
- The **contribution API** (`WeaveCtx`, `MethodSlot`, `w.sv`, `SvModel`) carries a
  semver of its own, `sv_weave.API_VERSION`, starting at `0.1`.
- Each plugin declares a compatible range. A plugin outside the range is refused at
  load time with a clear message. This is the "version the IR from day one" decision,
  applied to the API that is actually shared.
- The manifest records the API version and every plugin's version, so a woven build
  can be reproduced.

Built-in plugins: the `copy`, `compare`, `print` and `xcheck` weavers. sv-weave has
no built-in binding (restructure R): bindings live with their libraries, the UVM one in
`sv-weave-uvm`; `examples/uvm/` and `examples/reflib/` show how.

---

## 11. Tooling: CLI and dv-flow package

**CLI** (`sv-weave`):
- `sv-weave gen -c sv-weave.yaml [-f files.f] [-o out]` runs the full pipeline.
- `sv-weave list [--targets|--weavers|--bindings]` runs selection only and prints what
  would be woven.
- `sv-weave report build/woven/weave-manifest.json` renders the manifest as markdown.
- `sv-weave rt-path` prints the directory of `sv_weave_pkg.sv` and the binding runtimes,
  for use in hand-written filelists.

**dv-flow package `svweave`:**
- It follows the libhdlsim conventions: `__ext__.dvfm_packages()` points to `flow.dv`,
  registered under the `dv_flow.mgr` entry point.

| Task | Consumes | Produces |
|---|---|---|
| `svweave.Runtime` | – | FileSet `systemVerilogSource` with `sv_weave_pkg.sv` and the configured binding's runtime |
| `svweave.Weave` (pytask) | `systemVerilogSource` FileSets (the user's sources, in order) | FileSet `systemVerilogSource`: the woven packages and init package in compile order. Also a `std.FileSet` of type `jsonManifest` holding `weave-manifest.json`. Params: `config`, `profiles`, `binding`. |

Usage:

```yaml
- name: woven
  uses: svweave.Weave
  needs: [rtl, tb]
  with: {config: sv-weave.yaml}
- name: sim
  uses: hdlsim.vlt.SimImage
  needs: [svweave.Runtime, rtl, tb, woven]
```

- Incremental builds: `changed=False` when the manifest hash is unchanged.

---

## 12. Decisions requested

| # | Question | Proposal |
|---|---|---|
| D1 | ~~Zuspec IR for contributions~~ | **Decided 2026-11-08:** independent and pyslang-centric. sv-weave keeps its own structure model, method bodies are SV fragments, and pyslang re-verification replaces checking over an IR (§7). |
| D2 | Registration trigger | Explicit `sv_weave_init()` through an adapter hook and a small init module. Static as opt-in. Revisit after the M1 spike. |
| D3 | Runtime unit: profile or extension set? | Profile (separate woven classes). `guarded` mode later if needed. |
| D4 | Inheritance | Flatten fields and recognised methods into each woven class (§6.4), rather than chaining helpers, which fail on `protected` fields. |
| D5 | One repo for now? | Yes. Develop `sv_weave` (engine, `plain` binding, core weavers, `sv_weave_pkg`) in this repo, then split into the org layout once API 0.1 is stable. |
| D6 | Woven naming | `Woven_<C>[_<hash>]__<profile>` in package `<P>_woven`. Users never type these names, but they appear in logs and the report. |
| D7 | Where the fw adapter and weavers live | Still handoff Q1, and needs the fw-hdl source. Not blocking for M0–M2. |
| D9 | Default Verify level | `full` with caching until M1 measures the cost. Switch the default to `syntax`, with `full` in CI, if a full re-elaboration costs a noticeable fraction of the user's compile time. |

---

## 13. Proposed source layout and milestones

```
pyproject.toml                      # name: sv-weave; entry points; package-data **/*.sv, flow.dv
src/sv_weave/
  __init__.py  __version__.py  api.py          # API_VERSION, public re-exports
  config.py                                    # sv-weave.yaml schema (pydantic) + loader
  run.py                                       # stages 1–7 wired together
  cli.py
  frontend/loader.py   frontend/model.py   frontend/specialize.py
  match.py   bus.py   diag.py
  weave/ctx.py   weave/builder.py   weave/slot.py   weave/svhelpers.py   # w.sv
  check.py
  render.py   verify.py   report.py           # SV text + line map; pyslang re-elaboration
  plugin.py                                    # Weaver/Binding bases, discovery, version gate
  bindings/plain.py   bindings/uvm.py
  weavers/copy.py  compare.py  print.py  method_order.py
  dfm/__ext__.py  dfm/flow.dv  dfm/tasks.py
  share/sv/sv_weave_pkg.sv  share/sv/sv_weave_uvm_pkg.sv
tests/unit/  tests/sim/   # sim tests run on verilator and xezim through dfm / pytest-dfm
```

| Milestone | Content | Exit criteria |
|---|---|---|
| **M0 Model** | Loader, `SvModel`, specialisation discovery, match predicates, selection, `sv-weave list`, report skeleton | Unit tests on small SV fixtures: inheritance, interfaces, parameterised classes, attributes |
| **M1 Spike** | `plain` binding, `sv_weave_pkg`, one `MethodSlot` override weaver, rendering and pyslang verification, explicit and static registration | Verilator and xezim run a test where `weave_factory#(A)::create()` returns the woven class. Registration-trigger behaviour recorded for each simulator (risk 2, D2). Load and Verify times measured on a small fixture and on a full UVM testbench (for example, an existing UVM example with the UVM library), to settle D9. |
| **M2 Core weavers** | copy, compare, print with flattening; extension sets and profiles; the Check stage (virtual, local) and Verify rand-safety rules; runtime plusargs | Sim tests for a 3-level hierarchy; a debug-profile seed reproduces release randomisation |
| **M3 dv-flow** | `svweave` package, Runtime and Weave tasks, incremental builds | Example flow runs under pytest-dfm |
| **M4 UVM** | Verify `uvm_factory` behaviour (risk 4), `weave_uvm_factory`, UVM features `do_copy`/`do_compare`/`do_print`/`do_pack` | Instance and type overrides plus weaving; benchmark against `uvm_field_*` |
| **M5 fw** | fw binding and the `fw_factory` hook, then a weaver to replace `FW_*_IMP` | Needs fw-hdl; follows the handoff's fw-hdl spike |

The handoff's next step 2 runs the fw-hdl spike first. This design puts the `plain`
spike (M1) first, because it is self-contained in this workspace and answers the same
registration and override-forwarding questions. M5 then only has to add the fw adapter.
**[D8]** Is that reordering OK?
