// debug_seed_repro: with the same seed, release and debug randomise to the same values,
// because the debug code (xcheck) consumes no random numbers.
module tb;
  import reflib_pkg::*;
  import prof_pkg::*;

  sv_weave_init_m u_init();

  initial begin
    pkt p;
    p = ref_factory #(pkt)::create();
    p.srandom(1234);
    for (int i = 0; i < 4; i++) begin
      `CHECK(p.randomize(), "randomize")
      $display("VALUES %0d: %h %h %h", i, p.addr, p.data, p.kind);
    end
    $display("IMPL %s", p.ref_impl_name());
    check_pkg::pass();
    $finish;
  end
endmodule
