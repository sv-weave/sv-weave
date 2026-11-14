"""analysis.rw: read/write sets of method bodies as member paths."""
from sv_weave.analysis.rw import analyze, analyze_stmts

from .conftest import model_of

TYPES = """
package t_pkg;
  typedef struct { bit [3:0] a; int b; } s_t;
  typedef struct packed { bit [3:0] a; bit b; } ps_t;
  typedef struct { s_t inner; bit c; } n_t;
endpackage
"""


_KEEP = []     # the pyslang AST lives only as long as its model


def rw(body, decls="", cls="C", meth="m", extra=""):
    m = model_of(TYPES, """
    package p;
      import t_pkg::*;
      %s
      class C;
        %s
        %s
      endclass
    endpackage""" % (extra, decls, body), runtime=False)
    _KEEP.append(m)
    return m.find_class("p::%s" % cls).find_method(meth)


def sets(mth):
    return set(mth.reads), set(mth.writes), set(mth.rw.opaque)


def test_simple_assign():
    r, w, o = sets(rw("function void m(); x = y + 1; endfunction", "int x, y;"))
    assert (r, w, o) == ({"y"}, {"x"}, set())


def test_locals_and_args_ignored():
    r, w, _ = sets(rw("function void m(int a); int l; l = a; x = l; endfunction", "int x;"))
    assert (r, w) == (set(), {"x"})


def test_local_initializer_reads():
    r, w, _ = sets(rw("function void m(); int l = y; x = l; endfunction", "int x, y;"))
    assert (r, w) == ({"y"}, {"x"})


def test_explicit_this():
    r, w, _ = sets(rw("function void m(); this.x = this.y; endfunction", "int x, y;"))
    assert (r, w) == ({"y"}, {"x"})


def test_compound_and_incdec():
    r, w, _ = sets(rw("function void m(); x += y; z++; endfunction", "int x, y, z;"))
    assert r == {"x", "y", "z"} and w == {"x", "z"}


def test_struct_field_access():
    r, w, _ = sets(rw("function void m(); q.a = q.b[3:0]; endfunction", "s_t q;"))
    assert (r, w) == ({"q.b"}, {"q.a"})


def test_whole_struct_read_reads_every_field():
    r, w, _ = sets(rw("function void m(); q2 = q; endfunction", "s_t q, q2;"))
    assert r == {"q.a", "q.b"} and w == {"q2.a", "q2.b"}


def test_nested_struct_expands_recursively():
    r, _, _ = sets(rw("function void m(); n2 = n; endfunction", "n_t n, n2;"))
    assert r == {"n.inner.a", "n.inner.b", "n.c"}
    r, _, _ = sets(rw("function void m(); n2.inner = n.inner; endfunction", "n_t n, n2;"))
    assert r == {"n.inner.a", "n.inner.b"}


def test_packed_struct_expands():
    r, w, _ = sets(rw("function void m(); x = pq; pq.b = 1; endfunction", "ps_t pq; int x;"))
    assert r == {"pq.a", "pq.b"} and w == {"x", "pq.b"}


def test_constant_index():
    r, w, _ = sets(rw("function void m(); arr[1] = arr[2]; endfunction", "int arr[4];"))
    assert (r, w) == ({"arr[2]"}, {"arr[1]"})


def test_variable_index_covers_whole_array():
    r, w, _ = sets(rw("function void m(); arr[i] = 0; x = arr[i+1]; endfunction",
                      "int arr[4]; int i, x;"))
    assert r == {"arr", "i"} and w == {"arr", "x"}


def test_written_on_any_path():
    r, w, _ = sets(rw("""function void m();
        if (c) x = 1; else if (d) y = 2;
        case (e) 0: z = 1; default: ; endcase
      endfunction""", "bit c, d; int e, x, y, z;"))
    assert r == {"c", "d", "e"} and w == {"x", "y", "z"}


def test_loops_and_concat_lvalue():
    r, w, _ = sets(rw("""function void m();
        for (int k = 0; k < 4; k++) arr[k] = y;
        {hi, lo} = v;
      endfunction""", "int arr[4]; int y; bit [3:0] hi, lo; bit [7:0] v;"))
    assert r == {"y", "v"} and w == {"arr", "hi", "lo"}


def test_same_class_call_followed():
    mth = rw("""function void m(); x = f(); g(); endfunction
      function int f(); return y; endfunction
      function void g(); z = 1; endfunction""", "int x, y, z;")
    assert sets(mth) == ({"y"}, {"x", "z"}, set())


def test_transitive_calls_and_recursion():
    mth = rw("""function void m(); a(3); endfunction
      function void a(int n); x = 1; if (n > 0) b(n - 1); endfunction
      function void b(int n); y = x; a(n); endfunction""", "int x, y;")
    r, w, o = sets(mth)
    assert r == {"x"} and w == {"x", "y"} and o == set()


def test_static_function_and_static_property():
    mth = rw("function void m(); x = S::sf(y); cnt++; endfunction",
             "int x, y; static int cnt;",
             extra="class S; static int k; static function int sf(int v); k = v; return v; endfunction endclass")
    r, w, _ = sets(mth)
    assert r == {"y", "p::C::cnt"} and w == {"x", "p::C::cnt", "p::S::k"}


def test_ref_and_output_args():
    mth = rw("""function void m(); o(x, y, z); endfunction
      function automatic void o(input int a, output int b, ref int c); endfunction""",
             "int x, y, z;")
    r, w, _ = sets(mth)
    assert r == {"x", "z"} and w == {"y", "z"}


def test_member_handle_call_prefixed():
    mth = rw("function void m(); x = sub.get(); sub.put(x); endfunction",
             "D sub; int x;",
             extra="""class D; int v; int w;
               function int get(); return v; endfunction
               function void put(int a); w = a; endfunction endclass""")
    assert sets(mth) == ({"x", "sub.v"}, {"x", "sub.w"}, set())


def test_method_port_call_is_opaque():
    mth = rw("function void m(); x = port.t.get(); endfunction",
             "P port; int x;",
             extra="""interface class I; pure virtual function int get(); endclass
               class P; I t; endclass""")
    r, w, o = sets(mth)
    assert w == {"x"} and o == {"port.t.get"}


def test_pure_virtual_self_call_is_opaque():
    mth = rw("", "", cls="V",
             extra="""virtual class V; int x;
               pure virtual function int f();
               function void m(); x = f(); endfunction endclass""")
    assert sets(mth) == (set(), {"x"}, {"f"})


def test_parameterized_class_specialization():
    m = model_of(TYPES, """
    package p;
      import t_pkg::*;
      class G #(type T = bit);
        T d; T o;
        function void m(); o = d; endfunction
      endclass
      class U; G #(t_pkg::s_t) g; G #(int) gi; endclass
    endpackage""", runtime=False)
    found = {str(sorted(c.find_method("m").reads)) for c in m.generic("p::G").specializations}
    assert found == {"['d.a', 'd.b']", "['d']"}


def test_constant_parameter_if_is_superset():
    m = model_of("""
    package p;
      class K #(int MODE = 0);
        int a, b, x;
        function void m(); if (MODE == 1) x = a; else x = b; endfunction
      endclass
      class U; K #(1) k; endclass
    endpackage""", runtime=False)
    (k,) = m.generic("p::K").specializations
    mth = k.find_method("m")
    assert set(mth.reads) == {"a", "b"} and set(mth.writes) == {"x"}


def test_function_returning_struct():
    mth = rw("""function void m(); x = mk().b; q = mk(); endfunction
      function s_t mk(); s_t s; s.a = y; s.b = 0; return s; endfunction""",
             "s_t q; int x; bit [3:0] y;")
    r, w, _ = sets(mth)
    assert r == {"y"} and w == {"x", "q.a", "q.b"}


def test_cached():
    mth = rw("function void m(); x = y; endfunction", "int x, y;")
    assert mth.rw is mth.rw


def test_analyze_on_symbol():
    mth = rw("function void m(); x = y; endfunction", "int x, y;")
    assert analyze(mth.slang).writes == {"x"}


def test_summary_hook():
    """A summary stands for the callee (prefixed by the receiver); None follows it."""
    from sv_weave.analysis.rw import RwSets
    mth = rw("function void m(); h.get(); h.put(); endfunction", "H h;",
             extra="""class H; int v, w;
                 function int get(); return v; endfunction
                 function void put(); w = 1; endfunction
               endclass""")
    stub = RwSets(frozenset({"@f"}), frozenset(), frozenset())
    res = analyze(mth.slang, lambda c: stub if c.name == "get" else None)
    assert (set(res.reads), set(res.writes), set(res.opaque)) == ({"h.@f"}, {"h.w"}, set())


def _stmts(body, decls):
    r = analyze_stmts(rw(body, decls).slang)
    return None if r is None else [(set(s.reads), set(s.writes)) for s in r]


def test_stmts_per_statement():
    got = _stmts("function void m(); x = y; begin z = w; if (c) z = y; end endfunction",
                 "int x, y, z, w; bit c;")
    assert got == [({"y"}, {"x"}), ({"w"}, {"z"}), ({"c", "y"}, {"z"})]


def test_stmts_local_gives_none():
    assert _stmts("function void m(); int l; l = y; x = l; endfunction", "int x, y;") is None


def test_stmt_rw_property():
    mth = rw("function void m(); x = y; z = w; endfunction", "int x, y, z, w;")
    assert [set(s.writes) for s in mth.stmt_rw] == [{"x"}, {"z"}]
    assert mth.stmt_rw is mth.stmt_rw
    assert rw("function void m(); int l; x = l; endfunction", "int x;").stmt_rw is None
