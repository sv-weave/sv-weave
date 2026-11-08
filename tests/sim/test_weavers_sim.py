"""P5 end-to-end: the built-in copy, compare and print weavers on Verilator."""
import os

import pytest

from .conftest import weave_sim

HERE = os.path.dirname(os.path.abspath(__file__))
LIB_CFG = os.path.join(HERE, "lib_tx", "sv-weave.yaml")

pytestmark = pytest.mark.sim


def case(name):
    return os.path.join(HERE, name)


@pytest.mark.parametrize("name", ["copy_hier3", "copy_arrays", "copy_param"])
def test_copy_compare(dvflow, name):
    weave_sim(dvflow, case(name), lib="lib_tx").assert_pass()


def test_print_basic(dvflow):
    r = weave_sim(dvflow, case("print_basic"), lib="lib_tx")
    r.assert_pass()
    out = r.text.split("PRINT-BEGIN\n", 1)[1].split("PRINT-END", 1)[0].splitlines()
    assert "g: 'h2a" in out
    assert 'gs: "hello"' in out
    assert "c: GREEN" in out
    assert "deep_h: {v: 'h5" in out
    assert "shallow_h: null" in out


def test_user_do_copy_coexists(dvflow):
    weave_sim(dvflow, case("user_do_copy_coexists")).assert_pass()
