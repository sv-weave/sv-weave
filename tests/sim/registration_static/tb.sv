// registration_static: registration: static, and the testbench neither instantiates
// sv_weave_init_m nor calls sv_weave_init(). Registration relies on the simulator
// running static initialisers of a class nothing references (design §8.4, D2).
module tb;
  import reflib_pkg::*;
  import a_pkg::*;

  initial begin
    A a;
    a = ref_factory #(A)::create();
    `CHECK_EQ(a.ref_impl_name(), "Woven_A__release", "registered by static initialiser")
    check_pkg::pass();
    $finish;
  end
endmodule
