"""The syntax pre-pass (Bus.on_syntax): a weaver generates a base class that the user's
sources extend before it exists."""
import os
import textwrap

import pytest

from sv_weave import plugin
from sv_weave.config import parse_config
from sv_weave.diag import SvWeaveError
from sv_weave.filelist import SourceSpec
from sv_weave.run import PRE_FILELIST, run

from .test_design import EXAMPLE

SRC = """
package pgen_user;
  import reflib_pkg::*;
  import pgen_base_pkg::*;
  (* t_base = "ref_object" *) class foo #(int W = 4) extends foo_base #(W);
    virtual function void build(); endfunction
  endclass
  class bar extends ref_object;
  endclass
endpackage
"""


class _Gen(plugin.Weaver):
    """Writes ``<C>_base`` (extending the class the attribute names) for each class
    with ``t_base``, in package ``pgen_base_pkg``."""
    name = "t_gen"

    def subscribe(self, bus):
        bus.on_syntax(self.gen)

    def gen(self, s):
        lines = ["package pgen_base_pkg;", "  import reflib_pkg::*;"]
        for c in s.classes("t_base"):
            lines += ["  virtual class %s_base %s extends %s;" % (c.name, c.params,
                                                                   c.attr_string("t_base")),
                      "    bit [W-1:0] gen_field;",
                      "    pure virtual function void build();",
                      "  endclass"]
        lines.append("endpackage")
        s.add_source("pgen_base_pkg.sv", "\n".join(lines) + "\n")


@pytest.fixture
def gen_weaver():
    plugin.register_weaver(_Gen)
    yield _Gen
    plugin.unregister("t_gen")


def _weave(src=SRC, out_dir=None, write=False, verify="full"):
    cfg = parse_config("sv-weave:\n  binding: reflib\n" + textwrap.indent(textwrap.dedent("""\
        weavers:
          - {name: t_gen}
        """), "  "))
    spec = SourceSpec(files=[os.path.join(EXAMPLE, "select_pkg.sv")])
    return run(cfg, spec=spec, texts=[("p.sv", src)], out_dir=out_dir, write=write,
               verify=verify)


def test_classes_sees_attributes():
    from sv_weave.frontend.loader import load_text
    from sv_weave.frontend.syntax import syntax_classes
    ld = load_text("package q; (* a = \"x\", b *) class c #(int N = 2) extends d #(N); "
                   "endclass class d #(int N = 1); endclass endpackage")
    cs = {c.name: c for c in syntax_classes(ld.trees, ld.source_manager)}
    c = cs["c"]
    assert c.package == "q" and c.qname == "q::c"
    assert c.attrs == {"a": '"x"', "b": None} and c.attr_string("a") == "x"
    assert c.base == "d" and c.base_args == "#(N)" and c.params == "#(int N = 2)"
    assert c.loc is not None and c.loc.line == 1
    assert cs["d"].attrs == {} and cs["d"].base == ""


def test_generated_base_elaborates(gen_weaver, tmp_path):
    res = _weave(out_dir=str(tmp_path), write=True)
    assert res.pre_files == ["pgen_base_pkg.sv"]
    assert res.verify_status == "full"
    pre = tmp_path / "pgen_base_pkg.sv"
    assert "virtual class foo_base #(int W = 4) extends ref_object;" in pre.read_text()
    assert (tmp_path / PRE_FILELIST).read_text() == str(pre) + "\n"
    # Not in the woven compile order: it goes before the user's sources.
    assert "pgen_base_pkg.sv" not in res.compile_order
    assert res.manifest["files"]["pre"] == ["pgen_base_pkg.sv"]
    assert "pgen_base_pkg.sv" in res.generated_names


def test_without_weaver_base_is_missing():
    cfg = parse_config("sv-weave:\n  binding: reflib\n")
    spec = SourceSpec(files=[os.path.join(EXAMPLE, "select_pkg.sv")])
    with pytest.raises(SvWeaveError):
        run(cfg, spec=spec, texts=[("p.sv", SRC)], write=False)


def test_error_in_added_source_points_at_it(gen_weaver, tmp_path, monkeypatch):
    monkeypatch.setattr(_Gen, "gen", lambda self, s: s.add_source(
        "bad_pkg.sv", "package pgen_base_pkg;\n  typedef no_such_t t;\n"
        "endpackage\n"))
    with pytest.raises(SvWeaveError) as ei:
        _weave(out_dir=str(tmp_path), write=True)
    assert any(d.loc is not None and d.loc.file.endswith("bad_pkg.sv") for d in ei.value.diags)
    assert (tmp_path / "bad_pkg.sv").exists()


@pytest.mark.parametrize("name,msg", [("../x.sv", "bad file name"),
                                      ("sv_weave.f", "clash")])
def test_add_source_bad_names(gen_weaver, monkeypatch, name, msg):
    monkeypatch.setattr(_Gen, "gen", lambda self, s: s.add_source(name, "package z; endpackage\n"))
    with pytest.raises(SvWeaveError) as ei:
        _weave()
    assert any(msg in d.msg for d in ei.value.diags)
