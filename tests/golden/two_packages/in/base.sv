package base_pkg;
  import reflib_pkg::*;

  class item extends ref_object;
    rand bit [7:0] addr;
    protected int id;
    function new(int id = 0);
      this.id = id;
    endfunction
  endclass
endpackage
