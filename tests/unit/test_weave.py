"""Weave core: bus order, slots, ctx, check and render (P2)."""
import textwrap

import pytest

from sv_weave.config import parse_config
from sv_weave.diag import Severity, SvWeaveError
from sv_weave.filelist import SourceSpec
from sv_weave.frontend.loader import load
from sv_weave.run import run

pytestmark = pytest.mark.usefixtures("test_weavers")

SRC = """
package p;
  import reflib_pkg::*;
  class A extends ref_object;
    int a; protected int pa; local int la; static int sa; const int ca = 1;
    (* weave_nocopy *) int nc;
    function new(string name = "A"); endfunction
    virtual function void build(); endfunction
    function void nonvirt(); endfunction
    virtual function int calc(int x, output int y); y = x; return x; endfunction
  endclass
  class B extends A;
    int b;
    function new(string name = "B"); super.new(name); endfunction
  endclass
endpackage
"""


def weave(yaml_body, src=SRC, **kw):
    cfg = parse_config("sv-weave:\n  binding: reflib\n" + textwrap.indent(textwrap.dedent(yaml_body), "  "))
    return run(cfg, texts=[("p.sv", src)], write=False, **kw)


def text_of(res, pkg="p_woven.sv"):
    return res.file(pkg).text


def block(text, start, end):
    """The lines from the one containing ``start`` to the next one containing ``end``."""
    lines = text.splitlines()
    i = next(k for k, l in enumerate(lines) if start in l)
    j = next(k for k in range(i, len(lines)) if end in lines[k])
    return [l.strip() for l in lines[i:j + 1]]


def test_slot_order_two_weavers():
    res = weave("""
        weavers:
        - {name: t_build, options: {tag: X}}
        - {name: t_build2, options: {tag: Y}}
        """)
    b = block(text_of(res), "class Woven_A__release", "endclass")
    body = block("\n".join(b), "function void build", "endfunction")
    assert body == [
        "virtual function void build();",
        '$display("X: pre build A");',
        '$display("Y: pre build A");',
        "super.build();",
        '$display("Y: post build A");',      # post: reverse contributor order
        '$display("X: post build A");',
        "endfunction : build",
    ]


def test_config_order_overrides_name_order():
    res = weave("""
        weavers:
        - {name: t_build, options: {tag: X}, order: 2}
        - {name: t_build2, options: {tag: Y}, order: 1}
        """)
    body = block(text_of(res), "function void build", "endfunction")
    assert body[1] == '$display("Y: pre build A");'


def test_copy_flattens_and_skips():
    res = weave("weavers: [{name: t_copy}]\n")
    copy_b = block(text_of(res), "Woven_B__release extends", "endclass")
    stmts = [l for l in copy_b if l.startswith("this.")]
    assert stmts == ["this.a = __w_rhs.a;", "this.pa = __w_rhs.pa;", "this.b = __w_rhs.b;"]
    warns = [d for d in res.diags if d.severity == Severity.WARNING]
    assert len(warns) == 1 and "p::A.la is local" in warns[0].msg
    assert warns[0].loc.file == "p.sv" and warns[0].loc.line == 5


def test_strict_makes_local_an_error():
    with pytest.raises(SvWeaveError, match="la is local"):
        weave("strict: true\nweavers: [{name: t_copy}]\n")


def test_constructor_forwarded_with_defaults():
    res = weave("weavers: [{name: t_build}]\n")
    b = "\n".join(block(text_of(res), "class Woven_B__release", "endclass"))
    ctor = block(b, "function new", "endfunction")
    assert ctor == ['function new(input string name = "B");', "super.new(name);",
                    "endfunction : new"]


def test_non_virtual_override_reported_at_user_line(test_weavers):
    from sv_weave import plugin

    class Bad(plugin.Weaver):
        name = "t_nonvirt"

        def subscribe(self, bus):
            from sv_weave.match import named
            bus.on(named("A"), lambda w: w.override("nonvirt").body.add("// x"))
    plugin.register_weaver(Bad)
    try:
        with pytest.raises(SvWeaveError) as e:
            weave("weavers: [{name: t_nonvirt}]\n")
        d = e.value.diags[0]
        assert "p::A::nonvirt is not virtual; cannot weave" in d.msg
        assert d.loc.file == "p.sv" and d.loc.line == 9
    finally:
        plugin.unregister("t_nonvirt")


def test_replace_super_exclusive():
    with pytest.raises(SvWeaveError, match="replace_super already set by t_replace"):
        weave("weavers: [{name: t_replace}, {name: t_replace2}]\n")


def test_replace_super_single():
    res = weave("weavers: [{name: t_replace}]\n")
    body = block(text_of(res), "function void build", "endfunction")
    assert "super.build();" not in body and '$display("replaced");' in body


def test_function_result_from_super():
    from sv_weave import plugin

    class Calc(plugin.Weaver):
        name = "t_calc"

        def subscribe(self, bus):
            from sv_weave.match import named
            bus.on(named("A"), lambda w: w.override("calc").body.add("__w_ret += 1;"))
    plugin.register_weaver(Calc)
    try:
        res = weave("weavers: [{name: t_calc}]\n")
    finally:
        plugin.unregister("t_calc")
    body = block(text_of(res), "function int calc", "endfunction")
    assert body == ["virtual function int calc(input int x, output int y);", "int __w_ret;",
                    "__w_ret = super.calc(x, y);", "__w_ret += 1;", "return __w_ret;",
                    "endfunction : calc"]


def test_add_field_needs_allow_state():
    with pytest.raises(SvWeaveError, match="does not allow_state"):
        weave("""
            extension-sets: {core: {}, debug: {}}
            weavers: [{name: t_state, set: debug}]
            profiles: {release: [core], debug: [core, debug]}
            """)
    res = weave("""
        extension-sets: {core: {}, debug: {allow_state: true}}
        weavers: [{name: t_state, set: debug}]
        profiles: {release: [core], debug: [core, debug]}
        """)
    names = [wc.name for wc in res.woven]
    # Only the debug profile includes the weaver's set; release has nothing to weave.
    assert names == ["Woven_A__debug", "Woven_B__debug"]
    assert "int unsigned __w_seen;" in text_of(res)


def test_fresh_avoids_member_names():
    src = SRC.replace("int b;", "int b; int __w_seen;")
    res = weave("""
        extension-sets: {core: {allow_state: true}}
        weavers: [{name: t_state}]
        """, src=src)
    b = block(text_of(res), "class Woven_B__release", "endclass")
    assert "int unsigned __w_seen_1;" in b


def test_weaver_exception_is_reported():
    with pytest.raises(SvWeaveError, match="t_boom failed on p::A: KeyError"):
        weave("weavers: [{name: t_boom}]\n")


def test_match_narrows():
    res = weave("weavers: [{name: t_build, match: 'named(B)'}]\n")
    assert [wc.name for wc in res.woven] == ["Woven_B__release"]
    assert res.selection.skipped["p::A"] == "no weaver subscription matches"


def test_abstract_not_registered():
    src = SRC + """
package q;
  import reflib_pkg::*;
  virtual class V extends ref_object;
    pure virtual function void f();
    virtual function void build(); endfunction
  endclass
endpackage
"""
    res = weave("weavers: [{name: t_build}]\n", src=src)
    v = [wc for wc in res.woven if wc.cls.qname == "q::V"][0]
    assert not v.concrete and v.unimplemented == ["f"]
    assert any(d.severity == Severity.NOTE and "not registered" in d.msg for d in res.diags)


def test_line_map_points_at_weaver():
    res = weave("weavers: [{name: t_build}]\n")
    f = res.file("p_woven.sv")
    line = next(i for i, l in enumerate(f.text.splitlines(), 1) if "pre build A" in l)
    o = f.origin_at(line)
    assert o.contributor == "t_build" and o.ext_set == "core"
    assert o.file.endswith("tests/test_weavers.py")


def test_deterministic():
    a = weave("weavers: [{name: t_build}, {name: t_copy}]\n")
    b = weave("weavers: [{name: t_copy}, {name: t_build}]\n")
    assert a.output_hash == b.output_hash
    assert text_of(a) == text_of(b)


def test_output_elaborates():
    """The woven package compiles with the user code (pre-Verify sanity check)."""
    res = weave("weavers: [{name: t_build}, {name: t_copy}]\n")
    files = res.runtime_files
    load(SourceSpec(files=list(files)), [("p.sv", SRC), ("p_woven.sv", text_of(res))])


def test_writes_and_skips_unchanged(tmp_path):
    cfg = parse_config("sv-weave:\n  binding: reflib\n  weavers: [{name: t_build}]\n")
    r1 = run(cfg, texts=[("p.sv", SRC)], out_dir=str(tmp_path))
    assert "p_woven.sv" in r1.changed and (tmp_path / "weave-manifest.json").exists()
    r2 = run(cfg, texts=[("p.sv", SRC)], out_dir=str(tmp_path))
    assert r2.changed == []
    assert [l.rsplit("/", 1)[1] for l in (tmp_path / "sv_weave.f").read_text().split()] == [
        "p_woven.sv", "sv_weave_init_pkg.sv", "sv_weave_init_m.sv"]
    # A package that is no longer woven is removed.
    cfg3 = parse_config("sv-weave:\n  binding: reflib\n  packages: {exclude: [p]}\n  weavers: [{name: t_build}]\n")
    run(cfg3, texts=[("p.sv", SRC)], out_dir=str(tmp_path))
    assert not (tmp_path / "p_woven.sv").exists()


def test_identical_profiles_deduplicated():
    res = weave("""
        extension-sets: {core: {}, debug: {}}
        weavers:
        - {name: t_build, set: core}
        - {name: t_build2, set: debug, match: 'named(B)'}
        profiles: {release: [core], debug: [core, debug]}
        """)
    names = {(wc.cls.name, tuple(wc.profiles)): wc.name for wc in res.woven}
    # A: debug adds nothing over release, so one class serves both profiles.
    assert names[("A", ("release", "debug"))] == "Woven_A__release"
    # B: debug differs, so both classes exist.
    assert names[("B", ("release",))] == "Woven_B__release"
    assert names[("B", ("debug",))] == "Woven_B__debug"
    text = text_of(res)
    assert "Woven_A__debug" not in text
    assert 'Woven_A__release__impl i_Woven_A__release = new("debug");' in text
    m = res.manifest["targets"]
    a = [t for t in m if t["class"] == "p::A"][0]
    assert a["woven"]["debug"]["name"] == "Woven_A__release"


def test_weaver_default_order():
    from sv_weave import plugin
    from tests.test_weavers import TBuild

    class Outer(TBuild):
        name = "t_zouter"
        order = -1
    plugin.register_weaver(Outer)
    try:
        res = weave("weavers: [{name: t_build}, {name: t_zouter, options: {tag: Z}}]\n")
    finally:
        plugin.unregister("t_zouter")
    body = block(text_of(res), "function void build", "endfunction")
    assert body[1] == '$display("Z: pre build A");' and body[-2] == '$display("Z: post build A");'


def test_input_hash_follows_weaver_source(tmp_path):
    """An edited weaver changes the input hash even with its version unchanged."""
    from .test_plugin import _weaver_pkg
    d = _weaver_pkg(tmp_path, "fpw_run")
    cfg = parse_config("sv-weave:\n  binding: reflib\n  weavers: [{name: 'fpw_run.weaver:W'}]\n",
                       base_dir=str(tmp_path))
    h1 = run(cfg, texts=[("p.sv", SRC)], write=False).input_hash
    assert run(cfg, texts=[("p.sv", SRC)], write=False).input_hash == h1
    (d / "helper.py").write_text("X = 2\n")
    assert run(cfg, texts=[("p.sv", SRC)], write=False).input_hash != h1


def test_init_false_writes_no_init(tmp_path):
    res = weave("init: false\nweavers: [{name: t_build}]\n")
    assert res.compile_order == ["p_woven.sv"]
    assert not any(n.startswith("sv_weave_init") for n in res.extra_files)
    assert res.manifest["register"] == ["p_woven"]
    res = weave("weavers: [{name: t_build}]\n")
    assert res.compile_order == ["p_woven.sv", "sv_weave_init_pkg.sv", "sv_weave_init_m.sv"]
    assert res.manifest["register"] == ["p_woven"]


def test_generated_init_in_sources_is_error(tmp_path):
    """A Weave over another run's output (init: true on both) would define the init
    package twice."""
    (tmp_path / "p.sv").write_text(SRC)
    first = run(parse_config("sv-weave:\n  binding: reflib\n  weavers: [{name: t_build}]\n"),
                spec=SourceSpec(files=[str(tmp_path / "p.sv")]), out_dir=str(tmp_path / "w1"))
    spec = SourceSpec(files=[str(tmp_path / "p.sv")] + first.woven_files)
    cfg = parse_config("sv-weave:\n  binding: reflib\n")
    with pytest.raises(SvWeaveError, match="already hold a generated init.*init: false"):
        run(cfg, spec=spec, texts=[("q.sv", "package q; endpackage\n")],
            out_dir=str(tmp_path / "w2"))
    cfg = parse_config("sv-weave:\n  binding: reflib\n  init: false\n")
    res = run(cfg, spec=spec, texts=[("q.sv", "package q; endpackage\n")],
              out_dir=str(tmp_path / "w2"))
    assert res.compile_order == []
