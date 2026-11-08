"""Toolchain smoke: pytest-dfm drives Verilator on SV class code.

Checked with Verilator 5.054 through hdlsim.vlt (default flags), covering the
class features woven code relies on: inheritance, virtual dispatch with super,
$cast, parameterised classes and static member initialisers.
"""
import os

import pytest

from .conftest import run_sim, source_tasks

HERE = os.path.dirname(os.path.abspath(__file__))


@pytest.mark.sim
def test_smoke(dvflow):
    r = run_sim(dvflow, source_tasks(dvflow, os.path.join(HERE, "smoke")))
    r.assert_pass()


@pytest.mark.sim
def test_harness_detects_fail(dvflow):
    r = run_sim(dvflow, source_tasks(dvflow, os.path.join(HERE, "smoke_fail")))
    with pytest.raises(AssertionError):
        r.assert_pass()
    assert "deliberately wrong" in r.text
