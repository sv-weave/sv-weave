// Shared by the P7 selector sim cases. The base and the subclasses are in different
// packages, so the selector's code has to import the subclasses' package.
package sel_base_pkg;
  import reflib_pkg::*;

  (* weave_select *)
  virtual class pkt extends ref_object;
    pure virtual function string kind();
  endclass
endpackage
