"""Discovery of parameterised-class specialisations (design §4.3)."""
from .conftest import model_of

SRC = r'''
package p;
  class B; endclass
  class G #(int W=8, type T=int) extends B;
    bit [W-1:0] v; T t1;
    static function int k(); return W; endfunction
  endclass
  class C extends G#(16);                 // only in extends
    G#(4, G#(2)) n;                       // nested, as a property
    function void m(); G#(7) loc; endfunction   // subroutine local
    function G#(11) r(G#(12) a); return null; endfunction  // return and argument
  endclass
  typedef G#(32) a32_t;                   // typedef
  class D #(int K=1) extends G#(K*2); endclass
  class E; D#(3) d; G#(13) arr[$]; endclass   // via another specialisation; array element
endpackage
module top;
  initial begin
    int x;
    p::G#(5) l;                           // module-scope block local
    x = p::G#(9)::k();                    // only in an expression
  end
endmodule
'''


def test_all_specialisations_found():
    m = model_of(SRC)
    g = m.generic("G")
    assert sorted(int(s.params["W"]) for s in g.specializations) == [
        2, 4, 5, 6, 7, 9, 11, 12, 13, 16, 32]
    assert [s.qname for s in m.generic("D").specializations] == ["p::D#(3)"]
    nested = m.find_class("p::G#(4, p::G#(2, int))")
    assert nested.params == {"W": "4", "T": "p::G#(2, int)"}
    assert m.find_class("p::D#(3)").base.qname == "p::G#(6, int)"


def test_specialisation_members_and_spelling():
    m = model_of(SRC)
    s = m.find_class("p::G#(16, int)")
    assert s.type_expr == "p::G#(16, int)"
    assert s.is_specialization and s.generic.qname == "p::G"
    v = [f for f in s.fields if f.name == "v"][0]
    assert v.type.width == 16
    assert s.is_a("G") and s.is_a("p::G") and s.is_a("B")


def test_unused_default_specialisation_not_modelled():
    m = model_of("package p; class G #(int W=8); endclass endpackage\n")
    assert m.generic("G").specializations == []
    assert m.find_class("p::G#(8)") is None


def test_deterministic_order():
    a = [c.qname for c in model_of(SRC).classes()]
    b = [c.qname for c in model_of(SRC).classes()]
    assert a == b
