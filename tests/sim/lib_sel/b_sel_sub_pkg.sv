package sel_sub_pkg;
  import reflib_pkg::*;
  import sel_base_pkg::*;

  class rd_pkt extends pkt;
    virtual function string kind(); return "rd"; endfunction
  endclass

  (* weave_weight = 3 *)
  class wr_pkt extends pkt;
    virtual function string kind(); return "wr"; endfunction
  endclass

  // Abstract: never selected.
  virtual class ctrl_pkt extends pkt;
  endclass

  class nop_pkt extends ctrl_pkt;
    virtual function string kind(); return "nop"; endfunction
  endclass

  // Weight 0: listed, never picked at random.
  (* weave_weight = 0 *)
  class never_pkt extends pkt;
    virtual function string kind(); return "never"; endfunction
  endclass

  // A user override target for rd_pkt.
  class my_rd_pkt extends rd_pkt;
    virtual function string kind(); return "my_rd"; endfunction
  endclass

  class ppkt #(int W = 8) extends pkt;
    virtual function string kind(); return $sformatf("p%0d", W); endfunction
  endclass

  class uses_ppkt;
    ppkt#(16) p16;
    ppkt#(32) p32;
  endclass
endpackage
