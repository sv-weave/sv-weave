"""Built-in weavers: diagnostics and options (P5)."""
import textwrap

import pytest

from sv_weave.config import parse_config
from sv_weave.diag import Severity, SvWeaveError
from sv_weave.run import run

SRC = """
package p;
  import reflib_pkg::*;
  class A extends ref_object;
    int a;
    local int la;
  endclass
  (* weave_nocopy *) class NoCopy extends ref_object; int n; endclass
endpackage
"""


def weave(yaml_body, src=SRC):
    cfg = parse_config("sv-weave:\n  binding: reflib\n" + textwrap.indent(textwrap.dedent(yaml_body), "  "))
    return run(cfg, texts=[("p.sv", src)], write=False)


def test_local_field_warns():
    res = weave("weavers: [{name: copy}]\n")
    w = [d for d in res.diags if d.severity == Severity.WARNING]
    assert len(w) == 1 and "p::A.la is local" in w[0].msg and w[0].loc.line == 6


def test_local_field_strict_errors():
    with pytest.raises(SvWeaveError, match="la is local"):
        weave("strict: true\nweavers: [{name: copy}]\n")


def test_class_opt_out():
    res = weave("weavers: [{name: copy}]\n")
    assert [wc.cls.name for wc in res.woven] == ["A"]
    assert res.selection.skipped["p::NoCopy"] == "no weaver subscription matches"


def test_all_core_weavers_verify():
    res = weave("weavers: [{name: copy}, {name: compare}, {name: print}]\n")
    assert res.verify_status == "full"
    assert set(res.woven[0].slots) >= {"copy", "compare", "sprint", "ref_impl_name"}


PROF = """
extension-sets: {core: {}, debug.xcheck: {}}
weavers:
- {name: copy}
- {name: %s, set: debug.xcheck}
profiles: {release: [core], debug: [core, "debug.*"]}
"""

SRC4 = """
package q;
  import reflib_pkg::*;
  class pkt extends ref_object; rand logic [7:0] addr; int n; endclass
endpackage
"""


def test_xcheck_passes_rand_safety():
    res = weave(PROF % "xcheck", src=SRC4)
    assert res.verify_status == "full"
    names = [(wc.name, wc.profiles) for wc in res.woven]
    assert names == [("Woven_pkt__release", ["release"]), ("Woven_pkt__debug", ["debug"])]
    text = res.file("q_woven.sv").text
    assert "function void post_randomize();" in text and "$isunknown(this.addr)" in text


def test_xcheck_variant_with_rand_rejected():
    from sv_weave import plugin
    from sv_weave.weavers.xcheck import XCheckWeaver

    class Bad(XCheckWeaver):
        name = "t_bad_xcheck"

        def weave(self, w):
            super().weave(w)
            w.add_item("rand bit __w_extra;")
    plugin.register_weaver(Bad)
    try:
        with pytest.raises(SvWeaveError, match="rand-safety: 'rand' from t_bad_xcheck"):
            weave(PROF % "t_bad_xcheck", src=SRC4)
    finally:
        plugin.unregister("t_bad_xcheck")
