// selector_weights: wr_pkt has weight 3 and rd_pkt weight 1, so wr is drawn about
// three times as often; never_pkt (weight 0) never.
module tb;
  import reflib_pkg::*;
  import select_pkg::*;
  import sel_base_pkg::*;

  sv_weave_init_m u_init();

  initial begin
    pkt p;
    int seen[string];
    for (int i = 0; i < 4000; i++) begin
      p = select_types #(pkt)::create_random();
      seen[p.kind()]++;
    end
    foreach (seen[k]) $display("SEEN %s %0d", k, seen[k]);
    `CHECK(!seen.exists("never"), "weight 0 never picked")
    `CHECK(seen["wr"] > 2 * seen["rd"], "weight 3 drawn more than twice as often as weight 1")
    `CHECK(seen["wr"] < 4 * seen["rd"], "weight 3 drawn less than four times as often")
    check_pkg::pass();
    $finish;
  end
endmodule
