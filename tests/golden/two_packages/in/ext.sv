package ext_pkg;
  import base_pkg::*;

  typedef enum bit [1:0] { RD, WR } kind_e;

  class ext_item extends item;
    kind_e kind;
    byte data[$];
    (* weave_nocopy *) int scratch;
    function new(int id = 7);
      super.new(id);
    endfunction
  endclass
endpackage
