# sv-weave market survey: UVM or fw-*?

Status: 2026-11-08. Web research, run 2026-11-08, plus analysis. Confidence: **H**
high, **M** medium, **L** low. Unverified items are marked.

## Recommendation

**fw-\* drives the design; UVM is where the market is. Enter UVM through a narrow
wedge, not a broad "fix UVM" pitch.**

1. **fw-hdl / fw-dv stays the design driver and first committed user.** sv-weave is
   a hard dependency there (handoff Q1), so fw-\* succeeds whether or not UVM adopts.
   But fw-\* is not a market: mainstream synthesis tools don't support SV classes, and
   no HLS tool takes them, so synthesizable class-based SV is a niche no vendor serves
   (§3). fw-\* proves the technology; it won't build a user base by itself.
2. **UVM is the market.** UVM is used on about 80% of IC/ASIC projects and about 50%
   of FPGA projects, and its share is still growing (§1). The field-macro problem
   has been documented since 2011, and **no existing tool takes the user's own class
   as its input** (§2). The gap is real and empty.
3. **But UVM shops are conservative.** Most are still on UVM 1.1d or 1.2, they run
   vendor sign-off flows, and some work under safety-standard rules. Win them with a
   few pain points we can clearly solve, aimed at the people most likely to say yes
   (open-source and Verilator users, and methodology leads at small and mid-size
   teams), before going after large commercial sign-off shops.
4. **Keep the engine neutral.** UVM traction must not pull the core towards UVM.
   Bindings keep each library's specifics at the edge, which is already the design.
   fw-\* needs (the synthesizable subset, views vs profiles, resolving the factory
   statically for synthesis) stay first-class.

The two efforts reinforce each other. UVM adoption brings users, contributors and
credibility that fw-\* can't produce alone. fw-\* gives a demanding second binding,
which keeps the engine from becoming UVM-shaped.

## 1. Size and trend

| Fact | Conf. | Source |
|---|---|---|
| UVM is used on ~80% of IC/ASIC projects and ~50% of FPGA projects (2024 study). FPGA projects also use OSVVM (~35%) and UVVM (~28%). | M | [Siemens/Wilson 2024](https://verificationacademy.com/topics/planning-measurement-and-analysis/wrg-industry-data-and-trends/2024-siemens-eda-and-wilson-research-group-ic-asic-functional-verification-trend-report/), [Sigasi summary](https://www.sigasi.com/news/verification-blog/) |
| Growing: >70% ASIC and >40% FPGA in an earlier study | M | [Siemens blog 2016](https://blogs.sw.siemens.com/verificationhorizons/2016/03/21/dvcon-us-uvm-is-big/) |
| Only 14% of IC/ASIC projects got first-silicon success (the lowest in 20 years), and 75% were behind schedule | M | Siemens/Wilson 2024 |
| Demand for verification engineers grew 6.2% a year (2007–2022); no total headcount found | M | [Siemens blog 2022](https://blogs.sw.siemens.com/verificationhorizons/2022/12/12/part-8-the-2022-wilson-research-group-functional-verification-study/) |
| Version inertia: 50% on UVM 1.2, 40% on 1.1d, <5% on 1800.2-2020 (DVCon 2021 poll, ~170 people) | M | [AMIQ](https://www.consulting.amiq.com/2021/03/05/highlights-of-dvcon-us-2021/) |
| Open source: Verilator supports UVM 2020-3.2 (5.052, Sep 2026); cocotb 2.0 (Nov 2025); pyuvm 3.0 added a register layer; slang leads the sv-tests compliance suite | H | [Verilator changes](https://verilator.org/guide/latest/changes.html), [Antmicro](https://antmicro.com/blog/2025/10/support-for-upstream-uvm-2017-in-verilator), [cocotb](https://www.cocotb.org/blog.html), [sv-lang](https://sv-lang.com/) |
| 2024 percentages for Python/cocotb, PSS and SystemC | — | not verified |

## 2. Competitors

| Tool | Approach | Model |
|---|---|---|
| Siemens UVMF | YAML → whole testbench | Free, Apache-2.0 |
| Doulos Easier UVM | Templates and guidelines → testbench | Free |
| Synopsys uvmgen | Skeleton generator | Bundled with VCS |
| Agnisys IDesignSpec | Spec → RTL, register layer, testbench | Commercial |
| PeakRDL-uvm, ralgen | SystemRDL or IP-XACT → register model | Open source / commercial |
| Reflection work: Rich (DVCon 2016, VPI/DPI), Timi (2016 API prototype) | Runtime introspection | Research; not widely adopted (L) |
| Specman e (AOP) | Weaving in a proprietary language | Declined after SV/UVM; the industry chose a standard language over a more powerful proprietary one |

- **Every generator works from separate metadata** (YAML, a spec, SystemRDL) and
  mostly scaffolds testbenches. None reads the user's own class and generates its
  hooks (M; absence of evidence).
- **Generators are free or bundled.** sv-weave has to be free and open.
- **The e lesson:** sv-weave wins because its output is *plain standard SV*, unlike
  e's AOP. Say so in the pitch.

## 3. The fw-\* side

- **Synthesis tools don't support SV classes** beyond static functions in parameterized
  classes (Design Compiler, Vivado). There's no HLS from SV classes; Catapult and
  Stratus take C++ and SystemC (H, partly absence of evidence).
- **Neighbouring projects:** Chisel has ~4.8k GitHub stars, SpinalHDL and Amaranth
  ~2.1k each (L, secondary source). Bluespec is open source. XLS is "experimental".
- **Conclusion:** fw-hdl's audience is a research-sized group. It's strategically
  important to the Zuspec ecosystem, but it isn't a market for sv-weave.

## 4. UVM pain points and sv-weave's fit

Sources are DVCon papers, Verification Academy and Accellera forums, Semiengineering,
Hacker News and the cocotb survey. Reddit couldn't be fetched.

| Pain point | Widespread? | sv-weave fit | Key source |
|---|---|---|---|
| **Boilerplate and field macros.** A 22-line class expands to 644 lines; macros hurt speed and debug. | many | **Direct.** This is the core use case. | [Erickson, DVCon 2011](https://dvcon-proceedings.org/wp-content/uploads/are-ovm-uvm-macros-evil-a-cost-benefit-analysis.pdf) |
| **config_db:** keyed by strings, silent misses, slow with wildcards (5000 set/gets take ~200 s) | many (≥4 DVCon papers) | **Partial to direct. Not in our plan yet** (see §5). | [Go Figure](https://dvcon-proceedings.org/wp-content/uploads/go-figure-uvm-configure-the-good-the-bad-the-debug-paper.pdf), [Config Madness](https://dvcon-proceedings.org/wp-content/uploads/1118-Avoiding-Configuration-Madness-The-Easy-Way.pdf), [Glasser](https://dvcon-proceedings.org/wp-content/uploads/configuration-in-uvm-the-missing-manual.pdf) |
| **Generators' own pains.** Doulos: "Do not modify the generated code until… you are ready to burn your bridges"; the way out is to "extend classes and override". | some | **Direct.** Generating subclasses and overriding is sv-weave's architecture. | [Aynsley, DVCon 2022](https://dvcon-proceedings.org/wp-content/uploads/how-far-can-you-take-uvm-code-generation-and-why-would-you-want-to-presentation.pdf) |
| **Random stability.** A small change can shift test results. | some (experts) | **Direct, and a differentiator.** | [Doulos SNUG 2013](https://www.doulos.com/media/1293/snug2013_sv_random_stability_paper.pdf), [AMIQ 2026 stimuli replay](https://www.consulting.amiq.com/2026/11/02/uvm-stimuli-replay/) |
| **Performance overhead** (macros, config_db, objections) | some to many | **Partial to direct** | [Yikes](https://dvcon-proceedings.org/wp-content/uploads/yikes-why-is-my-systemverilog-testbench-so-slooooow.pdf) |
| **Debug visibility** of macro code | many | **Direct**, if the output is readable and kept as files | Erickson |
| **Factory verbosity**; overrides miss on `new()` | some | **Partial.** sv-weave inherits the `new()` blind spot. | [VA forum](https://verificationacademy.com/forums/t/factory-type-override-of-sequence-item-does-not-work/41646) |
| Phasing and objections | many | Partial (build/connect wiring only) | [Rapid Adoption](https://dvcon-proceedings.org/wp-content/uploads/uvm-rapid-adoption-a-practical-subset-of-uvm-paper.pdf) |
| TLM verbosity (`imp_decl`) | some | Partial, if connect generation is added | Erickson |
| Open-source simulator support | some | Partial (inference) | [Antmicro](https://antmicro.com/blog/2023/10/running-simple-uvm-testbenches-in-verilator) |
| **Complexity and learning curve** (the most cited pain) | many | Partial. It hides some mechanics but **adds concepts**. | [Johnson](https://semiengineering.com/the-future-of-uvm/), Rapid Adoption |
| Reuse that doesn't materialise | many | None | [Litterick](https://dvcon-proceedings.org/wp-content/uploads/pragmatic-verification-reuse-in-a-vertical-world.pdf) |
| Sequences, virtual sequencers, p_sequencer | many | None | [Semiengineering](https://semiengineering.com/universal-verification-methodology-running-out-of-steam/) |
| Register model (RAL) | some | None (register generators own this) | Accellera forum |

**Of the five biggest pains:** boilerplate (direct), config_db (direct, if built),
complexity (partial), reuse (none), scenario control (none). The pains that drive
people to cocotb and PSS are ones sv-weave doesn't touch. **Don't pitch sv-weave as
a fix for UVM's complexity.** Pitch it as:

> Hand-quality code with macro convenience, type-checked configuration, and debug
> builds that don't move your seeds.

## 5. What this changes

### New opportunity: type-checked config_db

This came out of the research and isn't in the design yet. config_db is the
second-most-cited UVM pain, with at least four DVCon papers on it. A weaver can:
- generate typed `get` calls for fields marked with an attribute (e.g.
  `(* weave_config *) virtual bus_if vif;`), with a fatal error on a miss and a clear
  message;
- cross-check, at build time, the `set` and `get` calls slang can see (with literal
  keys and types) and report type mismatches and keys nobody reads;
- replace wildcard lookups on hot paths with generated direct calls.

Runtime paths stay dynamic, but the silent-miss class of bug goes away.

### Must-haves before pitching to UVM shops

- **A `new()` lint.** The most common factory bug is a silent fallback to `new()`,
  and sv-weave would fail silently in the same way. Report every `new()` on a target
  class.
- **Readable output that teams can check in, and line mapping back to the weaver.**
  Otherwise generated code becomes the new macro soup.
- **Clear override precedence.** User overrides vs weaving, with `factory.print()`
  showing woven classes. The custom `uvm_factory` subclass is the biggest trust
  hurdle.
- **slang vs vendor dialects.** Vendor flows accept constructs slang rejects. Parse
  only the user's packages, provide slang's compatibility options, and have a story
  for encrypted base classes.
- **Coexistence with UVMF, Easier UVM and in-house generators.** sv-weave weaves
  whatever classes they emit; it doesn't replace them.

### Who to target first (narrows `audience-and-series.md`)

1. Open-source and Verilator UVM users (A3): low friction, Python-friendly, and
   UVM 2020 now runs on Verilator.
2. Methodology leads at small and mid-size teams (A1 and A4).
3. fw-\* users (A12): already committed.

Large commercial sign-off shops (A8, A9, A11) come later, once there are adoption
stories and the must-haves are in place.

### Changes to the blog series

- Add a **config_db post** ("No more silent config_db misses") to phase 2, as soon as
  the weaver exists. It may be the strongest hook after the launch post.
- Lead the launch post with the **Erickson numbers** (22 → 644 lines). They are
  independent, citable and well known.
- Quote **Aynsley's "extend classes and override"** in post 2 (how weaving works):
  a recognised expert names our architecture as the way out.
- Bring the **random stability** post forward. There's live interest (AMIQ, Nov
  2026), and nobody else claims this.
- Don't pitch reduced complexity, reuse, sequences or RAL.

## 6. Decision gates

| Gate | Criterion | If met | If not |
|---|---|---|---|
| G1: fw-hdl spike | One `FW_*_IMP` replaced by a weaver; runs on Verilator and xezim | Commit to sv-weave as a hard dependency of fw-\* | Re-examine the factory approach before any UVM work |
| G2: UVM wedge | do_* weavers, the `new()` lint, the override story and a benchmark against field macros | Launch phase 1 of the blog series | Hold the UVM launch; keep it fw-\* only |
| G3: design partners | 2–3 outside teams (open-source or small/mid) using it on a real testbench | Invest in config_db, `sv-weave-uvm` as a product, commercial simulator results | Keep UVM as a binding and example; fw-\* stays the focus |

## Open questions

- Commercial-simulator behaviour with the factory adapter, and parse compatibility, are
  untested.
- How much of the 80% of UVM projects is reachable at all (open-source tool use,
  willingness to add a Python step)? There's no data; G3 is the real test.
- Should fw-\* weavers ship with fw-hdl (handoff Q1)? This survey says yes. fw-\* is
  a committed user, not a market to position for.
