package a_pkg;
  import reflib_pkg::*;

  class A extends ref_object;
    int x;
    virtual function void build();
      x = 1;
    endfunction
  endclass
endpackage
