// selector_respects_override: a factory override on rd_pkt applies to what the
// selector creates, and the result is the woven override class.
module tb;
  import reflib_pkg::*;
  import select_pkg::*;
  import sel_base_pkg::*;
  import sel_sub_pkg::*;

  sv_weave_init_m u_init();

  initial begin
    pkt p;
    select_string_q names;
    int rd_idx = -1;
    ref_factory #(rd_pkt)::set_override(ref_override_to #(rd_pkt, my_rd_pkt)::get());
    names = select_types #(pkt)::all();
    foreach (names[i]) if (names[i] == "sel_sub_pkg::rd_pkt") rd_idx = i;
    `CHECK(rd_idx >= 0, "rd_pkt is selectable")
    p = select_types #(pkt)::create(rd_idx, "tb.x");
    `CHECK_EQ(p.kind(), "my_rd", "override applied")
    `CHECK_EQ(p.ref_impl_name(), "Woven_my_rd_pkt__release", "woven override class")
    check_pkg::pass();
    $finish;
  end
endmodule
