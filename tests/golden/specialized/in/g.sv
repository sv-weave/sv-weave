package g_pkg;
  import reflib_pkg::*;

  class G #(int W = 4) extends ref_object;
    bit [W-1:0] v;
  endclass

  class user;
    G#(8)  g8;
    G#(16) g16;
  endclass
endpackage
