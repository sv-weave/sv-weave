package f_pkg;
  import reflib_pkg::*;

  typedef enum bit [1:0] { RED, GREEN, BLUE } color_e;
  typedef struct packed { bit [3:0] hi; bit [3:0] lo; } nib_t;
  typedef struct { int a; string b; } rec_t;

  class leaf extends ref_object;
    int v;
  endclass

  class all_fields extends ref_object;
    int          i;
    logic [7:0]  l8;
    color_e      color;
    string       s;
    real         r;
    chandle      ch;
    event        ev;
    nib_t        nib;
    rec_t        rec;
    leaf         shallow_h;
    (* weave_deep *) leaf deep_h;
    int          fixed_a[4];
    int          fixed_2d[2][3];
    byte         dyn_a[];
    int          q[$];
    string       aa[int];
    (* weave_deep *) leaf deep_q[$];
    (* weave_deep *) leaf deep_d[];
    (* weave_deep *) leaf deep_aa[string];
    (* weave_deep *) leaf deep_f[2];
    static int   st;
    const int    k = 1;
    (* weave_nocopy, weave_nocompare, weave_noprint *) int skipped;
    local int    hidden;
  endclass
endpackage
