"""The example reference library (examples/reflib) is clean under Verilator's -Wall lint."""
import os
import subprocess

import pytest


pytestmark = pytest.mark.sim

REFLIB = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "examples",
                                      "reflib", "reflib_pkg.sv"))

TOP = """
module top;
  import reflib_pkg::*;
  class A extends ref_object; endclass
  initial begin
    A a;
    ref_profiles::select("debug", "x::*", "*");
    a = ref_factory#(A)::create("top.a");
    $display("%s %0d %s", ref_profiles::active("x::A", "top"), ref_glob("a*c", "abc"),
             a.ref_impl_name());
    ref_registry::inst().dump();
  end
endmodule
"""


def test_runtime_lint_wall(tmp_path):
    top = tmp_path / "top.sv"
    top.write_text(TOP)
    log = tmp_path / "lint.log"
    with open(log, "w") as fp:
        r = subprocess.run(["verilator", "--lint-only", "-Wall", "--top-module", "top"]
                           + [REFLIB, str(top)], stdout=fp, stderr=subprocess.STDOUT,
                           cwd=str(tmp_path))
    assert r.returncode == 0, log.read_text()[-3000:]
