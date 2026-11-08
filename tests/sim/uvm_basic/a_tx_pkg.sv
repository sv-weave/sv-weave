`include "uvm_macros.svh"
package tx_pkg;
  import uvm_pkg::*;

  // A plain UVM transaction: no field macros, no hand-written do_copy/do_compare.
  class tx extends uvm_sequence_item;
    `uvm_object_utils(tx)
    rand bit [7:0]  addr;
    rand bit [31:0] data;
    byte            payload[$];
    function new(string name = "tx");
      super.new(name);
    endfunction
  endclass

  class my_tx extends tx;
    `uvm_object_utils(my_tx)
    int extra;
    function new(string name = "my_tx");
      super.new(name);
    endfunction
  endclass
endpackage

// A different class registered under the same UVM type name, "tx", in a package that
// is not woven. (Two classes both named tx in different packages would be the usual
// way to get this, but Verilator 5.054 cannot build that.)
package alt_pkg;
  import uvm_pkg::*;
  class alt_tx extends uvm_sequence_item;
    typedef uvm_object_registry #(alt_tx, "tx") type_id;
    static function type_id get_type();
      return type_id::get();
    endfunction
    virtual function uvm_object_wrapper get_object_type();
      return type_id::get();
    endfunction
    virtual function string get_type_name();
      return "alt_tx";
    endfunction
    function new(string name = "alt_tx");
      super.new(name);
    endfunction
  endclass
endpackage
