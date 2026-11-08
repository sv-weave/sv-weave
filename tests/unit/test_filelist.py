import pytest

from sv_weave.diag import SvWeaveError
from sv_weave.filelist import read_filelist


def test_expansion(tmp_path, monkeypatch):
    monkeypatch.setenv("SVW_ROOT", str(tmp_path / "lib"))
    (tmp_path / "sub").mkdir()
    (tmp_path / "sub" / "inner.f").write_text("c.sv\n+incdir+inc2\n")
    (tmp_path / "top.f").write_text(
        "// comment\n# hash comment\n"
        "+incdir+inc+inc1\n-Iinc3\n+define+A=1+B\n-DC=x\n"
        "a.sv b.sv  // trailing comment\n"
        "-f sub/inner.f\n"
        "${SVW_ROOT}/d.sv\n"
        "a.sv\n")
    s = read_filelist(str(tmp_path / "top.f"))
    t = str(tmp_path)
    assert s.files == [t + "/a.sv", t + "/b.sv", t + "/sub/c.sv", t + "/lib/d.sv"]
    assert s.incdirs == [t + "/inc", t + "/inc1", t + "/inc3", t + "/sub/inc2"]
    assert s.defines == {"A": "1", "B": None, "C": "x"}


def test_unsupported_option_has_line(tmp_path):
    (tmp_path / "x.f").write_text("a.sv\n-y libdir\n")
    with pytest.raises(SvWeaveError) as e:
        read_filelist(str(tmp_path / "x.f"))
    assert e.value.diags[0].loc.line == 2


def test_recursive_filelist(tmp_path):
    (tmp_path / "x.f").write_text("-f x.f\n")
    with pytest.raises(SvWeaveError, match="includes itself"):
        read_filelist(str(tmp_path / "x.f"))


def test_unset_env(tmp_path, monkeypatch):
    monkeypatch.delenv("SVW_NOPE", raising=False)
    (tmp_path / "x.f").write_text("$SVW_NOPE/a.sv\n")
    with pytest.raises(SvWeaveError, match="SVW_NOPE"):
        read_filelist(str(tmp_path / "x.f"))
