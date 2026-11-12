import json

import pytest

from sv_weave import cli

SRC = """
package a_pkg;
  import reflib_pkg::*;
  class A extends ref_object;
    virtual function void build(); endfunction
  endclass
endpackage
"""

pytestmark = pytest.mark.usefixtures("test_weavers")


def test_gen_and_report(tmp_path, capsys):
    (tmp_path / "a.sv").write_text(SRC)
    (tmp_path / "sv-weave.yaml").write_text(
        "sv-weave:\n  binding: reflib\n  sources: {files: [a.sv]}\n  out_dir: out\n  weavers: [{name: t_build}]\n")
    assert cli.main(["gen", "-c", str(tmp_path / "sv-weave.yaml")]) == 0
    out = capsys.readouterr().out
    assert "1 woven class in 1 package" in out and "7 files changed" in out
    man = tmp_path / "out" / "weave-manifest.json"
    m = json.loads(man.read_text())
    assert m["targets"][0]["woven"]["release"]["name"] == "Woven_A__release"
    assert m["files"]["compile_order"] == ["a_pkg_woven.sv", "sv_weave_init_pkg.sv",
                                           "sv_weave_init_m.sv"]

    assert cli.main(["gen", "-c", str(tmp_path / "sv-weave.yaml")]) == 0
    assert "0 files changed" in capsys.readouterr().out

    assert cli.main(["report", str(man)]) == 0
    assert "`Woven_A__release` (t_build[core])" in capsys.readouterr().out


def test_gen_error_exit(tmp_path, capsys):
    (tmp_path / "a.sv").write_text(SRC)
    (tmp_path / "sv-weave.yaml").write_text("sv-weave:\n  binding: reflib\n  weavers: [{name: nope}]\n")
    assert cli.main(["gen", "-c", str(tmp_path / "sv-weave.yaml"), str(tmp_path / "a.sv")]) == 1
    assert "unknown weaver 'nope'" in capsys.readouterr().err


def test_schema(capsys):
    assert cli.main(["schema"]) == 0
    s = json.loads(capsys.readouterr().out)
    props = s["properties"]["sv-weave"]["properties"]
    assert {"verify", "extension-sets", "build-profiles", "weavers"} <= set(props)
    assert "base_dir" not in props
