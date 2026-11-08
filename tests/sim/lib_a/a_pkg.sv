package a_pkg;
  import reflib_pkg::*;

  class A extends ref_object;
    int built;
    virtual function void build();
      built++;
    endfunction
  endclass

  // No build(): t_build does not match, so B is not woven.
  class B extends ref_object;
    int b;
  endclass

  class MyA extends A;
    virtual function void build();
      super.build();
      built += 10;
    endfunction
  endclass
endpackage
