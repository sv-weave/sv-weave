package reg_pkg;
  int n_registered;
  function automatic bit register_me();
    n_registered++;
    return 1;
  endfunction
endpackage

// Nothing references this package or its class.
package unref_pkg;
  function automatic bit do_reg();
    return reg_pkg::register_me();
  endfunction
  class holder;
    static bit m_done = do_reg();
  endclass
endpackage

module init_m;
  bit m_installed = reg_pkg::register_me();
endmodule

module tb;
  init_m u_init();
  initial begin
    // Expect 2: one from the module's static initialiser, one from the unreferenced class.
    $display("n_registered=%0d", reg_pkg::n_registered);
    $finish;
  end
endmodule
