"""``run(config)``: the whole pipeline (design §3). The CLI and the dv-flow task are
thin wrappers around it."""
import dataclasses as dc
import hashlib
import json
import os
import shutil
import time
from typing import Dict, List, Optional, Sequence, Tuple

from . import plugin
from .__version__ import __version__
from .bus import Bus
from .check import check
from .config import Config
from .diag import Diag, Severity, SvWeaveError
from .filelist import SourceSpec
from .frontend.loader import Loaded, load
from .frontend.model import SvModel, build_model
from .render import (INIT_FILE, INIT_STUB_NAME, RenderedFile, content_key, init_stub,
                     register_items, render_init, render_package)
from .report import build_manifest, manifest_text, render_report
from .select import Selection, select
from .weave.design import GEN_PKG, gen_package_cycles
from .weave.model import WovenClass, WovenPackage
from .verify import FAILED_DIR, verify as verify_stage
from .write import MANIFEST, write_if_changed, write_outputs

REPORT = "weave-report.md"
WOVEN_FILELIST = "sv_weave.f"
RUNTIME_FILELIST = "sv_weave_rt.f"


@dc.dataclass
class RunResult:
    cfg: Config
    out_dir: str
    loaded: Optional[Loaded] = None
    model: Optional[SvModel] = None
    selection: Optional[Selection] = None
    woven: List[WovenClass] = dc.field(default_factory=list)
    packages: List[WovenPackage] = dc.field(default_factory=list)
    rendered: List[RenderedFile] = dc.field(default_factory=list)
    extra_files: Dict[str, str] = dc.field(default_factory=dict)
    runtime_files: List[str] = dc.field(default_factory=list)
    generated_names: List[str] = dc.field(default_factory=list)
    compile_order: List[str] = dc.field(default_factory=list)
    changed: List[str] = dc.field(default_factory=list)
    diags: List[Diag] = dc.field(default_factory=list)
    plugin_versions: Dict[str, str] = dc.field(default_factory=dict)
    input_hash: str = ""
    output_hash: str = ""
    verify_status: str = "not run"
    verified: Optional[Dict] = None
    manifest: Dict = dc.field(default_factory=dict)
    timings: Dict[str, float] = dc.field(default_factory=dict)

    def file(self, name: str) -> Optional[RenderedFile]:
        for r in self.rendered:
            if r.name == name:
                return r
        return None

    @property
    def woven_files(self) -> List[str]:
        """Generated SV files, in compile order (absolute paths)."""
        return [os.path.join(self.out_dir, n) for n in self.compile_order]


def _hash(parts: Sequence[Tuple[str, str]]) -> str:
    h = hashlib.sha256()
    for name, text in parts:
        h.update(name.encode())
        h.update(b"\0")
        h.update(text.encode())
        h.update(b"\0")
    return h.hexdigest()


def _input_hash(spec: SourceSpec, texts, cfg: Config, plugins: Dict[str, str]) -> str:
    parts = []
    for f in spec.files:
        with open(f) as fp:
            parts.append((f, fp.read()))
    parts.extend(texts)
    parts.append(("incdirs", json.dumps(spec.incdirs)))
    parts.append(("defines", json.dumps(spec.defines, sort_keys=True)))
    parts.append(("tops", json.dumps(spec.tops)))
    parts.append(("config", cfg.model_dump_json(by_alias=True)))
    parts.append(("plugins", json.dumps(plugins, sort_keys=True)))
    parts.append(("sv-weave", __version__))
    return _hash(parts)


def _dedup(diags: List[Diag]) -> List[Diag]:
    seen, out = set(), []
    for d in diags:
        if d not in seen:
            seen.add(d)
            out.append(d)
    return out


def _stop(diags: List[Diag], summary: str):
    errs = [d for d in diags if d.severity == Severity.ERROR]
    if errs:
        raise SvWeaveError(errs, summary)


def _previous_manifest(out_dir: str) -> Optional[dict]:
    try:
        with open(os.path.join(out_dir, MANIFEST)) as fp:
            return json.load(fp)
    except (OSError, ValueError):
        return None


class _Timer:
    def __init__(self, res: "RunResult", stage: str):
        self.res, self.stage = res, stage

    def __enter__(self):
        self.t0 = time.perf_counter()

    def __exit__(self, *exc):
        self.res.timings[self.stage] = time.perf_counter() - self.t0


def run(cfg: Config, spec: Optional[SourceSpec] = None, texts: Sequence[Tuple[str, str]] = (),
        out_dir: Optional[str] = None, write: bool = True,
        add_runtime: bool = True, verify: Optional[str] = None) -> RunResult:
    """Runs the pipeline. ``spec`` adds sources to the config's own; ``texts`` adds
    in-memory ``(name, text)`` sources (tests); ``verify`` overrides the config's
    level. Raises SvWeaveError on any error."""
    out_dir = os.path.abspath(out_dir or cfg.resolve(cfg.out_dir))
    res = RunResult(cfg, out_dir)
    level = verify or cfg.verify
    if level not in ("full", "syntax", "off"):
        raise SvWeaveError([Diag(Severity.ERROR, "unknown verify level '%s' (full, syntax, off)"
                                 % level)])

    # Plugins first: bindings may add library sources (sv_runtime_files).
    if not cfg.bindings:
        raise SvWeaveError([Diag(Severity.ERROR, "no binding configured: set 'binding:' in "
                                 "sv-weave.yaml (sv-weave has no built-in binding)")])
    bindings = {}
    for name in cfg.bindings:
        b = plugin.find(plugin.BINDING_GROUP, name, cfg.plugin_dirs())()
        bindings[b.name] = b
        res.plugin_versions["binding:" + b.name] = b.version
    bus = Bus()
    for i, wcfg in enumerate(cfg.weavers):
        wcls = plugin.find(plugin.WEAVER_GROUP, wcfg.name, cfg.plugin_dirs())
        res.plugin_versions["weaver:" + wcls.name] = wcls.version
        bus.subscribe(wcls(wcfg.options), wcfg.set,
                      wcfg.order if wcfg.order is not None else wcls.order, wcfg.match,
                      where="weavers[%d].match" % i, before=wcfg.before, after=wcfg.after)

    # 1-2. Load and model.
    full = cfg.source_spec()
    if spec is not None:
        full.extend(spec)
    rt: List[str] = []
    for b in bindings.values():
        rt.extend(f for f in b.sv_runtime_files() if f not in rt)
    res.runtime_files = rt
    if add_runtime:
        user_names = {os.path.basename(f) for f in full.files}
        full.files[:0] = [f for f in rt if os.path.basename(f) not in user_names]
    res.input_hash = _input_hash(full, texts, cfg, res.plugin_versions)
    load_texts = list(texts)
    if INIT_FILE not in {os.path.basename(f) for f in full.files}:
        load_texts.append((INIT_STUB_NAME, init_stub()))
    with _Timer(res, "load"):
        res.loaded = load(full, load_texts)
    with _Timer(res, "model"):
        res.model = build_model(res.loaded)

    # 3. Select.
    res.selection = select(res.model, cfg, list(bindings.values()), wanted=bus.wanted)
    res.diags.extend(res.selection.diags)

    # 4. Weave.
    aggregates: Dict = {}
    woven, diags = bus.dispatch(res.selection.targets, cfg.build_profiles, cfg.profile_sets,
                                bindings, cfg, res.model, aggregates)
    res.diags = _dedup(res.diags + diags)
    _stop(res.diags, "weaving failed")
    t_order = {id(t.cls): i for i, t in enumerate(res.selection.targets)}
    p_order = {p: i for i, p in enumerate(cfg.build_profiles)}
    woven.sort(key=lambda wc: (t_order[id(wc.cls)], p_order[wc.profile]))
    res.woven = woven

    # 5. Check.
    res.diags = _dedup(res.diags + check(woven, cfg))
    _stop(res.diags, "check failed")

    # Deduplicate: a woven class identical to one already kept for an earlier profile
    # is dropped, and the kept one is registered for both profiles.
    kept: List[WovenClass] = []
    seen: Dict[Tuple[int, str], WovenClass] = {}
    for wc in woven:
        key = (id(wc.cls), content_key(wc))
        if key in seen:
            seen[key].also_profiles.append(wc.profile)
        else:
            seen[key] = wc
            kept.append(wc)
    woven = res.woven = kept

    # Group into packages, in model package order; design-handler code (aggregates)
    # joins its package, or sv_weave_gen_pkg when woven packages would import each
    # other in a cycle.
    def new_pkg(name: str, user_pkg: Optional[str]) -> WovenPackage:
        imports = [user_pkg] if user_pkg else []
        preamble: List[str] = []
        for b in bindings.values():
            imports.extend(i for i in b.imports() if i not in imports)
            preamble.extend(l for l in b.preamble() if l not in preamble)
        return WovenPackage(name, user_pkg or "", imports, preamble=preamble)

    to_gen = gen_package_cycles(aggregates)
    pkgs: Dict[str, WovenPackage] = {}
    for p in res.model.packages():
        if any(wc.cls.package == p.name for wc in woven) or (
                p.name in aggregates and p.name not in to_gen):
            pkgs[p.name] = new_pkg(p.name + "_woven", p.name)
        for wc in woven:
            if wc.cls.package == p.name:
                pkgs[p.name].classes.append(wc)
    if to_gen:
        pkgs[GEN_PKG] = new_pkg(GEN_PKG, None)
    agg_regs: Dict[str, List[str]] = {}
    for user_pkg in sorted(aggregates, key=lambda n: list(pkgs).index(n) if n in pkgs else 0):
        a = aggregates[user_pkg]
        wp = pkgs[GEN_PKG] if user_pkg in to_gen else pkgs[user_pkg]
        extra = ([user_pkg] if user_pkg in to_gen else []) + a.imports
        extra += [u + "_woven" for u in sorted(a.uses_woven)]
        wp.imports.extend(i for i in extra if i not in wp.imports)
        wp.items.extend(a.items)
        agg_regs.setdefault(wp.name, []).extend(a.registrations)
    res.packages = list(pkgs.values())
    for wp in res.packages:
        used = []
        for wc in wp.classes:
            if wc.target.binding not in used:
                used.append(wc.target.binding)
        stmts: List[str] = []
        for bn in used:
            stmts.extend(bindings[bn].package_items(wp, cfg) or [])
        stmts.extend(agg_regs.get(wp.name, []))
        register_items(wp, stmts, cfg.registration == "static")
    for b in bindings.values():
        res.extra_files.update(b.init_files(res.packages, cfg))
    res.extra_files[INIT_FILE] = render_init(res.packages)

    # 6. Render.
    res.rendered = [render_package(wp) for wp in res.packages]
    # Compile order: woven packages, binding extras, then the init package last.
    extras = sorted((k, v) for k, v in res.extra_files.items() if k != INIT_FILE)
    gen = [(r.name, r.text) for r in res.rendered] + extras + [(INIT_FILE, res.extra_files[INIT_FILE])]
    res.output_hash = _hash(gen)
    res.compile_order = [name for name, _ in gen]

    # 7. Verify.
    previous = _previous_manifest(out_dir)
    with _Timer(res, "verify"):
        vr = verify_stage(res, level, previous)
    res.verify_status = vr.status
    res.diags = _dedup(res.diags + vr.diags)
    failed_dir = os.path.join(out_dir, FAILED_DIR)
    if not vr.ok:
        if write:
            for name, text in gen:
                write_if_changed(os.path.join(failed_dir, name), text)
        _stop(res.diags, "verification (%s) failed; the generated code is in %s"
              % (vr.status, failed_dir))
    if vr.status == "full":
        res.verified = {"level": "full", "input_hash": res.input_hash,
                        "output_hash": res.output_hash}
    elif vr.status == "cached":
        res.verified = previous["verified"]
    if write and os.path.isdir(failed_dir):
        shutil.rmtree(failed_dir)

    # 8. Write.
    files = dict(gen)
    files[WOVEN_FILELIST] = "".join(os.path.join(out_dir, n) + "\n" for n in res.compile_order)
    files[RUNTIME_FILELIST] = "".join(f + "\n" for f in rt)
    res.generated_names = list(files) + [MANIFEST, REPORT]
    res.manifest = build_manifest(res)
    files[MANIFEST] = manifest_text(res.manifest)
    files[REPORT] = render_report(res.manifest)
    if write:
        res.changed = write_outputs(out_dir, files)
    return res
