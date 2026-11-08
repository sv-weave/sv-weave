// factory_basic: ref_factory#(A)::create() returns the woven class, and the woven
// override runs around the user's build().
module tb;
  import reflib_pkg::*;
  import a_pkg::*;

  sv_weave_init_m u_init();

  initial begin
    A a;
    a = ref_factory #(A)::create("tb.a");
    `CHECK(a != null, "create returned null")
    `CHECK_EQ(a.ref_impl_name(), "Woven_A__release", "woven implementation")
    a.build();
    `CHECK_EQ(a.built, 1, "user build() ran once through the woven override")
    check_pkg::pass();
    $finish;
  end
endmodule
