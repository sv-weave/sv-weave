// override_forwarding: a user override A -> MyA through the plain factory gives the
// woven MyA, not the woven A (factory override first, then weaving).
module tb;
  import reflib_pkg::*;
  import a_pkg::*;

  sv_weave_init_m u_init();

  initial begin
    A a;
    ref_factory #(A)::set_override(ref_override_to #(A, MyA)::get());
    a = ref_factory #(A)::create("tb.a");
    `CHECK_EQ(a.ref_impl_name(), "Woven_MyA__release", "override resolved before weaving")
    a.build();
    `CHECK_EQ(a.built, 11, "MyA::build ran through the woven override")
    check_pkg::pass();
    $finish;
  end
endmodule
