import json

from sv_weave import cli

SRC = """
package a_pkg;
  import reflib_pkg::*;
  class A extends ref_object; endclass
  class P #(int W = 4) extends A; endclass
  class Q extends P#(8); endclass
  class Plain; endclass
endpackage
"""


def test_list_targets_json(tmp_path, capsys):
    f = tmp_path / "a.sv"
    f.write_text(SRC)
    assert cli.main(["list", "-b", "reflib", "--json", str(f)]) == 0
    rows = json.loads(capsys.readouterr().out)["targets"]
    assert [r["class"] for r in rows] == ["a_pkg::A", "a_pkg::P#(8)", "a_pkg::Q"]
    assert rows[1]["params"] == {"W": "8"}
    assert rows[0]["loc"].startswith(str(f) + ":4")


def test_list_classes_text(tmp_path, capsys):
    f = tmp_path / "a.sv"
    f.write_text(SRC)
    assert cli.main(["list", "-b", "reflib", "--classes", str(f)]) == 0
    out = capsys.readouterr().out
    assert "* a_pkg::Q" in out
    assert "a_pkg::Plain" in out and "no binding root" in out


def test_list_with_config_and_filelist(tmp_path, capsys):
    (tmp_path / "a.sv").write_text(SRC)
    (tmp_path / "files.f").write_text("a.sv\n")
    (tmp_path / "sv-weave.yaml").write_text(
        "sv-weave:\n  binding: reflib\n  sources: {filelists: [files.f]}\n  packages: {exclude: ['a_*']}\n")
    assert cli.main(["list", "-c", str(tmp_path / "sv-weave.yaml")]) == 0
    assert "no target classes" in capsys.readouterr().out


def test_list_reports_errors(tmp_path, capsys):
    f = tmp_path / "bad.sv"
    f.write_text("package p; class A; int x = nope; endclass endpackage\n")
    assert cli.main(["list", "-b", "reflib", str(f)]) == 1
    err = capsys.readouterr().err
    assert "does not elaborate cleanly" in err and "bad.sv:1" in err


def test_list_top(tmp_path, capsys):
    """--top names the modules to elaborate; without it a module that cannot
    elaborate on its own fails the load."""
    f = tmp_path / "a.sv"
    f.write_text(SRC + "module needs_class #(parameter type T = int); T h = null; endmodule\n"
                 "module stub_top; endmodule\n")
    assert cli.main(["list", "-b", "reflib", "--json", str(f)]) != 0
    capsys.readouterr()
    assert cli.main(["list", "-b", "reflib", "--json", "--top", "stub_top", str(f)]) == 0
    rows = json.loads(capsys.readouterr().out)["targets"]
    assert [r["class"] for r in rows] == ["a_pkg::A", "a_pkg::P#(8)", "a_pkg::Q"]
