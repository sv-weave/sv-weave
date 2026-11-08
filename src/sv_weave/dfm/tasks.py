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


def _upstream_spec(input) -> SourceSpec:
    spec = SourceSpec()
    for fs in input.inputs:
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


async def Weave(runner, input) -> TaskDataResult:
    from ..config import Config, load_config
    from ..run import run

    p = input.params
    markers = []
    try:
        if p.config:
            path = p.config if os.path.isabs(p.config) else os.path.join(input.srcdir, p.config)
            cfg = load_config(path)
        else:
            cfg = Config()
        updates = {}
        if _list(p.profiles):
            updates["build_profiles"] = _list(p.profiles)
            updates["default_profile"] = None
        if _list(p.binding):
            updates["binding"] = _list(p.binding)
        if updates:
            base = cfg.base_dir
            cfg = Config.model_validate({**cfg.model_dump(by_alias=False), **updates})
            cfg._base_dir = base

        out_dir = os.path.join(input.rundir, "woven")
        old_hash = None
        if input.memento is not None:
            old_hash = input.memento.get("output_hash")
        res = run(cfg, spec=_upstream_spec(input), out_dir=out_dir,
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
