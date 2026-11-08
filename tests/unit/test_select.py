import pytest

from sv_weave.config import Config, parse_config
from sv_weave.diag import SvWeaveError
from sv_weave import plugin
from sv_weave.diag import SvWeaveError
from sv_weave.select import StubBinding, select


def builtin_bindings(names):
    return [plugin.find(plugin.BINDING_GROUP, n)() for n in names]

from .conftest import model_of
from .test_model import UVM_STUB

SRC = """
package a_pkg;
  import reflib_pkg::*;
  class A extends ref_object; int x; endclass
  (* weave_off *) class Off extends A; endclass
  virtual class Abs extends A; pure virtual function void f(); endclass
  class P #(int W = 4) extends A; bit [W-1:0] v; endclass
  class Q extends P#(8); endclass
  class Plain; endclass
  interface class I; endclass
endpackage
package a_tb_pkg; import reflib_pkg::*; class T extends ref_object; endclass endpackage
"""


def targets(sel):
    return [t.cls.qname for t in sel.targets]


def test_reflib_selection():
    m = model_of(SRC)
    sel = select(m, Config(), builtin_bindings(["reflib"]))
    assert targets(sel) == ["a_pkg::A", "a_pkg::Abs", "a_pkg::P#(8)", "a_pkg::Q", "a_tb_pkg::T"]
    assert sel.skipped["a_pkg::Off"] == "(* weave_off *)"
    assert sel.skipped["a_pkg::Plain"] == "no binding root among its base classes"
    assert sel.skipped["a_pkg::I"] == "interface class"
    assert sel.skipped["reflib_pkg::ref_object"] == "no binding root among its base classes"
    assert sel.target("a_pkg::Q").root.qname == "reflib_pkg::ref_object"


def test_package_filter_and_wanted():
    cfg = parse_config("sv-weave:\n  binding: reflib\n  packages: {include: ['a_*'], exclude: ['*_tb_pkg']}\n")
    m = model_of(SRC)
    sel = select(m, cfg, builtin_bindings(["reflib"]), wanted=lambda c: c.name != "A")
    assert targets(sel) == ["a_pkg::Abs", "a_pkg::P#(8)", "a_pkg::Q"]
    assert sel.skipped["a_pkg::A"] == "no weaver subscription matches"
    assert sel.skipped["a_tb_pkg::T"] == "package 'a_tb_pkg' not selected"


def test_extern_root_from_stub_uvm():
    m = model_of(UVM_STUB, "package t_pkg; class X extends uvm_pkg::uvm_object; endclass endpackage\n",
                 runtime=False)
    sel = select(m, Config(), [StubBinding("uvm", ["uvm_pkg::uvm_object"])])
    assert targets(sel) == ["t_pkg::X"]
    # uvm_pkg is never woven, even when the include globs match it.
    assert sel.skipped["uvm_pkg::uvm_object"] == "package 'uvm_pkg' not selected"


def test_two_bindings_claim_is_error():
    m = model_of(SRC)
    with pytest.raises(SvWeaveError, match="claimed by bindings plain, other"):
        select(m, Config(), [StubBinding("plain", ["ref_object"]),
                             StubBinding("other", ["a_pkg::A"])])


def test_unknown_binding():
    with pytest.raises(SvWeaveError, match="unknown binding 'nope'"):
        builtin_bindings(["nope"])
