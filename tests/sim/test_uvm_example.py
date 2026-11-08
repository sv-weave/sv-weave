"""The UVM example binding (examples/uvm/) on Verilator's bundled UVM."""
import os

import pytest

from .conftest import CHECK_SV_DIR, run_sim

HERE = os.path.dirname(os.path.abspath(__file__))

pytestmark = pytest.mark.sim


def test_uvm_basic(dvflow):
    case = os.path.join(HERE, "uvm_basic")
    uvm = dvflow.mkTask("hdlsim.vlt.SimLibUVM", name="uvm")
    # The example binding's SV package: compiled after UVM, before the design.
    swu = dvflow.mkTask("std.FileSet", name="swu", type="systemVerilogSource",
                        base=os.path.join(HERE, "..", "..", "examples", "uvm"),
                        include="sv_weave_uvm_pkg.sv")
    chk = dvflow.mkTask("std.FileSet", name="check_sv", type="systemVerilogSource",
                        base=CHECK_SV_DIR, include="check_pkg.sv")
    src = dvflow.mkTask("std.FileSet", name="src", type="systemVerilogSource",
                        base=case, include="*.sv")
    woven = dvflow.mkTask("svweave.Weave", name="woven", needs=[uvm, swu, chk, src],
                          config=os.path.join(case, "sv-weave.yaml"))
    r = run_sim(dvflow, [woven])
    r.assert_pass()
    text = r.text.split("STRING ", 1)[1].split("SV_WEAVE_TEST", 1)[0]
    assert text.splitlines()[:3] == ["addr: 'h12", "data: 'hcafe", "payload: '{'h1, 'h2, 'h3}"]
    assert "begin_event" not in text      # UVM's own fields are not woven
