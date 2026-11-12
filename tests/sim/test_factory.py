"""P3 end-to-end: weave, build and run on Verilator through pytest-dfm."""
import os

import pytest

from .conftest import run_sim, source_tasks, weave_sim, weave_task

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
    assert [os.path.basename(p) for p in paths] == ["a_pkg_woven.sv", "sv_weave_init_pkg.sv",
                                                      "sv_weave_init_m.sv"]
    mtimes = [os.stat(p).st_mtime_ns for p in paths]

    t2 = weave_task(dvflow, case("incremental"), lib="lib_a")
    status, out2 = dvflow.runTask(t2)
    assert status == 0
    assert out2.changed is False
    assert [os.stat(p).st_mtime_ns for p in paths] == mtimes


def _weave_reasons(dvflow, cfg_path):
    """Runs Weave over the incremental case with ``cfg_path``; returns (status,
    output, the runner's verdicts for the Weave task: "run" or "uptodate")."""
    srcs = source_tasks(dvflow, case("incremental"), lib="lib_a")
    t = dvflow.mkTask("svweave.Weave", name="woven", needs=srcs, config=str(cfg_path))
    reasons = []

    def listener(task, reason):
        if str(getattr(task, "name", "")).endswith("woven") and reason in ("run", "uptodate"):
            reasons.append(reason)
    status, out = dvflow.runTask(t, listener=listener)
    return status, out, reasons


def _edit_case(tmp_path, mod):
    """A config in tmp_path using a weaver package ``mod`` there (a module plus a
    helper it imports)."""
    d = tmp_path / mod
    d.mkdir()
    (d / "__init__.py").write_text("")
    (d / "helper.py").write_text("MSG = 'one'\n")
    (d / "weaver.py").write_text(
        "from sv_weave import plugin\n"
        "from sv_weave.match import has_method\n"
        "from . import helper\n\n"
        "class W(plugin.Weaver):\n"
        "    name = '%s'\n\n"
        "    def subscribe(self, bus):\n"
        "        bus.on(has_method('build'), self.weave)\n\n"
        "    def weave(self, w):\n"
        "        w.override('build').pre.add('$display(\"%%s\");' %% helper.MSG)\n" % mod)
    cfg = tmp_path / "sv-weave.yaml"
    cfg.write_text("sv-weave:\n  binding: reflib\n  weavers:\n  - {name: '%s.weaver:W'}\n"
                   % mod)
    return d, cfg


def test_incremental_weaver_edit(dvflow, tmp_path):
    """Editing a weaver's source re-runs Weave, though dv-flow sees no change."""
    d, cfg = _edit_case(tmp_path, "edit_w1")
    status, _, reasons = _weave_reasons(dvflow, cfg)
    assert status == 0 and reasons == ["run"]
    status, _, reasons = _weave_reasons(dvflow, cfg)
    assert status == 0 and reasons == ["uptodate"]
    (d / "helper.py").write_text("MSG = 'two'\n")
    status, out, reasons = _weave_reasons(dvflow, cfg)
    assert status == 0 and reasons == ["run"]


def test_incremental_config_edit(dvflow, tmp_path):
    """Editing sv-weave.yaml (the file the config param names) re-runs Weave."""
    _, cfg = _edit_case(tmp_path, "edit_w2")
    status, _, reasons = _weave_reasons(dvflow, cfg)
    assert status == 0 and reasons == ["run"]
    status, _, reasons = _weave_reasons(dvflow, cfg)
    assert status == 0 and reasons == ["uptodate"]
    cfg.write_text(cfg.read_text() + "  strict: true\n")
    status, out, reasons = _weave_reasons(dvflow, cfg)
    assert status == 0 and reasons == ["run"]
    woven = [fs for fs in out.output if getattr(fs, "src", None) == "woven"
             and fs.filetype == "jsonManifest"]
    assert woven


def test_two_weaves_one_init(dvflow):
    """Two Weave tasks with init false (the task param) and one svweave.Init feed one
    image; both libraries' factories return their woven classes."""
    d = case("two_weaves_one_init")
    cfg = os.path.join(d, "sv-weave.yaml")
    check = dvflow.mkTask("std.FileSet", name="check_sv", type="systemVerilogSource",
                          base=os.path.join(HERE, "sv"), include="check_pkg.sv")
    lib_a = dvflow.mkTask("std.FileSet", name="lib_a", type="systemVerilogSource",
                          base=case("lib_a"), include="*.sv")
    lib_c = dvflow.mkTask("std.FileSet", name="lib_c", type="systemVerilogSource",
                          base=case("lib_c"), include="*.sv")
    w1 = dvflow.mkTask("svweave.Weave", name="woven_a", needs=[check, lib_a], config=cfg,
                       init=False)
    w2 = dvflow.mkTask("svweave.Weave", name="woven_c", needs=[lib_c], config=cfg, init=False)
    init = dvflow.mkTask("svweave.Init", name="init", needs=[w1, w2])
    tb = dvflow.mkTask("std.FileSet", name="tb", type="systemVerilogSource", base=d,
                       include="tb.sv")
    rt = dvflow.mkTask("svweave.Runtime", name="rt", binding=["reflib"])
    r = run_sim(dvflow, [rt, init, tb])
    r.assert_pass()
    with open(os.path.join(str(dvflow.tmpdir), "init", "init", "sv_weave_init_pkg.sv")) as fp:
        text = fp.read()
    assert "a_pkg_woven::__register();" in text and "c_pkg_woven::__register();" in text


def test_init_rejects_weave_with_own_init(dvflow):
    """svweave.Init over a Weave that writes its own init is an error."""
    lib_a = dvflow.mkTask("std.FileSet", name="lib_a", type="systemVerilogSource",
                          base=case("lib_a"), include="*.sv")
    w = dvflow.mkTask("svweave.Weave", name="woven", needs=[lib_a],
                      config=os.path.join(case("two_weaves_one_init"), "sv-weave.yaml"))
    init = dvflow.mkTask("svweave.Init", name="init", needs=[w])
    status, _ = dvflow.runTask(init)
    assert status != 0


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
