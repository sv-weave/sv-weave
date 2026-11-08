// profile_compiletime: only release is built, so asking for debug falls back to it.
module tb;
  import reflib_pkg::*;
  import prof_pkg::*;

  sv_weave_init_m u_init();

  initial begin
    pkt p;
    p = ref_factory #(pkt)::create();
    `CHECK_EQ(p.ref_impl_name(), "Woven_pkt__release", "falls back to the built profile")
    check_pkg::pass();
    $finish;
  end
endmodule
