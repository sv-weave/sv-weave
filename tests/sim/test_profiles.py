"""P6 end-to-end: profiles chosen at compile time and at run time."""
import os
import re

import pytest

from .conftest import weave_sim, weave_sim_runs

HERE = os.path.dirname(os.path.abspath(__file__))

pytestmark = pytest.mark.sim


def case(name):
    return os.path.join(HERE, name)


def test_profile_runtime(dvflow):
    rs = weave_sim_runs(dvflow, case("profile_runtime"), lib="lib_prof", runs={
        "default": ["mode=default"],
        "profile": ["mode=profile", "weave_profile=debug"],
        "type": ["mode=type", "weave_impl=debug:prof_pkg::pkt"],
        "inst": ["mode=inst", "weave_impl=debug:*@tb.dbg*", "weave_report"],
    })
    for name, r in rs.items():
        r.assert_pass()
    assert "reflib: resolve prof_pkg::pkt @ 'tb.dbg1' -> Woven_pkt__debug" in rs["inst"].text


def test_profile_compiletime(dvflow):
    r = weave_sim(dvflow, case("profile_compiletime"), lib="lib_prof",
                  plusargs=["weave_profile=debug"])
    r.assert_pass()
    woven = os.path.join(str(dvflow.tmpdir), "woven", "woven", "prof_pkg_woven.sv")
    with open(woven) as fp:
        assert "__debug" not in fp.read()


def test_debug_seed_repro(dvflow):
    rs = weave_sim_runs(dvflow, case("debug_seed_repro"), lib="lib_prof", runs={
        "release": ["weave_profile=release"],
        "debug": ["weave_profile=debug"],
    })
    vals = {}
    for name, r in rs.items():
        r.assert_pass()
        vals[name] = re.findall(r"^VALUES .*$", r.text, re.M)
    assert "IMPL Woven_pkt__release" in rs["release"].text
    assert "IMPL Woven_pkt__debug" in rs["debug"].text
    assert len(vals["release"]) == 4
    assert vals["release"] == vals["debug"]
