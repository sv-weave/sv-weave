"""P7 end-to-end: a design-wide weaver, using the selector example in examples/selector."""
import os

import pytest

from .conftest import weave_sim

HERE = os.path.dirname(os.path.abspath(__file__))
EXAMPLE = os.path.abspath(os.path.join(HERE, "..", "..", "examples", "selector"))
LIBS = [(EXAMPLE, "select_pkg.sv"), "lib_sel"]

pytestmark = pytest.mark.sim


@pytest.mark.parametrize("name", ["selector_basic", "selector_weights",
                                  "selector_respects_override", "selector_param"])
def test_selector(dvflow, name):
    r = weave_sim(dvflow, os.path.join(HERE, name), lib=LIBS)
    r.assert_pass()
    if name == "selector_param":
        assert "PARAM sel_sub_pkg::ppkt#(16) p16" in r.text
        assert "PARAM sel_sub_pkg::ppkt#(32) p32" in r.text
