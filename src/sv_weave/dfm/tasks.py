"""dv-flow tasks of the ``svweave`` package (design §11)."""
import logging
import os

from dv_flow.mgr import FileSet, TaskDataResult
from dv_flow.mgr.task_data import SeverityE, TaskMarker, TaskMarkerLoc

from ..diag import Severity, SvWeaveError
from ..filelist import SourceSpec

_log = logging.getLogger("svweave")

SV_TYPES = ("systemVerilogSource", "verilogSource", "systemVerilogInclude")
_SEV = {Severity.ERROR: SeverityE.Error, Severity.WARNING: SeverityE.Warning,
        Severity.NOTE: SeverityE.Info}


def _marker(d) -> TaskMarker:
    loc = None
    if d.loc is not None:
        loc = TaskMarkerLoc(path=d.loc.file, line=d.loc.line, pos=d.loc.col or -1)
    return TaskMarker(msg=d.msg, severity=_SEV[d.severity], loc=loc)


def _list(v):
    if v is None:
        return []
    if isinstance(v, str):
        return v.split()
    return list(v)


async def Runtime(runner, input) -> TaskDataResult:
    """The SV sources the listed bindings need ahead of the design (may be none)."""
    from ..plugin import BINDING_GROUP, find

    files = []
    for n in _list(input.params.binding):
        for f in find(BINDING_GROUP, n, [input.srcdir])().sv_runtime_files():
            if f not in files:
                files.append(f)
    output = []
    if files:
        output.append(FileSet(filetype="systemVerilogSource", src=input.name, basedir="/",
                              files=[os.path.abspath(f) for f in files]))
    return TaskDataResult(changed=input.changed, output=output)


def _upstream_spec(inputs) -> SourceSpec:
    spec = SourceSpec()
    for fs in inputs:
        if getattr(fs, "type", None) != "std.FileSet" or fs.filetype not in SV_TYPES:
            continue
        if fs.filetype == "systemVerilogInclude":
            spec.incdirs.append(fs.basedir)
            continue
        for f in fs.files:
            p = f if os.path.isabs(f) else os.path.join(fs.basedir, f)
            if p not in spec.files:
                spec.files.append(p)
        for d in fs.incdirs:
            d = d if os.path.isabs(d) else os.path.join(fs.basedir, d)
            if d not in spec.incdirs:
                spec.incdirs.append(d)
        for d in fs.defines:
            name, _, val = d.partition("=")
            spec.defines[name] = val if val else None
    return spec


def _weave_config(p, srcdir):
    """The Weave task's config: the ``config`` file (relative to the flow's source
    directory), with the ``profiles`` and ``binding`` params applied."""
    from ..config import Config, load_config

    if p.config:
        path = p.config if os.path.isabs(p.config) else os.path.join(srcdir, p.config)
        cfg = load_config(path)
    else:
        cfg = Config()
    updates = {}
    if _list(p.profiles):
        updates["build_profiles"] = _list(p.profiles)
        updates["default_profile"] = None
    if _list(p.binding):
        updates["binding"] = _list(p.binding)
    if not getattr(p, "init", True) and cfg.init:
        updates["init"] = False
    if updates:
        base = cfg.base_dir
        cfg = Config.model_validate({**cfg.model_dump(by_alias=False), **updates})
        cfg._base_dir = base
    return cfg


def _weave_spec(p, inputs) -> SourceSpec:
    """The upstream sources plus the ``top`` param."""
    spec = _upstream_spec(inputs)
    spec.extend(SourceSpec(tops=_list(getattr(p, "top", None))))
    return spec


async def WeaveUpToDate(ctxt) -> bool:
    """dv-flow up-to-date check for Weave, run after dv-flow's own (params, inputs,
    outputs present). Up to date only if the input hash the last run stored still
    holds: it also covers the config file's content and the weavers' and bindings'
    source, which dv-flow does not see."""
    try:
        from ..run import input_hash, prepare

        old = (ctxt.memento or {}).get("input_hash")
        if not old:
            return False
        cfg = _weave_config(ctxt.params, ctxt.srcdir)
        now = input_hash(prepare(cfg, _weave_spec(ctxt.params, ctxt.inputs)))
        if now != old:
            _log.info("svweave.Weave: inputs changed (config, plugin or sv-weave source)")
        return now == old
    except Exception as e:  # anything unexpected: re-run
        _log.debug("svweave.Weave up-to-date check failed: %s", e)
        return False


async def Weave(runner, input) -> TaskDataResult:
    from ..run import run

    p = input.params
    markers = []
    try:
        cfg = _weave_config(p, input.srcdir)
        out_dir = os.path.join(input.rundir, "woven")
        old_hash = None
        if input.memento is not None:
            old_hash = input.memento.get("output_hash")
        res = run(cfg, spec=_weave_spec(p, input.inputs), out_dir=out_dir,
                  verify=getattr(p, "verify", "") or None)
    except SvWeaveError as e:
        markers = [_marker(d) for d in e.diags] or [TaskMarker(msg=str(e), severity=SeverityE.Error)]
        return TaskDataResult(status=1, changed=True, output=[], markers=markers)

    markers = [_marker(d) for d in res.diags]
    woven = FileSet(filetype="systemVerilogSource", src=input.name, basedir=out_dir,
                    files=list(res.compile_order))
    manifest = FileSet(filetype="jsonManifest", src=input.name, basedir=out_dir,
                       files=["weave-manifest.json"])
    changed = input.changed or old_hash != res.output_hash or bool(res.changed)
    return TaskDataResult(
        status=0, changed=changed, output=[woven, manifest], markers=markers,
        memento={"output_hash": res.output_hash, "input_hash": res.input_hash})


async def Init(runner, input) -> TaskDataResult:
    """One init for several Weave tasks: reads the ``register`` list of each upstream
    jsonManifest (in input order, each package once) and writes the init package and
    module."""
    import json

    from ..render import INIT_FILES, render_init
    from ..write import write_if_changed

    names, errs = [], []
    for fs in input.inputs:
        if getattr(fs, "type", None) != "std.FileSet" or fs.filetype != "jsonManifest":
            continue
        for f in fs.files:
            path = f if os.path.isabs(f) else os.path.join(fs.basedir, f)
            try:
                with open(path) as fp:
                    m = json.load(fp)
            except (OSError, ValueError) as e:
                errs.append("cannot read %s: %s" % (path, e))
                continue
            if "register" not in m:
                errs.append("%s has no 'register' list (from sv-weave before 0.2?)" % path)
                continue
            own = [n for n in m.get("files", {}).get("compile_order", []) if n in INIT_FILES]
            if own:
                errs.append("%s: that Weave writes its own init (%s); set 'init: false' on "
                            "it" % (path, ", ".join(own)))
                continue
            names.extend(n for n in m["register"] if n not in names)
    if errs:
        return TaskDataResult(status=1, changed=True, output=[],
                              markers=[TaskMarker(msg=e, severity=SeverityE.Error) for e in errs])
    out_dir = os.path.join(input.rundir, "init")
    changed = False
    for name, text in render_init(names).items():
        changed = write_if_changed(os.path.join(out_dir, name), text) or changed
    init = FileSet(filetype="systemVerilogSource", src=input.name, basedir=out_dir,
                   files=list(INIT_FILES))
    return TaskDataResult(status=0, changed=input.changed or changed, output=[init],
                          memento={"register": names})
