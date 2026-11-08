"""Verify (P4): elaboration of the woven code, rand-safety rules, levels and cache."""
import json
import os
import textwrap

import pytest

from sv_weave.config import parse_config
from sv_weave.diag import SvWeaveError
from sv_weave.run import run

pytestmark = pytest.mark.usefixtures("test_weavers")

SRC = """
package p;
  import reflib_pkg::*;
  class A extends ref_object;
    rand int x;
    int y;
    virtual function void build(); endfunction
  endclass
endpackage
"""

TEST_WEAVERS = os.path.join(os.path.dirname(__file__), "..", "..", "test_weavers.py")


def frag_line():
    with open(TEST_WEAVERS) as fp:
        for i, l in enumerate(fp, 1):
            if "FRAG_BODY_LINE" in l:
                return i


def cfg_for(opts, ext_set="core", flags="{}", verify="full"):
    return parse_config(textwrap.dedent("""
        sv-weave:
          binding: reflib
          verify: %s
          extension-sets: {core: {}, debug: %s}
          weavers:
          - {name: t_frag, set: %s, options: %s}
          profiles: {release: [core], debug: [core, debug]}
          build-profiles: [debug]
        """) % (verify, flags, ext_set, json.dumps(opts)))


def weave(opts, ext_set="core", flags="{}", verify="full", **kw):
    return run(cfg_for(opts, ext_set, flags, verify), texts=[("p.sv", SRC)], write=False, **kw)


RULES = [
    # (flag, fragment option, text)
    ("allow_rand", "body", "void'(randomize());"),
    ("allow_rand", "body", "y = $urandom();"),
    ("allow_rand", "body", "y = $urandom_range(3);"),
    ("allow_rand", "body", "this.srandom(1);"),
    ("allow_rand,allow_state", "item", "rand int __w_r;"),
    ("allow_rand", "item", "constraint __w_c { x < 10; }"),
    ("allow_state", "item", "int __w_count;"),
    ("allow_alloc", "body", "begin ref_object o; o = ref_factory#(A)::create(); end"),
    ("allow_alloc", "item", "function void __w_mk(); A a = new(); endfunction"),
    ("allow_threads", "body", "fork begin end join_none"),
]


@pytest.mark.parametrize("flag,where,text", RULES)
def test_rule_rejected_in_restricted_set(flag, where, text):
    with pytest.raises(SvWeaveError) as e:
        weave({where: text}, ext_set="debug")
    msgs = [d.msg for d in e.value.diags if d.code == "rand-safety"]
    assert msgs and all("extension set 'debug'" in m for m in msgs)
    for f in flag.split(","):
        assert any(f in m for m in msgs), "\n".join(str(d) for d in e.value.diags)


@pytest.mark.parametrize("flag,where,text", RULES)
def test_rule_allowed_in_core(flag, where, text):
    res = weave({where: text}, ext_set="core")
    assert res.verify_status == "full"


@pytest.mark.parametrize("flag,where,text", RULES)
def test_rule_allowed_by_flag(flag, where, text):
    res = weave({where: text}, ext_set="debug",
                flags="{%s}" % ", ".join("%s: true" % f for f in flag.split(",")))
    assert res.verify_status == "full"


def test_safe_debug_code_passes():
    res = weave({"body": '$display("x=%0d", x);'}, ext_set="debug")
    assert res.verify_status == "full"


def test_rule_error_points_at_weaver():
    with pytest.raises(SvWeaveError) as e:
        weave({"body": "y = $urandom();"}, ext_set="debug")
    d = [d for d in e.value.diags if d.code == "rand-safety"][0]
    assert d.loc.file.endswith("test_weavers.py") and d.loc.line == frag_line()
    assert "woven code" in d.msg and "p_woven.sv" in d.msg


def test_elaboration_error_points_at_weaver():
    with pytest.raises(SvWeaveError) as e:
        weave({"body": "no_such_var = 1;"})
    d = e.value.diags[0]
    assert "no_such_var" in d.msg and "from t_frag[core]" in d.msg
    assert d.loc.file.endswith("test_weavers.py") and d.loc.line == frag_line()


def test_syntax_level_catches_rules_not_types():
    with pytest.raises(SvWeaveError, match="rand-safety"):
        weave({"body": "y = $urandom();"}, ext_set="debug", verify="syntax")
    # An undeclared name is not a syntax error: only full catches it.
    res = weave({"body": "no_such_var = 1;"}, verify="syntax")
    assert res.verify_status == "syntax"
    with pytest.raises(SvWeaveError):
        weave({"body": "no_such_var = 1;"}, verify="full")


def test_syntax_level_catches_parse_errors():
    with pytest.raises(SvWeaveError, match="from t_frag"):
        weave({"body": "if (x) begin"}, verify="syntax")


def test_off():
    res = weave({"body": "no_such_var = 1;"}, verify="off")
    assert res.verify_status == "off"


def test_cache_and_failed_dir(tmp_path):
    out = str(tmp_path)
    cfg = cfg_for({"body": '$display("ok");'})
    r1 = run(cfg, texts=[("p.sv", SRC)], out_dir=out)
    assert r1.verify_status == "full"
    m1 = (tmp_path / "weave-manifest.json").read_text()
    r2 = run(cfg, texts=[("p.sv", SRC)], out_dir=out)
    assert r2.verify_status == "cached" and r2.changed == []
    assert (tmp_path / "weave-manifest.json").read_text() == m1
    # Different output: verified again.
    r3 = run(cfg_for({"body": '$display("ok2");'}), texts=[("p.sv", SRC)], out_dir=out)
    assert r3.verify_status == "full"
    # A failure writes .failed/ and leaves the previous outputs alone.
    with pytest.raises(SvWeaveError, match=r"\.failed"):
        run(cfg_for({"body": "no_such_var = 1;"}), texts=[("p.sv", SRC)], out_dir=out)
    assert "no_such_var" in (tmp_path / ".failed" / "p_woven.sv").read_text()
    assert "ok2" in (tmp_path / "p_woven.sv").read_text()
    # The next good run removes .failed/.
    run(cfg, texts=[("p.sv", SRC)], out_dir=out)
    assert not (tmp_path / ".failed").exists()


def test_structure_abstract_woven_class():
    src = SRC + """
package q;
  import reflib_pkg::*;
  virtual class V extends ref_object;
    pure virtual function void f();
    virtual function void build(); endfunction
  endclass
endpackage
"""
    cfg = cfg_for({"body": '$display("v");'})
    res = run(cfg, texts=[("p.sv", src)], write=False)
    v = [wc for wc in res.woven if wc.cls.qname == "q::V"][0]
    assert not v.concrete
    assert "virtual class Woven_V__debug" in res.file("q_woven.sv").text
    assert "Woven_V__debug__impl" not in res.file("q_woven.sv").text


def test_unknown_level():
    with pytest.raises(SvWeaveError, match="unknown verify level"):
        run(cfg_for({"body": "x = 1;"}), texts=[("p.sv", SRC)], write=False, verify="fast")


def test_yaml_off_is_off():
    assert cfg_for({}, verify="off").verify == "off"
