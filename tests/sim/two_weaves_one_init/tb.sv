// two_weaves_one_init: a_pkg and c_pkg woven by two Weave tasks (init false); one
// svweave.Init registers both.
module tb;
  import reflib_pkg::*;
  import a_pkg::*;
  import c_pkg::*;

  sv_weave_init_m u_init();

  initial begin
    A a;
    C c;
    a = ref_factory #(A)::create("tb.a");
    c = ref_factory #(C)::create("tb.c");
    `CHECK(a != null && c != null, "create returned null")
    `CHECK_EQ(a.ref_impl_name(), "Woven_A__release", "a_pkg woven implementation")
    `CHECK_EQ(c.ref_impl_name(), "Woven_C__release", "c_pkg woven implementation")
    check_pkg::pass();
    $finish;
  end
endmodule
