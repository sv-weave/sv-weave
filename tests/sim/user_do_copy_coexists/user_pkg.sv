package user_pkg;
  import reflib_pkg::*;

  class with_copy extends ref_object;
    (* weave_nocopy *) int n_user_copies;   // bookkeeping, not data: not copied
    local int secret;      // the woven code cannot reach it; the user's copy does
    int visible;
    function void set_secret(int s); secret = s; endfunction
    function int get_secret(); return secret; endfunction
    virtual function void copy(ref_object rhs);
      with_copy r;
      super.copy(rhs);
      void'($cast(r, rhs));
      secret = r.secret;
      n_user_copies++;
    endfunction
  endclass

  class sub_copy extends with_copy;
    int extra;
  endclass
endpackage
