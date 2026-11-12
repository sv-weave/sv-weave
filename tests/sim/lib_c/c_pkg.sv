package c_pkg;
  import reflib_pkg::*;

  class C extends ref_object;
    int built;
    virtual function void build();
      built++;
    endfunction
  endclass
endpackage
