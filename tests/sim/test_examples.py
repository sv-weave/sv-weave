"""The documented examples run as written."""
import os

import pytest

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))

pytestmark = pytest.mark.sim


def test_quickstart_flow(dvflow):
    flow = os.path.join(ROOT, "examples", "quickstart", "flow.dv")
    status, out = dvflow.runFlow(flow, "quickstart.sim-run")
    assert status == 0
    rundir = [fs.basedir for fs in out.output if getattr(fs, "filetype", None) == "simRunDir"][0]
    with open(os.path.join(rundir, "sim.log")) as fp:
        log = fp.read()
    assert "impl: Woven_packet__release" in log
    assert "addr=10" in log and "data=cafe" in log
