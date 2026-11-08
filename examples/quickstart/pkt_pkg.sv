package pkt_pkg;
  import reflib_pkg::*;

  class packet extends ref_object;
    rand bit [7:0]  addr;
    rand bit [31:0] data;
    int             id;
  endclass
endpackage
