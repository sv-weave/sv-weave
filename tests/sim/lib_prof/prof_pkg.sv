// Shared by the P6 sim cases.
package prof_pkg;
  import reflib_pkg::*;

  // Four-state fields: xcheck applies, so release and debug differ.
  class pkt extends ref_object;
    rand logic [7:0]  addr;
    rand bit   [15:0] data;
    rand logic [3:0]  kind;
    constraint c_kind { kind inside {[1:9]}; }
  endclass

  class other extends ref_object;
    rand logic [7:0] v;
  endclass

  // Two-state only: xcheck does not apply, so one woven class serves both profiles.
  class same extends ref_object;
    int n;
  endclass
endpackage
