// factory_unwoven_fallback: B gets no woven class (nothing matches it), so the
// factory falls back to B::new().
module tb;
  import reflib_pkg::*;
  import a_pkg::*;

  sv_weave_init_m u_init();

  initial begin
    B b;
    A a;
    b = ref_factory #(B)::create();
    `CHECK(b != null, "create returned null")
    `CHECK_EQ(b.ref_impl_name(), "", "B is not woven")
    a = ref_factory #(A)::create();
    `CHECK_EQ(a.ref_impl_name(), "Woven_A__release", "A is woven")
    check_pkg::pass();
    $finish;
  end
endmodule
