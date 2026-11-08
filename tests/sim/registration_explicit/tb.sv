// registration_explicit: no sv_weave_init_m; the testbench calls sv_weave_init()
// itself before the first create.
module tb;
  import reflib_pkg::*;
  import a_pkg::*;

  initial begin
    A a;
    sv_weave_init_pkg::sv_weave_init();
    a = ref_factory #(A)::create();
    `CHECK_EQ(a.ref_impl_name(), "Woven_A__release", "registered by explicit call")
    check_pkg::pass();
    $finish;
  end
endmodule
