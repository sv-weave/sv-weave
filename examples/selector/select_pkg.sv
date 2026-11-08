// select_pkg: runtime for the selector example (examples/selector/).
//
// Not part of sv-weave: an example of the runtime side of a design-wide weaver. The
// selector weaver registers one select_entry#(T) per concrete subclass of a base T,
// so code can count, list and randomly create those subclasses without naming them.
// Creation goes through each subclass's factory, so overrides and woven
// implementations apply. Compile after reflib_pkg and before the woven packages.
`ifndef SELECT_PKG_SV
`define SELECT_PKG_SV

package select_pkg;

  virtual class select_entry #(type T = int);
    pure virtual function string type_name();
    pure virtual function int unsigned weight();
    /* verilator lint_off UNUSEDSIGNAL */
    pure virtual function T create(string inst_path);
    /* verilator lint_on UNUSEDSIGNAL */
  endclass

  typedef string select_string_q[$];

  class select_types #(type T = int);
    static select_entry #(T) m_entries[$];

    static function void add(select_entry #(T) e);
      m_entries.push_back(e);
    endfunction

    static function int count();
      return m_entries.size();
    endfunction

    // Type names, in registration order (index order for create()).
    static function select_string_q all();
      select_string_q names;
      foreach (m_entries[i]) names.push_back(m_entries[i].type_name());
      return names;
    endfunction

    static function int unsigned weight(int idx);
      if (idx < 0 || idx >= m_entries.size()) return 0;
      return m_entries[idx].weight();
    endfunction

    // Creates subclass number idx (see all()), or null if idx is out of range.
    static function T create(int idx, string inst_path = "");
      if (idx < 0 || idx >= m_entries.size()) return null;
      return m_entries[idx].create(inst_path);
    endfunction

    // An index chosen at random, weighted by each entry's weight; -1 if every weight
    // is 0 or nothing is registered.
    static function int pick();
      int unsigned total = 0;
      int unsigned r;
      foreach (m_entries[i]) total += m_entries[i].weight();
      if (total == 0) return -1;
      r = $urandom_range(total - 1);
      foreach (m_entries[i]) begin
        if (r < m_entries[i].weight()) return i;
        r -= m_entries[i].weight();
      end
      return -1;
    endfunction

    // A randomly chosen subclass (weighted), created through its factory.
    static function T create_random(string inst_path = "");
      int idx = pick();
      if (idx < 0) return null;
      return m_entries[idx].create(inst_path);
    endfunction
  endclass

endpackage

`endif
