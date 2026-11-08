"""Helpers for sim tests: build a dv-flow graph and run it on Verilator.

Every sim case is a directory of SV files with a ``tb`` module that follows the
check_pkg convention (prints ``SV_WEAVE_TEST: PASS``, ``$fatal`` on failure).
P3 adds ``weave_sim``, which inserts the svweave.Runtime and svweave.Weave tasks
between the sources and the image build.
"""
import dataclasses as dc
import os
import shutil
from typing import List, Optional, Sequence

import pytest

SIM_DIR = os.path.dirname(os.path.abspath(__file__))
CHECK_SV_DIR = os.path.join(SIM_DIR, "sv")

PASS_TOKEN = "SV_WEAVE_TEST: PASS"
FAIL_TOKEN = "SV_WEAVE_TEST: FAIL"


def _has_dfm() -> bool:
    try:
        import pytest_dfm  # noqa: F401
        import dv_flow.libhdlsim  # noqa: F401
        return True
    except ImportError:
        return False


def pytest_collection_modifyitems(config, items):
    no_vlt = shutil.which("verilator") is None
    no_xzm = shutil.which("xezim") is None
    no_dfm = not _has_dfm()
    for item in items:
        if "sim" not in item.keywords and "xezim" not in item.keywords:
            continue
        if no_dfm:
            item.add_marker(pytest.mark.skip(reason="pytest-dfm / dv-flow-libhdlsim not installed"))
        elif "xezim" in item.keywords:
            if no_xzm:
                item.add_marker(pytest.mark.skip(reason="xezim is not on PATH"))
        elif no_vlt:
            item.add_marker(pytest.mark.skip(reason="verilator is not on PATH"))


@dc.dataclass
class SimResult:
    status: int
    rundir: Optional[str]
    log: Optional[str]
    text: str = ""

    def assert_pass(self):
        where = "log: %s" % self.log if self.log else "no sim.log (build failed?)"
        assert self.status == 0, "flow failed (status %d); %s" % (self.status, where)
        bad = [l for l in self.text.splitlines() if FAIL_TOKEN in l or "%Error" in l]
        assert not bad, "%s\n%s" % (where, "\n".join(bad[:20]))
        assert PASS_TOKEN in self.text, "%s not seen; %s" % (PASS_TOKEN, where)


def _find_run_dir(out) -> Optional[str]:
    outs = out if isinstance(out, list) else [out]
    for o in outs:
        if o is None:
            continue
        for fs in o.output:
            if getattr(fs, "filetype", None) == "simRunDir":
                return fs.basedir
    return None


def source_tasks(dvflow, case_dir: str, name: str = "src", lib=None) -> List:
    """FileSets for check_pkg.sv, optional shared libraries (``lib``: a directory under
    tests/sim or an absolute one, a (dir, include) pair, or a list of these), and the
    case's own *.sv files, in compile order."""
    tasks = [dvflow.mkTask("std.FileSet", name="check_sv", type="systemVerilogSource",
                           base=CHECK_SV_DIR, include="check_pkg.sv")]
    libs = [] if lib is None else ([lib] if isinstance(lib, (str, tuple)) else list(lib))
    for i, l in enumerate(libs):
        d, inc = (l, "*.sv") if isinstance(l, str) else l
        tasks.append(dvflow.mkTask("std.FileSet", name="lib%d" % i, type="systemVerilogSource",
                                   base=os.path.join(SIM_DIR, d), include=inc))
    tasks.append(dvflow.mkTask("std.FileSet", name=name, type="systemVerilogSource",
                               base=case_dir, include="*.sv"))
    return tasks


def run_sim(dvflow, srcs: Sequence, top="tb", plusargs: Sequence[str] = (),
            sim: str = "vlt") -> SimResult:
    """Build srcs into a simulation image with the given top(s) and run it.
    ``sim`` is an hdlsim backend: ``vlt`` (Verilator, the default) or ``xzm`` (xezim)."""
    tops = [top] if isinstance(top, str) else list(top)
    img = dvflow.mkTask("hdlsim.%s.SimImage" % sim, name="img", top=tops, needs=list(srcs))
    run = dvflow.mkTask("hdlsim.%s.SimRun" % sim, name="run", needs=[img],
                        plusargs=list(plusargs))
    status, out = dvflow.runTask(run)
    rundir = _find_run_dir(out)
    if rundir is None:
        # A failed run emits no simRunDir output; the task's directory is still there.
        rundir = os.path.join(str(dvflow.tmpdir), "run")
    log, text = None, ""
    if rundir is not None and os.path.isfile(os.path.join(rundir, "sim.log")):
        log = os.path.join(rundir, "sim.log")
        with open(log) as fp:
            text = fp.read()
    return SimResult(status, rundir, log, text)


def weave_task(dvflow, case_dir: str, config: str = "sv-weave.yaml", name: str = "woven",
               lib=None, **params):
    """svweave.Weave over check_pkg.sv, the shared library and the case's sources."""
    srcs = source_tasks(dvflow, case_dir, lib=lib)
    cfg = os.path.join(case_dir, config)
    if os.path.isfile(cfg):
        params["config"] = cfg
    return dvflow.mkTask("svweave.Weave", name=name, needs=srcs, **params)


def weave_sim(dvflow, case_dir: str, top="tb", plusargs: Sequence[str] = (),
              config: str = "sv-weave.yaml", lib=None, sim: str = "vlt", **params) -> SimResult:
    """Weave the case's sources, then build and run them (Verilator by default)."""
    rt = dvflow.mkTask("svweave.Runtime", name="rt", binding=["reflib"])
    woven = weave_task(dvflow, case_dir, config, lib=lib, **params)
    return run_sim(dvflow, [rt, woven], top=top, plusargs=plusargs, sim=sim)


def weave_sim_runs(dvflow, case_dir: str, runs, top="tb", config: str = "sv-weave.yaml",
                   lib=None, **params):
    """Weave and build once, then run the image once per entry of ``runs``
    ({name: plusargs}). Returns {name: SimResult}."""
    rt = dvflow.mkTask("svweave.Runtime", name="rt", binding=["reflib"])
    woven = weave_task(dvflow, case_dir, config, lib=lib, **params)
    tops = [top] if isinstance(top, str) else list(top)
    img = dvflow.mkTask("hdlsim.vlt.SimImage", name="img", top=tops, needs=[rt, woven])
    tasks = [dvflow.mkTask("hdlsim.vlt.SimRun", name="run_" + n, needs=[img], plusargs=list(p))
             for n, p in runs.items()]
    status, _ = dvflow.runTask(tasks)
    out = {}
    for n in runs:
        rundir = os.path.join(str(dvflow.tmpdir), "run_" + n)
        log = os.path.join(rundir, "sim.log")
        text = ""
        if os.path.isfile(log):
            with open(log) as fp:
                text = fp.read()
        else:
            log = None
        out[n] = SimResult(0 if log and status == 0 else status, rundir, log, text)
    return out
