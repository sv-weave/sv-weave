// Shared by the P5 sim cases: a 3-level hierarchy across two packages.
package base_pkg;
  import reflib_pkg::*;

  class gp extends ref_object;
    rand int g;
    protected string gs;
    function void set_gs(string s); gs = s; endfunction
    function string get_gs(); return gs; endfunction
  endclass
endpackage
