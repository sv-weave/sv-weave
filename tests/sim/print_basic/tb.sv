// print_basic: sprint() lists the fields; the test checks the log lines.
module tb;
  import reflib_pkg::*;
  import base_pkg::*;
  import mid_pkg::*;

  sv_weave_init_m u_init();

  initial begin
    child a;
    a = ref_factory #(child)::create();
    a.g = 'h2a; a.set_gs("hello"); a.c = GREEN;
    a.deep_h = ref_factory #(leaf)::create();
    a.deep_h.v = 5;
    $display("PRINT-BEGIN\n%sPRINT-END", a.sprint());
    check_pkg::pass();
    $finish;
  end
endmodule
