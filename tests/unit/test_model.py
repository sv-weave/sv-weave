"""SvModel: classes, inheritance, members, attributes and queries."""
import pytest

from sv_weave.diag import SvWeaveError
from sv_weave.frontend.model import ArgDir, MethodKind, RandMode, Visibility
from sv_weave.frontend.types import ArrayKind, TypeCat

from .conftest import model_of

UVM_STUB = """
package uvm_pkg;
  virtual class uvm_void; endclass
  class uvm_object extends uvm_void;
    function new(string name = ""); endfunction
    virtual function void do_copy(uvm_object rhs); endfunction
  endclass
endpackage
"""

CHAIN = """
package base_pkg;
  class A extends uvm_pkg::uvm_object;
    int a_fld;
    function new(string name = "A"); super.new(name); endfunction
  endclass
endpackage
package top_pkg;
  import base_pkg::*;
  class B extends A;
    rand int b_fld;
    function new(string name = "B"); super.new(name); endfunction
  endclass
  class C extends B;
    randc bit [3:0] c_fld;
    function new(string name = "C"); super.new(name); endfunction
  endclass
endpackage
"""


def test_inheritance_chain_across_packages():
    m = model_of(UVM_STUB, CHAIN, runtime=False)
    c = m.find_class("top_pkg::C")
    assert [x.qname for x in c.ancestors()] == [
        "top_pkg::B", "base_pkg::A", "uvm_pkg::uvm_object", "uvm_pkg::uvm_void"]
    assert c.package == "top_pkg" and c.type_expr == "top_pkg::C"
    assert [f.name for f in c.all_fields()] == ["a_fld", "b_fld", "c_fld"]
    uo = m.find_class("uvm_pkg::uvm_object")
    assert [f.name for f in c.all_fields(upto=uo)] == ["a_fld", "b_fld", "c_fld"]
    assert [f.name for f in c.all_fields(upto=m.find_class("base_pkg::A"))] == ["b_fld", "c_fld"]
    assert c.find_method("do_copy").owner is uo
    assert c.is_a("uvm_object") and c.is_a("base_pkg::A") and not c.is_a("X")
    assert m.find_class("uvm_void").is_abstract


def test_members():
    m = model_of("""
    package p;
      class B;
        rand int r; randc bit [1:0] rc; static int s; local int l; protected int pr;
        const int k = 1;
        (* weave_nocopy, weave_n = 3, weave_s = "txt" *) int at;
        int q[$]; string aa[int]; bit [7:0] fa[4];
        function new(); endfunction
        virtual function int vf(input int i, output int o, inout int io, ref int r, const ref int cr, input int d = 2 + 1);
          return 0;
        endfunction
        virtual task vt(); endtask
        static function void sf(); endfunction
        function void nv(); endfunction
        local function void lf(); endfunction
        extern virtual function void ext();
      endclass
      function void B::ext(); endfunction
      virtual class V; pure virtual function void pv(); endclass
      class D extends B; function int vf(input int i, output int o, inout int io, ref int r, const ref int cr, input int d = 2 + 1); return 1; endfunction endclass
    endpackage
    """)
    b = m.find_class("p::B")
    f = {x.name: x for x in b.fields}
    assert f["r"].rand == RandMode.RAND and f["rc"].rand == RandMode.RANDC
    assert f["s"].static and not f["r"].static
    assert f["l"].visibility == Visibility.LOCAL and f["pr"].visibility == Visibility.PROTECTED
    assert f["k"].const and not f["r"].const
    assert f["at"].attrs == {"weave_nocopy": True, "weave_n": 3, "weave_s": "txt"}
    assert f["q"].type.array_kind == ArrayKind.QUEUE
    assert f["aa"].type.declare("x") == "string x[int]"
    assert f["fa"].type.declare("x") == "bit [7:0] x[0:3]"

    meth = {x.name: x for x in b.methods}
    assert meth["new"].is_constructor and meth["new"].ret is None
    vf = meth["vf"]
    assert vf.virtual and vf.kind == MethodKind.FUNCTION and vf.ret.spelling == "int"
    assert [a.dir for a in vf.args] == [ArgDir.INPUT, ArgDir.OUTPUT, ArgDir.INOUT,
                                        ArgDir.REF, ArgDir.CONST_REF, ArgDir.INPUT]
    assert vf.args[-1].default == "2 + 1"
    assert vf.args[-1].declare() == "input int d = 2 + 1"
    assert meth["vt"].kind == MethodKind.TASK and meth["vt"].ret is None
    assert meth["sf"].static and not meth["sf"].virtual
    assert not meth["nv"].virtual
    assert meth["lf"].visibility == Visibility.LOCAL
    assert meth["ext"].virtual and not meth["ext"].pure
    assert "randomize" not in meth

    v = m.find_class("p::V")
    assert v.is_abstract and v.methods[0].pure
    assert [x.name for x in v.unimplemented_pure()] == ["pv"]
    # An override without the keyword is still virtual.
    assert m.find_class("p::D").methods[0].virtual


def test_interface_classes():
    m = model_of("""
    package p;
      interface class I; pure virtual function void f(); endclass
      interface class J extends I; endclass
      class A implements J; virtual function void f(); endfunction endclass
      class B extends A; endclass
      virtual class Ab implements I; pure virtual function void f(); endclass
    endpackage
    """)
    i = m.find_class("p::I")
    assert i.is_interface and i.is_abstract
    assert m.find_class("p::B").implements_iface("I")
    assert [c.qname for c in m.implementors_of("p::I")] == ["p::A", "p::B"]
    assert [c.qname for c in m.implementors_of("I", concrete=False)] == ["p::A", "p::Ab", "p::B"]


def test_class_attributes():
    m = model_of("""
    package p;
      (* weave_off *) class A; endclass
      (* weave_weight = 5, weave_tag = "x" *) class G #(int W = 1); endclass
      class U; G#(2) g; endclass
    endpackage
    """)
    assert m.find_class("p::A").attrs == {"weave_off": True}
    assert m.find_class("p::G#(2)").attrs == {"weave_weight": 5, "weave_tag": "x"}
    assert m.generic("G").attrs == {"weave_weight": 5, "weave_tag": "x"}


def test_queries_concrete_and_transitive():
    m = model_of("""
    package p;
      virtual class T; endclass
      class A extends T; endclass
      virtual class AbsB extends T; endclass
      class C extends AbsB; endclass
      class P #(int W = 1) extends T; endclass
      class U; P#(3) p3; P#(5) p5; endclass
    endpackage
    """)
    names = lambda cs: [c.qname for c in cs]
    assert names(m.subclasses_of("T")) == ["p::A", "p::C", "p::P#(3)", "p::P#(5)"]
    assert names(m.subclasses_of("p::T", concrete=False)) == [
        "p::A", "p::AbsB", "p::C", "p::P#(3)", "p::P#(5)"]
    assert names(m.subclasses_of("T", transitive=False)) == ["p::A", "p::P#(3)", "p::P#(5)"]
    assert names(m.subclasses_of(m.find_class("p::AbsB"))) == ["p::C"]
    assert [p.name for p in m.packages()] == ["reflib_pkg", "p"]


def test_unresolved_base_is_an_error():
    with pytest.raises(SvWeaveError, match="base class of 'p::A' could not be resolved"):
        model_of("package p; class A extends Missing; endclass endpackage\n")


def test_unit_scope_classes_are_modelled():
    m = model_of("class U; int x; endclass\nclass A extends U; endclass\n")
    u = m.find_class("U")
    assert u is not None and u.package is None
    assert m.find_class("A").base is u
