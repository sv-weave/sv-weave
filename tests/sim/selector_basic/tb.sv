// selector_basic: over 1000 draws, every concrete subclass with a weight appears, and
// abstract or zero-weight ones never do.
module tb;
  import reflib_pkg::*;
  import select_pkg::*;
  import sel_base_pkg::*;

  sv_weave_init_m u_init();

  initial begin
    pkt p;
    int seen[string];
    select_string_q names;
    names = select_types #(pkt)::all();
    $display("SELECTABLE %p", names);
    `CHECK_EQ(select_types #(pkt)::count(), 7, "count")
    for (int i = 0; i < 1000; i++) begin
      p = select_types #(pkt)::create_random("tb.gen");
      `CHECK(p != null, "create_random returned null")
      seen[p.kind()]++;
    end
    foreach (seen[k]) $display("SEEN %s %0d", k, seen[k]);
    `CHECK(seen.exists("rd") && seen.exists("wr") && seen.exists("nop"), "all concrete kinds")
    `CHECK(!seen.exists("never"), "weight 0 never picked")
    // create(idx) reaches every entry, including weight 0.
    foreach (names[i]) begin
      p = select_types #(pkt)::create(i);
      `CHECK(p != null, "create(idx)")
    end
    check_pkg::pass();
    $finish;
  end
endmodule
