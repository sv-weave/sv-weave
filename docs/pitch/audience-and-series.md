# sv-weave: audience and blog-series plan

Status: brainstorm, 2026-11-08. Builds on `docs/design/value-pitch.md` and
`docs/pitch/blog-sv-weave.md` (the launch post).

## 1. Audience map

| # | Audience | What they care about | Role | Pick-up speed |
|---|---|---|---|---|
| A1 | **Methodology / verification-infrastructure leads** | Enforcing conventions across many engineers; keeping quality consistent | Producer, and the person who decides | **Immediate.** They feel the pain and own the fix. |
| A2 | **In-house VIP and protocol-package authors** | Delivering components that are correct without support tickets | Producer | **Immediate.** "Ship the generator with the library" is made for them. |
| A3 | **Open-source / Verilator / cocotb users** | UVM that runs on open simulators; Python-native tooling; no licence friction | Producer and consumer | **Immediate.** They're used to early tools, have little procurement overhead, and field macros are a known pain on Verilator. |
| A4 | **Small teams and startups with no methodology team** | Getting a methodology without building one | Consumer of someone else's weavers | **Fast**, once `sv-weave-uvm` ships good defaults. |
| A5 | **DV engineers writing testbenches** | Less boilerplate, fewer silent bugs | Consumer | **Pulled in, not pushing.** Delighted when it arrives, but they rarely change the flow themselves. |
| A6 | **Regression and triage owners** | Reproducing failures fast | Consumer of profiles | **Fast** once the replay story is proven. |
| A7 | **Verification managers** | Onboarding time, consistency, bug escapes, cost | Sponsor | **Medium.** Needs numbers. |
| A8 | **CAD / flow teams** | Build reproducibility, build time, simulator support, maintenance | Gatekeeper | **Slow.** They're the most likely to block it. |
| A9 | **Commercial VIP vendors** | Customer support, IP protection, support on every simulator | Producer | **Slow.** Interested, but cautious. |
| A10 | **EDA vendors** | Debug integration, performance, whether this competes with their tools | Ecosystem | **Watching.** |
| A11 | **Regulated industries (ISO 26262, DO-254)** | Tool qualification, traceability | Consumer | **Slow.** Generated verification code needs a qualification argument. |
| A12 | **fw-hdl / Zuspec users** | Synthesizable class code with generated implementations | Producer and consumer | **Immediate**, within the ecosystem. |
| A13 | **People doing AI-assisted verification** | Small, regular input that agents get right | Consumer | **Fast.** The "compressed input" story fits them. |

**Who to court first:** A1, A2, A3 and A12. They gain the most, have the least friction,
and their success becomes the evidence for everyone else. A5 follows A1 automatically.
A7 and A8 need proof (numbers, adoption stories) before they'll move.

## 2. Concerns we'll hear

Each concern is listed with an honest answer, where we have one. Concerns marked
**open** have no good answer yet; they're inputs to the design as much as to the
blog.

| Concern | Who raises it | Answer / status |
|---|---|---|
| "It's magic; I can't see what my class does." (aversion to aspect-oriented programming and action at a distance) | A5, A8, code reviewers | The woven package is readable SV, `sv-weave report` shows what each weaver contributed, and you can step through it in the debugger. Attributes show intent in the class itself. |
| "It's another build step." | A8 | One dv-flow task or CLI call. **Open:** examples for plain Makefile and vendor flows; incremental and cached builds; parse time on large testbenches. |
| "Objects created with `new()` aren't woven." `tx = new("tx")` is common in sequences, and such an object silently gets the base hooks. | A1, A5 | **Open, and important.** Weaving relies on the factory by design. sv-weave should **lint calls to `new()` on target classes** and report them. This is a design item. |
| "Adopting it changes my seeds." | A6, A1 | Expected to be a one-time change, if any; the stability check measures it. Say so up front. |
| "Does debug code really not perturb randomization?" | A6 | The rand-safety rules, the RNG fence, and a generated stability check run on each simulator. |
| "Is it really fast?" | A7, A1 | Benchmarks against field macros and hand-written hooks, with the method published. |
| "Does it run on my simulator?" | A8, A9 | A support matrix. **Open:** results on commercial simulators. |
| "Our VIP is encrypted. Can slang parse it?" | A9, A8 | **Open.** Only user classes need weaving, but slang needs the base classes' declarations. Options: unencrypted header stubs, or a binding-supplied API description. |
| "Type names in logs and factory overrides by string." What do `get_type_name()`, `factory.print()` and overrides by type name show for woven classes? | A5, A6 | **Open.** Define this and document it; ideally woven classes show the original name. |
| "Generated code shows up in code coverage." | A7, A11 | Exclude woven packages by default, and document how. |
| "Tool qualification." | A11 | **Open.** Verify-before-write and traceable output (which weaver produced which line) are the starting points for a qualification argument. |
| "Who maintains it? What happens when pyslang changes?" | A8, A7 | Open-source, depends only on pyslang, and has a versioned plugin API. Needs a public compatibility policy. |
| "The weavers are arbitrary Python running in my build." | A8, security | The same trust model as any build plugin. Pin versions; the report lists every weaver that ran. |
| "We already have field macros everywhere." | A1, A5 | Gradual migration: woven code runs after `super`, and an audit mode finds the gaps in existing hand-written hooks. |
| "My commercial VIP customers won't install Python." | A9 | Ship pre-woven output for known configurations; weave on demand otherwise (the "fileset with an optional generator" idea in `pitch.md`). |

## 3. Blog-series outline

The series moves from **why** to **how** to **trust** to **what's next**. Each post
has one audience, one message and one runnable example under `examples/`.

### Phase 1: launch (needs only what's built)

**1. Stop writing UVM boilerplate** *(written: `docs/pitch/blog-sv-weave.md`)*
- Audience: all DV, aimed at A1 and A5.
- Message: write the class you meant to write; only producers learn the generator.

**2. How weaving works: borrowing the factory**
- Audience: A1, A8, and readers who are skeptical about "magic".
- Message: there's no magic. A subclass, a factory substitution, readable output.
- Walk-through: from source to slang model, then weaver contributions, the woven
  package, verification, and registration. Show the generated code, the report, and
  stepping through it in the debugger.
- Answers: "magic", debuggability, type names in logs.

**3. Your first weaver in 20 lines**
- Audience: A1, A2, A3.
- Message: producing is easy too. Match a pattern, contribute to a feature, and the
  binding handles the library.
- Example: a `convert2string` or `pack` weaver, with attributes, tests, and the error
  you get when the generated code is wrong.

**4. Bringing sv-weave into an existing testbench**
- Audience: A1, A8.
- Message: you can adopt it one class at a time, starting this week.
- Covers: coexistence with field macros, audit mode, the `new()` lint, the one-time
  seed change, and integration with Makefile, CLI and dv-flow.
- Answers: build step, migration, `new()`, seeds.

### Phase 2: trust (needs data and the stability features)

**5. Debug without changing your stimulus**
- Audience: A6, A1.
- Message: rerun a failing seed with every check on and get the same stimulus.
- Covers: profiles, the rand-safety rules, the RNG fence, the stability check, and a
  triage walk-through.

**6. The numbers: woven vs field macros vs hand-written**
- Audience: A7, A1, skeptics.
- Message: neutral to faster, with the method published.
- Covers: run time on a realistic mix of sequence items, compile time, weave time on a
  large testbench, and lines removed.

**7. UVM on open-source simulators**
- Audience: A3.
- Message: plain woven code instead of field macros helps UVM run on Verilator.
- Covers: a cocotb or Verilator flow end to end with dv-flow.

**8. Shipping a library with its generator**
- Audience: A2, A9.
- Message: VIP authors ship expertise, not just base classes.
- Covers: a protocol package worked through from start to finish, versioning weavers
  with the library, pre-woven output vs weaving on demand, encrypted IP.

### Phase 3: what's next (needs features under development)

**9. Reflection for SystemVerilog**
- Audience: A1, A2.
- Message: weavers can see the whole design.
- Covers: registries, selectors, `build_phase` and connection generation.

**10. Coverage your constraints can actually reach**
- Audience: A1, A7.
- Message: covergroups that stay in step with the transaction, with bins taken from
  constraint analysis.

**11. One class, many languages**
- Audience: A3, A12.
- Message: the SV class is the single source for Python and C++ mirrors, DPI,
  documentation and schemas. This is the SV-introspection pipeline.

**12. Fewer tokens, fewer bugs: sv-weave and AI-assisted verification**
- Audience: A13, A7.
- Message: compressed input. Agents write plain classes, and the rules live in
  weavers.

### Running item

**FAQ / "Yes, but…"**
- A living post that answers section 2's concerns directly, and is updated as the
  open items close. Every post links to it.

## 4. Notes on the series

- **The series doubles as requirements discovery.** The concerns marked open (the
  `new()` lint, encrypted base classes, type names, build integration, tool
  qualification) should become work items before posts 2, 4 and 8 go out.
- **Gate each post on what's real.** Phase 1 uses what's already built. Phase 2 needs
  the benchmarks and the stability features. Phase 3 posts are written as "where
  we're going", or they wait until the features exist.
- **An example for each post.** Each post links a runnable directory, so a reader can
  reproduce it in five minutes.
- **Guest posts.** An early A1 or A3 adopter writing post 4 or 7 would carry more
  weight than anything we write.
- **Cadence.** Roughly every two weeks; phase 1 back to back to keep the launch's
  momentum.
