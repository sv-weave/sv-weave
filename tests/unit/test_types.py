import pytest
from pyslang import ast as A

from sv_weave.frontend.loader import load_text
from sv_weave.frontend.types import ArrayKind, TypeCat, TypeConverter

SRC = r'''
package q; typedef struct packed { bit [3:0] a; } ps_t; class Q; endclass endpackage
package p;
  import q::*;
  typedef enum bit [1:0] {X,Y} pe_t;
  typedef int iq_t[$];
  class G #(int W=8, type T=int); endclass
  class B;
    typedef int e_t;
    e_t et; int i; logic signed [3:0] l4; real r; string s; chandle ch; event ev;
    pe_t pe; enum {A1,A2} ae; ps_t ps; struct { int x; } us;
    Q qh; G#(4) gh; G#(2, Q) gq;
    int q1[$]; int d1[]; int aa1[string]; bit [7:0] fa[4]; int fa2[2][3]; Q qq[$:3]; int aaw[*];
    iq_t iqt; bit [3:0][1:0] pk2;
  endclass
endpackage
'''

EXPECT = {
    # name: (cat, spelling, unpacked)
    "et": (TypeCat.INTEGRAL, "e_t", ""),
    "i": (TypeCat.INTEGRAL, "int", ""),
    "l4": (TypeCat.INTEGRAL, "logic signed [3:0]", ""),
    "r": (TypeCat.REAL, "real", ""),
    "s": (TypeCat.STRING, "string", ""),
    "ch": (TypeCat.CHANDLE, "chandle", ""),
    "ev": (TypeCat.EVENT, "event", ""),
    "pe": (TypeCat.ENUM, "p::pe_t", ""),
    "ae": (TypeCat.ENUM, None, ""),
    "ps": (TypeCat.STRUCT, "q::ps_t", ""),
    "us": (TypeCat.STRUCT, None, ""),
    "qh": (TypeCat.CLASS, "q::Q", ""),
    "gh": (TypeCat.CLASS, "p::G#(4, int)", ""),
    "gq": (TypeCat.CLASS, "p::G#(2, q::Q)", ""),
    "q1": (TypeCat.ARRAY, "int", "[$]"),
    "d1": (TypeCat.ARRAY, "int", "[]"),
    "aa1": (TypeCat.ARRAY, "int", "[string]"),
    "fa": (TypeCat.ARRAY, "bit [7:0]", "[0:3]"),
    "fa2": (TypeCat.ARRAY, "int", "[0:1][0:2]"),
    "qq": (TypeCat.ARRAY, "q::Q", "[$:3]"),
    "aaw": (TypeCat.ARRAY, "int", "[*]"),
    "iqt": (TypeCat.ARRAY, "p::iq_t", ""),
    "pk2": (TypeCat.INTEGRAL, "bit [3:0][1:0]", ""),
}


@pytest.fixture(scope="module")
def converted():
    l = load_text(SRC)
    tc = TypeConverter(frozenset(p.name for p in l.compilation.getPackages()))
    b = l.compilation.getPackage("p").find("B")
    out = {m.name: tc.convert(m.type) for m in b if m.kind == A.SymbolKind.ClassProperty}
    return l, out


@pytest.mark.parametrize("name", sorted(EXPECT))
def test_type(converted, name):
    _, out = converted
    t = out[name]
    assert (t.cat, t.spelling, t.unpacked) == EXPECT[name]


def test_details(converted):
    _, out = converted
    assert out["l4"].width == 4 and out["l4"].signed and out["l4"].four_state
    assert out["pe"].width == 2
    assert out["ps"].packed and out["ps"].width == 4
    assert out["fa2"].elem.array_kind == ArrayKind.FIXED and out["fa2"].elem.elem.spelling == "int"
    assert out["aa1"].index.cat == TypeCat.STRING
    assert out["aaw"].index is None
    assert out["qq"].elem.class_qname == "q::Q"
    assert not out["ae"].nameable
    with pytest.raises(ValueError):
        out["us"].declare("x")
