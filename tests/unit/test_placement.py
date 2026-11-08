"""Placement of contributions within a method section: first/append bands and
before/after relationships between weavers (design §6.3)."""
import json
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
    virtual function void build(); endfunction
  endclass
endpackage
"""


def L(section, text, **kw):
    return dict(section=section, text=text, **kw)


def build_body(weavers, extra=""):
    entries = "\n".join("  - {name: %s, options: %s%s}" % (n, json.dumps({"lines": lines}),
                                                         (", " + more) if more else "")
                        for n, lines, more in weavers)
    # Placeholder statements: ordering only, so no verification.
    cfg = parse_config("sv-weave:\n  binding: reflib\n  verify: off\n" + extra + "  weavers:\n"
                       + entries + "\n")
    res = run(cfg, texts=[("p.sv", SRC)], write=False)
    lines = [l.strip() for l in res.file("p_woven.sv").text.splitlines()]
    i = lines.index("virtual function void build();")
    j = lines.index("endfunction : build", i)
    return lines[i + 1:j]


def test_default_order_and_nesting():
    body = build_body([
        ("t_place_a", [L("pre", "a_pre;"), L("post", "a_post;"), L("decl", "int a;")], ""),
        ("t_place_b", [L("pre", "b_pre;"), L("post", "b_post;"), L("decl", "int b;")], ""),
    ])
    assert body == ["int a;", "int b;", "a_pre;", "b_pre;", "super.build();",
                    "b_post;", "a_post;"]


def test_first_prepends_within_section():
    body = build_body([
        ("t_place_a", [L("pre", "a_pre;")], ""),
        ("t_place_b", [L("pre", "b_pre;"), L("pre", "b_first;", first=True),
                       L("post", "b_post;")], ""),
        ("t_place_c", [L("post", "c_first;", first=True), L("post", "c_post;")], ""),
    ])
    assert body == ["b_first;", "a_pre;", "b_pre;", "super.build();",
                    "c_first;", "c_post;", "b_post;"]


def test_fragment_before_after():
    body = build_body([
        ("t_place_a", [L("pre", "a_pre;", after=["t_place_b"]),
                       L("post", "a_post;", before=["t_place_b"])], ""),
        ("t_place_b", [L("pre", "b_pre;"), L("post", "b_post;")], ""),
    ])
    assert body == ["b_pre;", "a_pre;", "super.build();", "a_post;", "b_post;"]


def test_config_relationship_applies_to_every_section():
    body = build_body([
        ("t_place_a", [L("pre", "a_pre;"), L("post", "a_post;")], ""),
        ("t_place_b", [L("pre", "b_pre;"), L("post", "b_post;")], "before: [t_place_a]"),
    ])
    # Textual: b's content precedes a's in pre AND in post.
    assert body == ["b_pre;", "a_pre;", "super.build();", "b_post;", "a_post;"]


def test_relationship_overrides_first_band():
    body = build_body([
        ("t_place_a", [L("pre", "a_first;", first=True)], "after: [t_place_b]"),
        ("t_place_b", [L("pre", "b_pre;")], ""),
    ])
    assert body == ["b_pre;", "a_first;", "super.build();"]


def test_weaver_class_relationship(test_weavers):
    from sv_weave import plugin
    from tests.test_weavers import TPlace

    class Late(TPlace):
        name = "t_place_late"
        after = ("t_place_b",)
    plugin.register_weaver(Late)
    try:
        body = build_body([
            ("t_place_late", [L("pre", "late;")], "order: -5"),
            ("t_place_b", [L("pre", "b_pre;")], ""),
        ])
    finally:
        plugin.unregister("t_place_late")
    assert body == ["b_pre;", "late;", "super.build();"]


def test_contradiction_is_an_error():
    with pytest.raises(SvWeaveError, match="contradictory before/after relationships in "
                                           "build.pre between t_place_a, t_place_b"):
        build_body([
            ("t_place_a", [L("pre", "a_pre;")], "before: [t_place_b]"),
            ("t_place_b", [L("pre", "b_pre;")], "before: [t_place_a]"),
        ])


def test_unknown_name_is_ignored():
    body = build_body([("t_place_a", [L("pre", "a_pre;", before=["nobody"])], "")])
    assert body == ["a_pre;", "super.build();"]
