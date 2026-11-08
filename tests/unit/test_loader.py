import pytest

from sv_weave.diag import SvWeaveError
from sv_weave.filelist import SourceSpec
from sv_weave.frontend.loader import load, load_text


def test_error_reports_file_and_line():
    with pytest.raises(SvWeaveError) as e:
        load_text("package p;\n  class A;\n    int x = nope;\n  endclass\nendpackage\n")
    d = e.value.diags[0]
    assert d.loc.file == "inline.sv" and d.loc.line == 3
    assert d.code == "UndeclaredIdentifier"


def test_missing_file():
    with pytest.raises(SvWeaveError, match="not found"):
        load(SourceSpec(files=["/no/such/file.sv"]))


def test_single_unit_macros_and_defines(tmp_path):
    (tmp_path / "inc").mkdir()
    (tmp_path / "inc" / "w.svh").write_text("`define WIDTH 12\n")
    (tmp_path / "a.sv").write_text('`include "w.svh"\n`define TWICE(x) (2*(x))\n')
    (tmp_path / "b.sv").write_text(
        "package p; class A; bit [`WIDTH-1:0] v; int t = `TWICE(`EXTRA); endclass endpackage\n")
    l = load(SourceSpec(files=[str(tmp_path / "a.sv"), str(tmp_path / "b.sv")],
                        incdirs=[str(tmp_path / "inc")], defines={"EXTRA": "3"}))
    a = l.compilation.getPackage("p").find("A")
    assert a.find("v").type.bitWidth == 12


def test_no_sources():
    with pytest.raises(SvWeaveError, match="no SystemVerilog sources"):
        load(SourceSpec())
