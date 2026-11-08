// selector_param: specialisations of a parameterised subclass are selectable.
module tb;
  import reflib_pkg::*;
  import select_pkg::*;
  import sel_base_pkg::*;

  sv_weave_init_m u_init();

  initial begin
    pkt p;
    select_string_q names;
    int found = 0;
    names = select_types #(pkt)::all();
    foreach (names[i]) begin
      if (names[i] == "sel_sub_pkg::ppkt#(16)" || names[i] == "sel_sub_pkg::ppkt#(32)") begin
        p = select_types #(pkt)::create(i);
        $display("PARAM %s %s", names[i], p.kind());
        found++;
      end
    end
    `CHECK_EQ(found, 2, "both specialisations selectable")
    check_pkg::pass();
    $finish;
  end
endmodule
