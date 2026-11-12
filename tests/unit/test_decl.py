"""SvDecl: class declarations as written (generic members, typedefs, struct members)."""
from .conftest import model_of

SRC = """
package dp;
  typedef struct packed { int unsigned A, B; } prm_t;
  function automatic int unsigned w1(int unsigned w); return w == 0 ? 1 : w; endfunction
  class ty #(prm_t P = '{8, 4});
    typedef struct packed {
      logic [P.A-1:0] id;
      (* fw_opt = "B" *) logic [w1(P.B)-1:0] user, u2;
    } ax_t;
  endclass
  (* fw_api *)
  interface class api_if #(prm_t P = '{8, 4}, type T = int);
    typedef ty #(P)::ax_t ax_t;
    pure virtual task aw(input ax_t t, output int r);
    (* fw_default = "empty" *)
    pure virtual function bit [3:0] f(input ax_t q[$], int x = 3);
  endclass
  class bun #(prm_t P = '{8, 4});
    (* fw_fwd *) ty #(P) a, b;
    local int n;
    function void g(); endfunction
  endclass
  class plain; endclass
endpackage
"""


def test_generic_interface_class():
    m = model_of(SRC, runtime=False)
    d = m.generic("dp::api_if").decl
    assert d.is_interface and d.attrs == {"fw_api": True}
    assert d.header == "#(prm_t P = '{8, 4}, type T = int)"
    assert d.param_names == ["P", "T"] and d.params_ref == "#(P, T)"
    assert [t.name for t in d.typedefs] == ["ax_t"]
    assert d.typedefs[0].type == "ty #(P)::ax_t"
    aw = d.method("aw")
    assert aw.is_task and [(a.dir, a.type, a.name) for a in aw.args] == [
        ("input", "ax_t", "t"), ("output", "int", "r")]
    assert [a.name for a in aw.outputs] == ["r"]
    f = d.method("f")
    assert f.ret == "bit [3:0]" and f.attrs == {"fw_default": "empty"}
    assert f.args[0].dims == "[$]"
    assert (f.args[1].dir, f.args[1].default) == ("input", "3")     # direction inherited
    assert f.prototype("g") == "function bit [3:0] g(input ax_t q [$], input int x = 3)"


def test_struct_members():
    m = model_of(SRC, runtime=False)
    td = m.generic("dp::ty").decl.typedef("ax_t")
    assert td.struct_kind == "struct packed"
    assert [(x.name, x.type, x.attrs) for x in td.members] == [
        ("id", "logic [P.A-1:0]", {}),
        ("user", "logic [w1(P.B)-1:0]", {"fw_opt": "B"}),
        ("u2", "logic [w1(P.B)-1:0]", {"fw_opt": "B"})]


def test_properties_and_plain_class():
    m = model_of(SRC, runtime=False)
    d = m.generic("dp::bun").decl
    assert [(p.name, p.type, p.attrs) for p in d.properties] == [
        ("a", "ty #(P)", {"fw_fwd": True}), ("b", "ty #(P)", {"fw_fwd": True}),
        ("n", "int", {})]
    assert d.properties[2].qualifiers == ["local"]
    assert [x.name for x in d.methods] == ["g"]
    p = m.find_class("dp::plain").decl
    assert p.header == "" and p.param_names == [] and not p.is_interface


def test_comments_are_not_text():
    # A comment before `interface` is leading trivia of that token; it must not
    # stop the class reading as an interface or appear in any text.
    m = model_of("""
package cp;
  // An API.
  interface class c_if #(type T /* payload */ = int);
    pure virtual task put(input T t); // one beat
  endclass
endpackage
""")
    d = m.generic("cp::c_if").decl
    assert d.is_interface
    assert d.header == "#(type T = int)"
    assert d.method("put").text == "pure virtual task put(input T t);"


def test_decl_types_are_public_api():
    import sv_weave.api as api
    from sv_weave.frontend import decl
    for n in ("SvDecl", "SvDeclArg", "SvDeclMember", "SvDeclMethod", "SvDeclProperty",
              "SvDeclTypedef"):
        assert getattr(api, n) is getattr(decl, n)
        assert n in api.__all__
