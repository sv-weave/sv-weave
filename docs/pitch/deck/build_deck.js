// Builds docs/pitch/sv-weave-pitch.pptx, the engineer-facing pitch deck.
//
// Needs pptxgenjs, react, react-dom, react-icons and sharp on NODE_PATH, and the
// pptx skill's apply_theme.js (APPLY_THEME env var, or the default path below).
//   NODE_PATH=<node_modules> node docs/pitch/deck/build_deck.js
const path = require("path");
const pptxgen = require("pptxgenjs");
const React = require("react");
const ReactDOMServer = require("react-dom/server");
const sharp = require("sharp");
const fa = require("react-icons/fa");
const { applyTheme } = require(process.env.APPLY_THEME ||
  path.join(process.env.HOME, ".claude/skills/synced/6d728707-72ff-4419-898e-2cd09cf1cbd3_06d217cb-44af-47d0-a704-8dc8adfa1f27/pptx/scripts/apply_theme.js"));

const OUT = path.join(__dirname, "..", "sv-weave-pitch.pptx");

const THEME = {
  name: "sv-weave",
  headFontFace: "Cambria",
  bodyFontFace: "Calibri",
  colors: {
    dk1: "1B1F3B", lt1: "FFFFFF", dk2: "3A4070", lt2: "F1F2F7",
    accent1: "E07A2F", accent2: "2F9C8C", accent3: "9DA3C9", accent4: "C94F4F",
    accent5: "5B6170", accent6: "F2C14E", hlink: "2F9C8C", folHlink: "9DA3C9",
  },
};
const CODE_FONT = "Courier New";

async function icon(Comp, color = "#FFFFFF") {
  const svg = ReactDOMServer.renderToStaticMarkup(React.createElement(Comp, { color, size: "256" }));
  const buf = await sharp(Buffer.from(svg)).resize(256, 256).png().toBuffer();
  return "image/png;base64," + buf.toString("base64");
}

async function main() {
  const pres = new pptxgen();
  pres.layout = "LAYOUT_16x9"; // 10 x 5.625
  pres.title = "sv-weave: write the class you meant to write";
  pres.author = "sv-weave";
  pres.theme = { headFontFace: THEME.headFontFace, bodyFontFace: THEME.bodyFontFace };
  const C = pres.SchemeColor;
  const S = pres.shapes;

  // ---- Layouts ----
  pres.defineSlideMaster({
    title: "DARK",
    background: { color: C.text1 },
    objects: [],
  });
  pres.defineSlideMaster({
    title: "CONTENT",
    background: { color: C.background1 },
    objects: [
      { text: { text: "sv-weave", options: { x: 0.5, y: 5.2, w: 3, h: 0.3, fontSize: 10, color: C.accent5, isTextBox: true, margin: 0 } } },
      { placeholder: { options: { name: "title", type: "title", x: 0.5, y: 0.3, w: 9, h: 0.75,
          fontSize: 32, bold: true, color: C.text1, fontFace: THEME.headFontFace, valign: "middle", margin: 0 }, text: "" } },
    ],
    slideNumber: { x: 9.0, y: 5.2, w: 0.5, h: 0.3, fontSize: 10, color: C.accent5, align: "right" },
  });

  const content = (section, title) => {
    const s = pres.addSlide({ masterName: "CONTENT", sectionTitle: section });
    s.addText(title, { placeholder: "title" });
    return s;
  };

  // ---- Helpers ----
  const codePanel = (s, x, y, w, h, lines, name, fontSize = 11) => {
    s.addShape(S.ROUNDED_RECTANGLE, { x, y, w, h, fill: { color: C.text1 }, rectRadius: 0.08, objectName: name + " panel" });
    const runs = lines.map((ln, i) => {
      const isComment = /^\s*(\/\/|#)/.test(ln);
      const ci = ln.indexOf("//");
      const last = i === lines.length - 1;
      if (!isComment && ci > 0) {
        return [
          { text: ln.slice(0, ci), options: { color: C.background1 } },
          { text: ln.slice(ci), options: { color: C.accent6, breakLine: !last } },
        ];
      }
      return [{ text: ln === "" ? " " : ln, options: { color: isComment ? C.accent6 : C.background1, breakLine: !last } }];
    }).flat();
    s.addText(runs, { x: x + 0.15, y: y + 0.12, w: w - 0.3, h: h - 0.24, fontFace: CODE_FONT, fontSize,
      valign: "top", margin: 0, isTextBox: true, objectName: name + " code" });
  };
  const iconCircle = (s, img, x, y, d, fill, name) => {
    s.addShape(S.OVAL, { x, y, w: d, h: d, fill: { color: fill }, line: { color: fill }, objectName: name + " circle" });
    const pad = d * 0.25;
    s.addImage({ data: img, x: x + pad, y: y + pad, w: d - 2 * pad, h: d - 2 * pad, altText: name, objectName: name + " icon" });
  };
  const card = (s, x, y, w, h, name, fill = C.background2) =>
    s.addShape(S.ROUNDED_RECTANGLE, { x, y, w, h, fill: { color: fill }, line: { color: fill }, rectRadius: 0.1, objectName: name });
  const bullets = (items, opts = {}) => items.map((t, i) => ({
    text: t, options: { bullet: true, breakLine: i < items.length - 1, paraSpaceAfter: 4, ...opts },
  }));

  const I = {
    weave: await icon(fa.FaLayerGroup),
    macro: await icon(fa.FaCode),
    hand: await icon(fa.FaKeyboard),
    yaml: await icon(fa.FaFileAlt),
    read: await icon(fa.FaSearch),
    gen: await icon(fa.FaCogs),
    check: await icon(fa.FaCheckCircle),
    swap: await icon(fa.FaExchangeAlt),
    producer: await icon(fa.FaUserCog),
    consumers: await icon(fa.FaUsers),
    filter: await icon(fa.FaFilter),
    plug: await icon(fa.FaPlug),
    tag: await icon(fa.FaTag),
    shield: await icon(fa.FaShieldAlt),
    moon: await icon(fa.FaMoon),
    redo: await icon(fa.FaRedo),
    bug: await icon(fa.FaBug),
    build: await icon(fa.FaCubes),
    list: await icon(fa.FaListUl),
    chart: await icon(fa.FaChartBar),
    py: await icon(fa.FaPython),
    box: await icon(fa.FaBoxOpen),
    book: await icon(fa.FaBook),
    flow: await icon(fa.FaStream),
    eraser: await icon(fa.FaEraser),
    brain: await icon(fa.FaLightbulb),
  };

  // ---- 1. Title ----
  pres.addSection({ title: "Intro" });
  {
    const s = pres.addSlide({ masterName: "DARK", sectionTitle: "Intro" });
    s.addText("sv-weave", { x: 0.6, y: 1.3, w: 6, h: 1.0, fontFace: THEME.headFontFace, fontSize: 54, bold: true,
      color: C.background1, margin: 0, isTextBox: true, objectName: "Title" });
    s.addText("Write the class you meant to write.", { x: 0.6, y: 2.35, w: 6.2, h: 0.6, fontSize: 24,
      color: C.accent1, margin: 0, isTextBox: true, objectName: "Subtitle" });
    s.addText("Factory weaving for SystemVerilog class libraries", { x: 0.6, y: 3.0, w: 6.2, h: 0.4, fontSize: 16,
      italic: true, color: C.accent3, margin: 0, isTextBox: true, objectName: "Tagline" });
    iconCircle(s, I.weave, 7.2, 1.35, 2.0, C.accent1, "Weave");
    s.addNotes("sv-weave lets engineers write plain SystemVerilog classes and get expert-quality implementations of the library hooks generated for them. The pitch in one line: only the people who build the library learn the generator; everyone else just gets better components.");
  }

  // ---- 2. Problem ----
  pres.addSection({ title: "Problem" });
  {
    const s = content("Problem", "Today's options all leak expertise");
    const cols = [
      ["Field macros", I.macro, ["Slow at run time", "Opaque in the debugger", "Behaviour hidden in macros"]],
      ["Hand-written hooks", I.hand, ["~40 lines per class", "Drift when fields change", "Silent scoreboard holes"]],
      ["YAML generators", I.yaml, ["Two sources of truth", "A generator to maintain", "Generated + hand code to merge"]],
    ];
    cols.forEach(([head, img, items], i) => {
      const x = 0.5 + i * 3.08;
      card(s, x, 1.25, 2.84, 2.75, head + " card");
      iconCircle(s, img, x + 0.25, 1.45, 0.6, C.accent4, head);
      s.addText(head, { x: x + 1.0, y: 1.45, w: 1.75, h: 0.6, fontSize: 17, bold: true, color: C.text1,
        valign: "middle", margin: 0, isTextBox: true, objectName: head + " heading" });
      s.addText(bullets(items), { x: x + 0.25, y: 2.25, w: 2.45, h: 1.6, fontSize: 14, color: C.text1,
        valign: "top", margin: 0, isTextBox: true, objectName: head + " points" });
    });
    card(s, 0.5, 4.2, 9.0, 0.75, "Takeaway", C.text1);
    s.addText([
      { text: "Common failure: ", options: { bold: true, color: C.accent1 } },
      { text: "every class author has to learn the mechanism.", options: { color: C.background1 } },
    ], { x: 0.75, y: 4.2, w: 8.5, h: 0.75, fontSize: 18, valign: "middle", margin: 0, isTextBox: true, objectName: "Takeaway text" });
    s.addNotes("Three ways teams avoid boilerplate today. Macros cost run time and hide behaviour. Hand-written hooks drift: add a field, forget do_compare, and the scoreboard silently stops checking it. YAML generators create a second source of truth and a merge problem. The common failure: the expertise is spread across everyone who writes a class.");
  }

  // ---- 3. Before / after ----
  {
    const s = content("Problem", "Write the class you meant to write");
    const before = [
      "class bus_tx extends uvm_sequence_item;",
      "  rand bit [31:0] addr;",
      "  rand bit [31:0] data;",
      "  rand bit [7:0]  payload[];",
      "  `uvm_object_utils_begin(bus_tx)",
      "    `uvm_field_int(addr, UVM_ALL_ON)",
      "    `uvm_field_int(data, UVM_ALL_ON)",
      "    `uvm_field_array_int(payload,",
      "                         UVM_ALL_ON)",
      "  `uvm_object_utils_end",
      "endclass",
    ];
    const after = [
      "class bus_tx extends uvm_sequence_item;",
      "  `uvm_object_utils(bus_tx)",
      "  rand bit [31:0] addr;",
      "  rand bit [31:0] data;",
      "  rand bit [7:0]  payload[];",
      "  (* weave_nocopy *) int n_retries;",
      "endclass",
      "",
      "// copy, compare, print: generated",
      "// add a field -> it's handled",
    ];
    s.addText("Before: field macros", { x: 0.5, y: 1.2, w: 4.4, h: 0.35, fontSize: 14, bold: true, color: C.accent4, margin: 0, isTextBox: true, objectName: "Before label" });
    s.addText("After: sv-weave", { x: 5.1, y: 1.2, w: 4.4, h: 0.35, fontSize: 14, bold: true, color: C.accent2, margin: 0, isTextBox: true, objectName: "After label" });
    codePanel(s, 0.5, 1.6, 4.4, 2.75, before, "Before", 11);
    codePanel(s, 5.1, 1.6, 4.4, 2.75, after, "After", 11);
    s.addText("Plain fields. Attributes only where you want something other than the default.", {
      x: 0.5, y: 4.5, w: 9, h: 0.5, fontSize: 15, italic: true, color: C.text2, margin: 0, isTextBox: true, objectName: "Caption" });
    s.addNotes("Left: the macro version everyone has written. Right: the class you meant to write. No field macros, no hand-written do_copy. An attribute such as weave_nocopy is the only thing a consumer ever adds. Add a field six months from now and it is copied, compared and printed on the next build.");
  }

  // ---- 4. How it works ----
  pres.addSection({ title: "How it works" });
  {
    const s = content("How it works", "How it works");
    const steps = [
      ["Read", I.read, "slang parses your real sources. No second description."],
      ["Weave", I.gen, "Weavers generate a subclass that implements the library's hooks."],
      ["Verify", I.check, "slang elaborates the generated code with your design."],
      ["Substitute", I.swap, "The library's own factory hands out the woven class."],
    ];
    steps.forEach(([head, img, desc], i) => {
      const x = 0.5 + i * 2.3;
      iconCircle(s, img, x + 0.6, 1.35, 0.85, i === 3 ? C.accent2 : C.accent1, head);
      if (i < 3) s.addShape(S.RIGHT_ARROW, { x: x + 1.65, y: 1.6, w: 0.55, h: 0.35, fill: { color: C.accent3 }, line: { color: C.accent3 }, objectName: "Arrow " + (i + 1) });
      s.addText(`${i + 1}. ${head}`, { x, y: 2.35, w: 2.05, h: 0.4, fontSize: 18, bold: true, color: C.text1, align: "center", margin: 0, isTextBox: true, objectName: head + " heading" });
      s.addText(desc, { x, y: 2.8, w: 2.05, h: 1.0, fontSize: 14, color: C.text1, align: "center", valign: "top", margin: 0, isTextBox: true, objectName: head + " text" });
    });
    card(s, 0.5, 4.05, 9.0, 0.85, "Guarantees");
    s.addText("Your source is never edited. Your code never names generated code. Generator errors point at the weaver, not at a 3-hour regression.", {
      x: 0.75, y: 4.05, w: 8.5, h: 0.85, fontSize: 15, color: C.text1, valign: "middle", margin: 0, isTextBox: true, objectName: "Guarantees text" });
    s.addNotes("Four stages. slang reads the real sources. Weavers generate a subclass of each matching class that implements the library hooks for exactly its fields. Before anything is written, slang elaborates the generated code together with the design, and errors are attributed to the weaver that produced the line. Then the library's own factory, the mechanism UVM already has, hands out the woven class wherever the original is created. Overrides still resolve as before.");
  }

  // ---- 5. Producers vs consumers ----
  {
    const s = content("How it works", "Only producers learn the generator");
    const sides = [
      [0.5, "Producers", I.producer, C.accent1, "Methodology team, VIP and protocol-package authors",
        ["Write weavers (Python) and base classes", "Encode how copy, compare, build, ... should work", "Fix once; every consumer gets it"]],
      [5.7, "Consumers", I.consumers, C.accent2, "Testbench and test writers: most of the team",
        ["Write ordinary SV classes", "Add an attribute when the default isn't right", "Learn nothing new"]],
    ];
    sides.forEach(([x, head, img, col, who, items]) => {
      card(s, x, 1.25, 3.8, 3.65, head + " card");
      iconCircle(s, img, x + 0.25, 1.45, 0.7, col, head);
      s.addText(head, { x: x + 1.1, y: 1.45, w: 2.5, h: 0.4, fontSize: 20, bold: true, color: C.text1, margin: 0, isTextBox: true, objectName: head + " heading" });
      s.addText(who, { x: x + 1.1, y: 1.85, w: 2.55, h: 0.55, fontSize: 12, italic: true, color: C.accent5, valign: "top", margin: 0, isTextBox: true, objectName: head + " who" });
      s.addText(bullets(items), { x: x + 0.25, y: 2.6, w: 3.35, h: 2.1, fontSize: 15, color: C.text1, valign: "top", margin: 0, isTextBox: true, objectName: head + " points" });
    });
    s.addShape(S.RIGHT_ARROW, { x: 4.45, y: 2.6, w: 1.1, h: 0.6, fill: { color: C.accent1 }, line: { color: C.accent1 }, objectName: "Flow arrow" });
    s.addText("expertise, once", { x: 4.35, y: 3.3, w: 1.3, h: 0.6, fontSize: 12, bold: true, color: C.accent1, align: "center", margin: 0, isTextBox: true, objectName: "Flow label" });
    s.addNotes("The key point. Producers, the people who own the library, learn the generator and put their expertise into weavers once. Consumers write ordinary classes and get correct, fast, consistent implementations. A library now ships with its generator: improve a weaver and every testbench that uses the library gets the change on its next build, with no change to consumer code.");
  }

  // ---- 6. A weaver ----
  {
    const s = content("How it works", "A weaver is a few lines of Python");
    const code = [
      "class PrintFields(plugin.Weaver):",
      "    name = \"print-fields\"",
      "",
      "    def subscribe(self, bus):",
      "        bus.on(extends_root(), self.weave)",
      "",
      "    def weave(self, w):",
      "        p = w.feature(\"print\")",
      "        for f in w.fields():",
      "            if f.static or not w.sv.accessible(f):",
      "                continue",
      "            p.body.add(...)  # one line per field",
    ];
    codePanel(s, 0.5, 1.25, 5.3, 3.65, code, "Weaver", 11.5);
    const pts = [
      [I.filter, "Subscribes by pattern", "Base class, package, name or attribute."],
      [I.plug, "Targets features, not methods", "One copy weaver works with every binding."],
      [I.tag, "Consumers see attributes", "weave_nocopy, weave_deep, weave_off"],
    ];
    pts.forEach(([img, head, desc], i) => {
      const y = 1.3 + i * 1.22;
      iconCircle(s, img, 6.1, y, 0.6, C.accent1, head);
      s.addText(head, { x: 6.85, y, w: 2.65, h: 0.35, fontSize: 15, bold: true, color: C.text1, margin: 0, isTextBox: true, objectName: head + " heading" });
      s.addText(desc, { x: 6.85, y: y + 0.38, w: 2.65, h: 0.6, fontSize: 13, color: C.accent5, valign: "top", margin: 0, isTextBox: true, objectName: head + " text" });
    });
    s.addNotes("This is a complete weaver from the quickstart. It subscribes to every class under the binding's root, and contributes one line per field to the print feature. Weavers contribute to features such as copy or print, never to a library's method by name, so the binding maps them onto do_copy for UVM or onto another library's hook. Consumers never see this code; they see attributes.");
  }

  // ---- 7. Comparison table ----
  pres.addSection({ title: "Why it matters" });
  {
    const s = content("Why it matters", "Faster, and it stays correct");
    const good = { color: C.accent2, bold: true }, bad = { color: C.accent4, bold: true };
    const hdr = (t) => ({ text: t, options: { bold: true, color: C.background1, fill: { color: C.text1 }, align: "center" } });
    const cell = (t, o) => ({ text: t, options: { ...o, align: "center" } });
    const rowHead = (t) => ({ text: t, options: { bold: true, color: C.text1, fill: { color: C.background2 } } });
    const rows = [
      [{ text: "", options: { fill: { color: C.text1 } } }, hdr("Field macros"), hdr("Hand-written"), hdr("sv-weave")],
      [rowHead("Run-time cost"), cell("High", bad), cell("Low", good), cell("Low", good)],
      [rowHead("Stays in step with fields"), cell("Yes", good), cell("No", bad), cell("Yes", good)],
      [rowHead("Readable in the debugger"), cell("No", bad), cell("Yes", good), cell("Yes", good)],
      [rowHead("Lines per class"), cell("1 per field", { color: C.text1 }), cell("~40", bad), cell("0", good)],
      [rowHead("Who must know the mechanism"), cell("Everyone", bad), cell("Everyone", bad), cell("Library owners", good)],
    ];
    s.addTable(rows, { x: 0.5, y: 1.3, w: 9.0, colW: [3.0, 2.0, 2.0, 2.0], rowH: 0.52, fontSize: 15,
      fontFace: THEME.bodyFontFace, valign: "middle", border: { type: "solid", pt: 1, color: "FFFFFF" }, objectName: "Comparison" });
    s.addText("Woven code is plain field-by-field SV: what an expert writes by hand, generated for every class.", {
      x: 0.5, y: 4.55, w: 9, h: 0.4, fontSize: 14, italic: true, color: C.accent5, margin: 0, isTextBox: true, objectName: "Caption" });
    s.addNotes("Woven code is performance-neutral to hand-written hooks and faster than field macros, because it is the same plain field-by-field code an expert would write. Unlike hand-written hooks, it never drifts from the fields. And only the library owners need to know how it works.");
  }

  // ---- 8. Profiles ----
  {
    const s = content("Why it matters", "Release and debug from one source");
    const yaml = [
      "profiles:",
      "  release: [core]",
      "  debug:   [core, \"debug.*\"]",
      "weavers:",
      "- {name: copy}",
      "- {name: compare}",
      "- {name: xcheck, set: debug.xcheck}",
      "- {name: trace,  set: debug.trace}",
    ];
    codePanel(s, 0.5, 1.25, 4.4, 2.65, yaml, "Profiles", 12);
    s.addText("Both built side by side; chosen at run time with +weave_profile=debug", {
      x: 0.5, y: 4.05, w: 4.4, h: 0.8, fontSize: 13, italic: true, color: C.accent5, valign: "top", margin: 0, isTextBox: true, objectName: "Profiles caption" });
    card(s, 5.2, 1.25, 4.3, 3.65, "Rules card");
    iconCircle(s, I.shield, 5.45, 1.45, 0.65, C.accent2, "Rand safety");
    s.addText("Debug sets cannot change your stimulus", { x: 6.25, y: 1.45, w: 3.1, h: 0.65, fontSize: 15, bold: true, color: C.text1, valign: "middle", margin: 0, isTextBox: true, objectName: "Rules heading" });
    s.addText(bullets([
      "No rand fields or constraints",
      "No randomize() calls",
      "No threads or delays",
      "Every debug fragment runs inside an RNG fence",
    ]), { x: 5.45, y: 2.3, w: 3.85, h: 1.7, fontSize: 14, color: C.text1, valign: "top", margin: 0, isTextBox: true, objectName: "Rules list" });
    s.addText("Enforced by the tool, not by convention.", { x: 5.45, y: 4.2, w: 3.85, h: 0.5, fontSize: 14, bold: true, italic: true, color: C.accent2, margin: 0, isTextBox: true, objectName: "Rules footer" });
    s.addNotes("Weavers belong to extension sets; profiles are lists of sets. Release and debug are generated side by side and selected at run time. Non-core sets are checked: they cannot add rand fields, call randomize, fork or add delays, and each debug fragment is wrapped in an RNG fence that saves and restores the thread's random state, so even library calls that allocate don't shift seeds.");
  }

  // ---- 9. Replay ----
  {
    const s = content("Why it matters", "Replay a failing seed with full debug");
    const steps = [
      [I.moon, C.accent4, "Overnight", "Seed 1234 fails in the release regression."],
      [I.redo, C.accent1, "Morning", "Rerun seed 1234 with +weave_profile=debug."],
      [I.bug, C.accent2, "Same failure", "Same stimulus, with X-checks, tracing and recording on."],
    ];
    steps.forEach(([img, col, head, desc], i) => {
      const x = 0.5 + i * 3.1;
      iconCircle(s, img, x + 0.95, 1.3, 0.9, col, head);
      if (i < 2) s.addShape(S.RIGHT_ARROW, { x: x + 2.25, y: 1.55, w: 0.6, h: 0.4, fill: { color: C.accent3 }, line: { color: C.accent3 }, objectName: "Arrow " + (i + 1) });
      s.addText(head, { x, y: 2.35, w: 2.8, h: 0.4, fontSize: 18, bold: true, color: C.text1, align: "center", margin: 0, isTextBox: true, objectName: head + " heading" });
      s.addText(desc, { x: x + 0.15, y: 2.8, w: 2.5, h: 0.75, fontSize: 14, color: C.text1, align: "center", valign: "top", margin: 0, isTextBox: true, objectName: head + " text" });
    });
    codePanel(s, 0.5, 3.9, 9.0, 0.85, [
      "simv +UVM_TESTNAME=smoke +ntb_random_seed=1234                       // release",
      "simv +UVM_TESTNAME=smoke +ntb_random_seed=1234 +weave_profile=debug  // same stimulus",
    ], "Commands", 11);
    s.addNotes("This is the workflow regressions have always wanted. Because the debug profile is guaranteed not to perturb randomization, the exact failing seed can be rerun with every check turned on, and it reproduces the same stimulus. No source change, no rebuild of the testbench code.");
  }

  // ---- 10. Bindings ----
  pres.addSection({ title: "Reach" });
  {
    const s = content("Reach", "Not just UVM");
    const col = (x, head, items, fill, txt) => {
      s.addText(head, { x, y: 1.2, w: 2.6, h: 0.4, fontSize: 16, bold: true, color: C.text1, align: "center", margin: 0, isTextBox: true, objectName: head + " heading" });
      items.forEach((t, i) => {
        const y = 1.7 + i * 0.58;
        s.addShape(S.ROUNDED_RECTANGLE, { x, y, w: 2.6, h: 0.46, fill: { color: fill }, line: { color: fill }, rectRadius: 0.08, objectName: head + " box " + (i + 1) });
        s.addText(t, { x, y, w: 2.6, h: 0.46, fontSize: 14, color: txt, align: "center", valign: "middle", margin: 0, isTextBox: true, objectName: head + " label " + (i + 1) });
      });
    };
    col(0.5, "Weavers", ["copy", "compare", "print", "xcheck", "your own"], C.accent1, C.background1);
    col(3.7, "Features", ["copy", "compare", "print", "pack", "post_build"], C.background2, C.text1);
    col(6.9, "Bindings", ["UVM 1.2", "IEEE 1800.2", "In-house library", "fw-hdl classes"], C.accent2, C.background1);
    [3.15, 6.35].forEach((x, i) => s.addShape(S.RIGHT_ARROW, { x, y: 2.9, w: 0.5, h: 0.4, fill: { color: C.accent3 }, line: { color: C.accent3 }, objectName: "Map arrow " + (i + 1) }));
    s.addText("Written once, against features. A binding maps each feature to one library's hook and factory.", {
      x: 0.5, y: 4.65, w: 9, h: 0.4, fontSize: 13, italic: true, color: C.accent5, margin: 0, isTextBox: true, objectName: "Caption" });
    s.addNotes("Weavers contribute to features, which a binding defines. The binding maps each feature to one library's hook, for example copy to do_copy with a cast in UVM, and says how woven classes register with that library's factory. So a copy weaver works for UVM, for an in-house library, or for synthesizable class code on the fw-hdl path. UVM version differences live in the binding, not in consumer code.");
  }

  // ---- 11. What's next ----
  {
    const s = content("Reach", "What's next: SV introspection");
    s.addText("SystemVerilog has no reflection. Weavers can query the whole design, and the same model can drive outputs beyond SV.", {
      x: 0.5, y: 1.15, w: 9, h: 0.55, fontSize: 14, color: C.accent5, margin: 0, isTextBox: true, objectName: "Intro" });
    const items = [
      [I.build, "Component construction", "build_phase and connections from declared handles"],
      [I.list, "Registries", "Every sequence and test, found automatically"],
      [I.chart, "Coverage", "Bins from what your constraints can reach"],
      [I.py, "Language mirrors", "Python and C++ types for cocotb and DPI"],
      [I.box, "Protocol packages", "Ship base classes with their weavers"],
      [I.book, "Docs and schemas", "Transaction docs, recording schemas"],
    ];
    items.forEach(([img, head, desc], i) => {
      const x = 0.5 + (i % 3) * 3.08, y = 1.85 + Math.floor(i / 3) * 1.6;
      card(s, x, y, 2.84, 1.4, head + " card");
      iconCircle(s, img, x + 0.2, y + 0.2, 0.55, C.accent1, head);
      s.addText(head, { x: x + 0.9, y: y + 0.2, w: 1.85, h: 0.55, fontSize: 14, bold: true, color: C.text1, valign: "middle", margin: 0, isTextBox: true, objectName: head + " heading" });
      s.addText(desc, { x: x + 0.2, y: y + 0.82, w: 2.5, h: 0.5, fontSize: 12, color: C.accent5, valign: "top", margin: 0, isTextBox: true, objectName: head + " text" });
    });
    s.addNotes("Where this goes next. Because weavers can query the whole design, they can generate code about sets of classes, such as registries and selectors. And because the model is an SV-introspection pipeline, the same classes can drive coverage whose bins come from constraint reachability, Python and C++ mirrors, regression lists and documentation. Each is a weaver or emitter a producer writes once.");
  }

  // ---- 12. Adoption ----
  pres.addSection({ title: "Getting started" });
  {
    const s = content("Getting started", "Adopt it one class at a time");
    const steps = [
      [I.flow, "Add the weave task", "One svweave.Weave task in your dv-flow, next to compilation."],
      [I.eraser, "Drop boilerplate", "Remove field macros class by class. Existing hand-written hooks keep working."],
      [I.brain, "Move expertise into weavers", "Library owners turn conventions into weavers, once."],
    ];
    steps.forEach(([img, head, desc], i) => {
      const y = 1.3 + i * 1.2;
      card(s, 0.5, y, 9.0, 1.0, head + " card");
      s.addText(String(i + 1), { x: 0.7, y: y + 0.15, w: 0.7, h: 0.7, fontSize: 32, bold: true, color: C.accent1, fontFace: THEME.headFontFace, align: "center", valign: "middle", margin: 0, isTextBox: true, objectName: head + " number" });
      iconCircle(s, img, 1.55, y + 0.2, 0.6, C.accent2, head);
      s.addText(head, { x: 2.4, y: y + 0.12, w: 6.9, h: 0.38, fontSize: 17, bold: true, color: C.text1, margin: 0, isTextBox: true, objectName: head + " heading" });
      s.addText(desc, { x: 2.4, y: y + 0.5, w: 6.9, h: 0.4, fontSize: 14, color: C.accent5, margin: 0, isTextBox: true, objectName: head + " text" });
    });
    s.addNotes("Adoption is incremental. Add the weave task to the flow. Remove field macros one class at a time; woven code runs after super, so classes with hand-written hooks keep working. Then library owners move the team's conventions into weavers.");
  }

  // ---- 13. Close ----
  {
    const s = pres.addSlide({ masterName: "DARK", sectionTitle: "Getting started" });
    s.addText("Write the class you meant to write.", { x: 0.6, y: 1.2, w: 8.8, h: 0.9, fontFace: THEME.headFontFace, fontSize: 36, bold: true, color: C.background1, margin: 0, isTextBox: true, objectName: "Close title" });
    s.addText("Let the people who know the library make it right: once, for everyone.", { x: 0.6, y: 2.1, w: 8.8, h: 0.6, fontSize: 20, color: C.accent1, margin: 0, isTextBox: true, objectName: "Close subtitle" });
    s.addText([
      { text: "Start here", options: { bold: true, color: C.background1, breakLine: true } },
      { text: "Quickstart: docs/quickstart.rst, examples/quickstart/", options: { color: C.accent3, breakLine: true } },
      { text: "Class writers: docs/user/attributes.rst", options: { color: C.accent3, breakLine: true } },
      { text: "Library owners: docs/authoring/weavers.rst, bindings.rst", options: { color: C.accent3 } },
    ], { x: 0.6, y: 3.1, w: 8.8, h: 1.5, fontSize: 15, valign: "top", paraSpaceAfter: 4, margin: 0, isTextBox: true, objectName: "Start here" });
    s.addNotes("Close on the one-liner. Point class writers at the attributes page and library owners at the weaver and binding authoring guides.");
  }

  await pres.writeFile({ fileName: OUT });
  await applyTheme(OUT, THEME);
  console.log("wrote", OUT);
}

main().catch((e) => { console.error(e); process.exit(1); });
