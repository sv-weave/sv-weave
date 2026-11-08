package mid_pkg;
  import reflib_pkg::*;
  import base_pkg::*;

  typedef enum bit [1:0] { RED, GREEN, BLUE } color_e;

  class leaf extends ref_object;
    int v;
  endclass

  class parent extends gp;
    int p;
    byte pq[$];
  endclass

  class child extends parent;
    color_e c;
    leaf shallow_h;
    (* weave_deep *) leaf deep_h;
    int fixed_a[3];
    int dyn_a[];
    string aa[int];
    (* weave_deep *) leaf deep_q[$];
    (* weave_deep *) leaf deep_aa[string];
    leaf shallow_q[$];
  endclass

  class G #(int W = 4) extends ref_object;
    bit [W-1:0] v;
    function int width(); return W; endfunction
  endclass

  // Names the specialisations, so that they are woven.
  class uses_g;
    G#(8)  g8;
    G#(16) g16;
  endclass
endpackage
