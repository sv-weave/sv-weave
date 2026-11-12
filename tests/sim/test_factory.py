"""P3 end-to-end: weave, build and run on Verilator through pytest-dfm."""
import os

import pytest

from .conftest import source_tasks, weave_sim, weave_task

HERE = os.path.dirname(os.path.abspath(__file__))

pytestmark = [pytest.mark.sim, pytest.mark.usefixtures("test_weavers")]


def case(name):
    return os.path.join(HERE, name)


def test_factory_basic(dvflow):
    r = weave_sim(dvflow, case("factory_basic"), lib="lib_a")
    r.assert_pass()
    assert "t_build: pre build A" in r.text and "t_build: post build A" in r.text


def test_factory_unwoven_fallback(dvflow):
    weave_sim(dvflow, case("factory_unwoven_fallback"), lib="lib_a").assert_pass()


def test_override_forwarding(dvflow):
    r = weave_sim(dvflow, case("override_forwarding"), lib="lib_a")
    r.assert_pass()
    assert "t_build: pre build MyA" in r.text


def test_registration_explicit(dvflow):
    weave_sim(dvflow, case("registration_explicit"), lib="lib_a").assert_pass()


def test_registration_static(dvflow):
    """Records Verilator's behaviour for D2 (docs/design/notes/registration-trigger.md)."""
    weave_sim(dvflow, case("registration_static"), lib="lib_a").assert_pass()


def test_incremental(dvflow):
    """A second Weave with unchanged inputs reports changed=False and rewrites nothing."""
    t1 = weave_task(dvflow, case("incremental"), lib="lib_a")
    status, out = dvflow.runTask(t1)
    assert status == 0
    woven = [fs for fs in out.output if getattr(fs, "src", None) == "woven"
             and fs.filetype == "systemVerilogSource"][0]
    paths = [os.path.join(woven.basedir, f) for f in woven.files]
    assert [os.path.basename(p) for p in paths] == ["a_pkg_woven.sv", "sv_weave_init.sv"]
    mtimes = [os.stat(p).st_mtime_ns for p in paths]

    t2 = weave_task(dvflow, case("incremental"), lib="lib_a")
    status, out2 = dvflow.runTask(t2)
    assert status == 0
    assert out2.changed is False
    assert [os.stat(p).st_mtime_ns for p in paths] == mtimes


def test_weave_top_param(dvflow, tmp_path):
    """The Weave task's ``top`` names the modules slang elaborates."""
    (tmp_path / "m.sv").write_text(
        "module needs_class #(parameter type T = int); T h = null; endmodule\n"
        "module stub_top; endmodule\n")

    def weave(**params):
        srcs = source_tasks(dvflow, case("factory_basic"), lib="lib_a")
        srcs.append(dvflow.mkTask("std.FileSet", name="extra", type="systemVerilogSource",
                                  base=str(tmp_path), include="m.sv"))
        t = dvflow.mkTask("svweave.Weave", name="woven", needs=srcs,
                          config=os.path.join(case("factory_basic"), "sv-weave.yaml"), **params)
        return dvflow.runTask(t)[0]

    assert weave() != 0
    assert weave(top=["stub_top"]) == 0


@pytest.mark.xezim
@pytest.mark.xfail(strict=True, reason="xezim 0.11.3 gives P#(a_pkg::A) and P#(A) separate "
                   "static storage; see docs/design/notes/registration-trigger.md")
@pytest.mark.parametrize("name", ["factory_basic", "registration_explicit", "registration_static"])
def test_registration_xezim(dvflow, name):
    """The D2 comparison: the same registration cases on xezim."""
    weave_sim(dvflow, case(name), lib="lib_a", sim="xzm").assert_pass()
