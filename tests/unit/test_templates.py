"""Jinja templates for weaver text: render(), SvText, the origin of rendered text."""
import os
import sys
import textwrap

import pytest

from sv_weave import plugin
from sv_weave.config import parse_config
from sv_weave.diag import SvWeaveError
from sv_weave.match import has_method
from sv_weave.run import run
from sv_weave.weave import templates
from sv_weave.weave.templates import SvText, render, template_dirs

pytest.importorskip("jinja2")

HERE = os.path.abspath(__file__)

SRC = """
package pa;
  import reflib_pkg::*;
  class A extends ref_object;
    virtual function void build(); endfunction
  endclass
endpackage
"""


def _write(d, name, text):
    p = os.path.join(str(d), name)
    with open(p, "w") as fp:
        fp.write(textwrap.dedent(text).lstrip("\n"))
    return p


def weave(name, src=SRC):
    cfg = parse_config("sv-weave:\n  binding: reflib\n  weavers: [{name: %s}]\n" % name)
    return run(cfg, texts=[("p.sv", src)], write=False)


@pytest.fixture
def tdir(tmp_path):
    templates._ENVS.clear()
    yield tmp_path
    templates._ENVS.clear()


@pytest.fixture
def design_weaver(tdir):
    class TTpl(plugin.Weaver):
        name = "t_tpl"
        templates = str(tdir)
        fn = None

        def subscribe(self, bus):
            bus.on_design(lambda d: type(self).fn(d))

    def make(fn):
        TTpl.fn = staticmethod(fn)
        plugin.register_weaver(TTpl)
        return TTpl
    yield make
    plugin.unregister("t_tpl")


# -- render ------------------------------------------------------------------------------
def test_render_environment(tdir):
    _write(tdir, "e.sv.j2", """
        // {{ what }} <a & b>
        class {{ name }};
        {% for f in fields %}
            int {{ f }};
        {% endfor %}
        endclass
        """)
    t = render("e.sv.j2", [str(tdir)], what="x", name="c", fields=["a", "b"])
    # trim_blocks + lstrip_blocks: block tags leave no lines; no autoescape;
    # keep_trailing_newline.
    assert t == "// x <a & b>\nclass c;\n    int a;\n    int b;\nendclass\n"
    assert isinstance(t, SvText) and isinstance(t, str)
    assert t.template == os.path.join(str(tdir), "e.sv.j2")
    assert t.py_file == HERE and t.py_line > 0
    assert type(t + "x") is str                     # derived text is plain


def test_render_undefined_names_template_line(tdir):
    _write(tdir, "u.sv.j2", """
        class c;
            int {{ x.missing }};
        endclass
        """)
    with pytest.raises(SvWeaveError) as e:
        render("u.sv.j2", [str(tdir)], x=object())
    d = e.value.diags[0]
    assert "missing" in d.msg and "u.sv.j2" in d.msg
    assert d.loc.file.endswith("u.sv.j2") and d.loc.line == 2


def test_render_syntax_error_and_missing_template(tdir):
    _write(tdir, "s.sv.j2", "{% for x in y %}\n")
    with pytest.raises(SvWeaveError) as e:
        render("s.sv.j2", [str(tdir)], y=[])
    assert e.value.diags[0].loc.file.endswith("s.sv.j2")
    with pytest.raises(SvWeaveError, match="template 'nope.j2' not found"):
        render("nope.j2", [str(tdir)])


def test_render_without_jinja(tdir, monkeypatch):
    monkeypatch.setitem(sys.modules, "jinja2", None)
    with pytest.raises(SvWeaveError, match=r"sv-weave\[templates\]"):
        render("e.sv.j2", [str(tdir)])


def test_template_dirs_default_and_attribute(tdir):
    class W(plugin.Weaver):
        name = "t_dirs"
    assert template_dirs(W()) == (os.path.join(os.path.dirname(HERE), "templates"),)
    W.templates = ["a", str(tdir)]
    assert template_dirs(W()) == (os.path.join(os.path.dirname(HERE), "a"), str(tdir))


def test_fingerprint_follows_templates(tmp_path):
    pkg = tmp_path / "tplpkg"
    (pkg / "templates").mkdir(parents=True)
    (pkg / "__init__.py").write_text("")
    (pkg / "templates" / "a.sv.j2").write_text("one\n")
    before = plugin._hash_paths([str(pkg)])
    (pkg / "templates" / "a.sv.j2").write_text("two\n")
    assert plugin._hash_paths([str(pkg)]) != before


# -- origin of rendered text -----------------------------------------------------------------
def test_add_item_origin_is_template(design_weaver, tdir):
    _write(tdir, "item.sv.j2", """
        // from a template
        typedef int {{ name }};
        """)

    def fn(d):
        d.add_item("pa", d.render("item.sv.j2", name="__w_t"))
        d.add_item("pa", "typedef int __w_plain;")
    design_weaver(fn)
    rf = weave("t_tpl").file("pa_woven.sv")
    lines = rf.text.splitlines()
    n = next(i for i, l in enumerate(lines, 1) if "__w_t;" in l)
    o = rf.origin_at(n)
    assert o.contributor == "t_tpl"
    assert (o.file, o.line) == (os.path.join(str(tdir), "item.sv.j2"), 1)
    assert o.py_file == HERE and o.py_line > 0
    assert "rendered at %s:" % HERE in str(o)
    plain = rf.origin_at(next(i for i, l in enumerate(lines, 1) if "__w_plain" in l))
    assert plain.file == HERE and plain.py_file == ""


def test_add_file_error_names_template(design_weaver, tdir):
    _write(tdir, "bad.sv.j2", """
        module {{ name }};
          __w_no_such_t x;
        endmodule
        """)

    def fn(d):
        d.add_file("w_bad.sv", d.render("bad.sv.j2", name="__w_bad"))
    design_weaver(fn)
    with pytest.raises(SvWeaveError) as e:
        weave("t_tpl")
    d = next(x for x in e.value.diags if "w_bad.sv" in x.msg)
    assert d.loc.file.endswith("bad.sv.j2")
    assert "rendered at" in d.msg


def test_class_item_and_field_from_template(tdir):
    _write(tdir, "ci.sv.j2", "typedef int {{ n }};\n")
    _write(tdir, "fd.sv.j2", "int {{ n }}")
    _write(tdir, "st.sv.j2", "$display(\"{{ n }}\");\n")

    class TCls(plugin.Weaver):
        name = "t_tpl_cls"
        templates = str(tdir)

        def subscribe(self, bus):
            bus.on(has_method("build"), self.weave)

        def weave(self, w):
            w.add_item(w.render("ci.sv.j2", n="__w_ci_t"))
            w.add_field(w.render("fd.sv.j2", n="__w_fd"))
            w.override("build").body.add(w.render("st.sv.j2", n="__w_body_t"))

    plugin.register_weaver(TCls)
    try:
        res = weave("t_tpl_cls")
    finally:
        plugin.unregister("t_tpl_cls")
    rf = res.file("pa_woven.sv")
    lines = rf.text.splitlines()
    for marker, tpl in (("__w_ci_t", "ci.sv.j2"), ("__w_fd", "fd.sv.j2"),
                        ("__w_body_t", "st.sv.j2")):
        n = next(i for i, l in enumerate(lines, 1) if marker in l)
        o = rf.origin_at(n)
        assert o.file.endswith(tpl) and o.line == 1 and o.py_file == HERE, (marker, o)
