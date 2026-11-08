import pytest

from sv_weave import plugin
from sv_weave.diag import SvWeaveError


@pytest.mark.parametrize("spec,ok", [
    (">=0.1,<0.2", True),
    (">=0.1", True),
    ("==0.1", True),
    ("==0.1.0", True),
    (">0.1", False),
    (">=0.2", False),
    ("<0.1", False),
    (">=0,<1", True),
])
def test_api_ranges(spec, ok):
    assert plugin.api_compatible(spec, (0, 1)) is ok


def test_bad_range():
    with pytest.raises(ValueError):
        plugin.api_compatible("~0.1")


def test_incompatible_weaver_refused():
    class Future(plugin.Weaver):
        name = "t_future"
        api = ">=1.0"
    plugin.register_weaver(Future)
    try:
        with pytest.raises(SvWeaveError, match="needs sv-weave API >=1.0, but this sv-weave provides 0.1"):
            plugin.find(plugin.WEAVER_GROUP, "t_future")
    finally:
        plugin.unregister("t_future")


def test_unknown_weaver():
    with pytest.raises(SvWeaveError, match="unknown weaver 'nope'"):
        plugin.find(plugin.WEAVER_GROUP, "nope")


def test_no_builtin_binding():
    from sv_weave.bindings import BUILTIN
    assert BUILTIN == []


def test_reflib_binding(reflib_binding):
    b = plugin.find(plugin.BINDING_GROUP, "reflib")()
    assert b.roots == ("reflib_pkg::ref_object",)
    assert set(b.features()) >= {"copy", "compare", "print"}


def test_not_a_subclass():
    class NotAWeaver:
        name = "t_bad"
    plugin._local[plugin.WEAVER_GROUP]["t_bad"] = NotAWeaver
    try:
        with pytest.raises(SvWeaveError, match="not a Weaver subclass"):
            plugin.find(plugin.WEAVER_GROUP, "t_bad")
    finally:
        plugin.unregister("t_bad")


def test_module_reference(tmp_path):
    (tmp_path / "my_weavers_mod.py").write_text(
        "from sv_weave import plugin\n"
        "class W(plugin.Weaver):\n"
        "    name = 'w'\n"
        "    def subscribe(self, bus): pass\n"
        "class NotOne: pass\n")
    w = plugin.find(plugin.WEAVER_GROUP, "my_weavers_mod:W", [str(tmp_path)])
    assert w.name == "w"
    with pytest.raises(SvWeaveError, match="not a Weaver subclass"):
        plugin.find(plugin.WEAVER_GROUP, "my_weavers_mod:NotOne", [str(tmp_path)])
    with pytest.raises(SvWeaveError, match="cannot load weaver 'no_such_mod:W'"):
        plugin.find(plugin.WEAVER_GROUP, "no_such_mod:W")
