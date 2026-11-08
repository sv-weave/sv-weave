import pytest

from sv_weave.diag import SvWeaveError
from sv_weave.match import (extends, has_attr, has_field, has_method, implements, in_package,
                            is_a, is_abstract, named, parse)

from .conftest import model_of

SRC = """
package eth_pkg;
  interface class put_if; pure virtual function void put(); endclass
  virtual class base; endclass
  (* weave_trace *)
  class pkt extends base implements put_if;
    rand int len; static int count; (* weave_nocopy *) int scratch;
    virtual function void put(); endfunction
    function void build(); endfunction
  endclass
  class big_pkt extends pkt; endclass
  class G #(int W = 1) extends base; endclass
  class U; G#(4) g; endclass
endpackage
package other_pkg; class lone; int x; endclass endpackage
"""


@pytest.fixture(scope="module")
def m():
    return model_of(SRC, runtime=False)


def names(m, pred):
    return [c.qname for c in m.classes(pred)]


def test_predicates(m):
    assert names(m, extends("base")) == ["eth_pkg::G#(4)", "eth_pkg::big_pkt", "eth_pkg::pkt"]
    assert names(m, extends("eth_pkg::pkt")) == ["eth_pkg::big_pkt"]
    assert names(m, is_a("pkt")) == ["eth_pkg::big_pkt", "eth_pkg::pkt"]
    assert names(m, extends("G")) == []
    assert names(m, is_a("G")) == ["eth_pkg::G#(4)"]
    assert names(m, implements("put_if")) == ["eth_pkg::big_pkt", "eth_pkg::pkt"]
    assert names(m, has_attr("weave_trace")) == ["eth_pkg::pkt"]
    assert names(m, has_method("build")) == ["eth_pkg::big_pkt", "eth_pkg::pkt"]
    assert names(m, has_method("put", virtual=True) & ~is_abstract()) == [
        "eth_pkg::big_pkt", "eth_pkg::pkt"]
    assert names(m, in_package("other_*")) == ["other_pkg::lone"]
    assert names(m, has_field(lambda f: f.rand.value == "rand")) == ["eth_pkg::big_pkt", "eth_pkg::pkt"]
    assert names(m, has_field("*", static=True)) == ["eth_pkg::big_pkt", "eth_pkg::pkt"]
    assert names(m, has_field(attr="weave_nocopy") & ~extends("pkt")) == ["eth_pkg::pkt"]
    assert names(m, named("*pkt") & in_package("eth_*")) == ["eth_pkg::big_pkt", "eth_pkg::pkt"]
    assert names(m, named("eth_pkg::G")) == ["eth_pkg::G#(4)"]


@pytest.mark.parametrize("text", [
    "extends(base)",
    "extends(uvm_sequence_item) & ~has_attr(weave_nocopy)",
    "(extends(a) | extends(b)) & in_package(eth_*)",
    "~(named(x) & named(y))",
    "has_method(build, virtual=true)",
    "has_field(len, rand=true)",
    'is_a("p::G#(8, int)")',
    "any() | is_abstract()",
])
def test_round_trip(text):
    p = parse(text)
    assert str(parse(str(p))) == str(p)
    assert str(p) == text


def test_parse_semantics(m):
    p = parse("extends(base) & ~has_attr(weave_trace) | named(lone)")
    assert names(m, p) == names(m, (extends("base") & ~has_attr("weave_trace")) | named("lone"))
    assert names(m, parse("has_field(len, rand=true)")) == ["eth_pkg::big_pkt", "eth_pkg::pkt"]


@pytest.mark.parametrize("text,needle", [
    ("extends(a", "expected ')'"),
    ("frobnicate(a)", "unknown predicate 'frobnicate'"),
    ("extends(a) &", "expected a predicate"),
    ("extends(a, b)", "takes 1 argument"),
    ("extends(a) extends(b)", "unexpected 'extends'"),
    ("extends(a) @ x", "unexpected character '@'"),
    ("", "empty match expression"),
])
def test_parse_errors(text, needle):
    with pytest.raises(SvWeaveError, match=needle.replace("(", r"\(").replace(")", r"\)")):
        parse(text, where="weavers[0].match")
