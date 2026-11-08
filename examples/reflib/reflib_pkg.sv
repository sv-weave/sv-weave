// reflib_pkg: a minimal reference class library, used by sv-weave's examples and tests.
//
// NOT part of sv-weave. It shows what a library needs for sv-weave to work with it: a
// base class (ref_object) whose virtual methods are the hooks woven subclasses
// implement, and a factory (ref_factory) that decides which class gets created. Its
// binding is reflib_binding.py in this directory. This factory also chooses among
// woven classes by profile (+weave_profile, +weave_impl), the way a real library
// binding would do it through its own factory (for UVM: uvm_factory overrides).
`ifndef REFLIB_PKG_SV
`define REFLIB_PKG_SV

package reflib_pkg;

  typedef class ref_profiles;

  // ---------------------------------------------------------------------------
  // Glob match: '*' matches any run of characters, '?' any one character.
  // ---------------------------------------------------------------------------
  function automatic bit ref_glob(string pat, string s);
    int p = 0;
    int i = 0;
    int star = -1;
    int mark = 0;
    while (i < s.len()) begin
      if (p < pat.len() && (pat[p] == "?" || pat[p] == s[i])) begin
        p++;
        i++;
      end else if (p < pat.len() && pat[p] == "*") begin
        star = p;
        mark = i;
        p++;
      end else if (star != -1) begin
        p = star + 1;
        mark++;
        i = mark;
      end else begin
        return 0;
      end
    end
    while (p < pat.len() && pat[p] == "*") p++;
    return p == pat.len();
  endfunction

  // Number of literal (non-wildcard) characters: how specific a glob is.
  function automatic int ref_glob_weight(string pat);
    int n = 0;
    for (int i = 0; i < pat.len(); i++) begin
      if (pat[i] != "*" && pat[i] != "?") n++;
    end
    return n;
  endfunction

  // ---------------------------------------------------------------------------
  // Implementations
  // ---------------------------------------------------------------------------

  // One woven implementation of a user type. Generated per woven class.
  virtual class ref_creator;
    pure virtual function string impl_name();   // "Woven_A__debug"
    pure virtual function string profile();     // "debug"
    pure virtual function string type_name();   // "foo_pkg::A"
  endclass

  // Statically typed creator: the hot path, no string keys.
  virtual class ref_impl #(type T = int) extends ref_creator;
    pure virtual function T create();
  endclass

  // String-keyed view of every registration, for adapters that only know type names
  // and for reporting.
  class ref_registry;
    static local ref_registry m_inst;
    local ref_creator m_map[string][string];   // type name -> profile -> creator

    static function ref_registry inst();
      if (m_inst == null) m_inst = new();
      return m_inst;
    endfunction

    function void add_type(string type_name, ref_creator c);
      m_map[type_name][c.profile()] = c;
    endfunction

    function bit has_type(string type_name);
      return m_map.exists(type_name);
    endfunction

    // The creator for the active profile of (type_name, inst_path), or null.
    function ref_creator lookup(string type_name, string inst_path = "");
      string p;
      if (!m_map.exists(type_name)) return null;
      p = ref_profiles::active(type_name, inst_path);
      if (m_map[type_name].exists(p)) return m_map[type_name][p];
      p = ref_profiles::get_default();
      if (m_map[type_name].exists(p)) return m_map[type_name][p];
      p = ref_profiles::get_config_default();
      if (m_map[type_name].exists(p)) return m_map[type_name][p];
      return null;
    endfunction

    function int size();
      return m_map.size();
    endfunction

    function void dump();
      $display("reflib: %0d woven type(s), default profile '%s'", m_map.size(),
               ref_profiles::get_default());
      foreach (m_map[t, p]) begin
        $display("reflib:   %s [%s] -> %s", t, p, m_map[t][p].impl_name());
      end
    endfunction
  endclass

  // Per-user-type implementation slot.
  class ref_type #(type T = int);
    static ref_impl #(T) impls[string];          // profile -> creator
    static string m_type_name;

    static function void add(string profile, ref_impl #(T) c);
      impls[profile] = c;
      m_type_name = c.type_name();
    endfunction

    static function ref_impl #(T) lookup(string inst_path = "");
      string p;
      ref_impl #(T) c;
      if (impls.size() == 0) return null;
      p = ref_profiles::active(m_type_name, inst_path);
      if (impls.exists(p)) c = impls[p];
      else begin
        // Fall back to the default profile, then to the config's (always built).
        p = ref_profiles::get_default();
        if (impls.exists(p)) c = impls[p];
        else begin
          p = ref_profiles::get_config_default();
          if (impls.exists(p)) c = impls[p];
        end
      end
      if (ref_profiles::report_on()) begin
        $display("reflib: resolve %s @ '%s' -> %s", m_type_name, inst_path,
                 (c != null) ? c.impl_name() : "(unwoven)");
      end
      return c;
    endfunction

    // The woven object for the active profile of (T, inst_path), or null.
    static function T create(string inst_path = "");
      ref_impl #(T) c = lookup(inst_path);
      if (c == null) return null;
      return c.create();
    endfunction
  endclass

  // ---------------------------------------------------------------------------
  // Profile selection (design §8.1)
  // ---------------------------------------------------------------------------
  // These are reported unused by -Wall in Verilator 5.054, although select() writes them and
  // active() reads them.
  /* verilator lint_off UNUSEDSIGNAL */
  class ref_profile_rule;
    string profile;
    string type_glob;
    string inst_glob;
  endclass
  /* verilator lint_on UNUSEDSIGNAL */

  class ref_profiles;
    static local string m_config_default;
    static local string m_default;
    static local string m_plusarg_default;
    static local ref_profile_rule m_rules[$];
    static local bit m_plusargs_read;

    // The default profile, in priority order: +weave_profile=<p>, then set_default(),
    // then the config's default-profile (set by the generated registration code).
    static function void set_default(string profile);
      m_default = profile;
    endfunction

    static function void set_config_default(string profile);
      m_config_default = profile;
    endfunction

    static function string get_config_default();
      return m_config_default;
    endfunction

    static function string get_default();
      from_plusargs();
      if (m_plusarg_default != "") return m_plusarg_default;
      if (m_default != "") return m_default;
      return m_config_default;
    endfunction

    // Use <profile> for types matching type_glob created at paths matching inst_glob.
    static function void select(string profile, string type_glob = "*",
                                string inst_glob = "*");
      ref_profile_rule r = new();
      r.profile = profile;
      r.type_glob = type_glob;
      r.inst_glob = inst_glob;
      m_rules.push_back(r);
    endfunction

    static function void clear_rules();
      m_rules.delete();
    endfunction

    // +weave_report: print every resolution, and the registry at initialisation.
    static local int m_report = -1;
    static function bit report_on();
      if (m_report == -1) m_report = $test$plusargs("weave_report") ? 1 : 0;
      return m_report == 1;
    endfunction

    // The most specific matching rule wins; ties go to the rule declared last.
    // Without a matching rule, the default profile.
    static function string active(string type_name, string inst_path = "");
      ref_profile_rule best;
      int best_w = -1;
      from_plusargs();
      foreach (m_rules[i]) begin
        ref_profile_rule r = m_rules[i];
        if (ref_glob(r.type_glob, type_name) && ref_glob(r.inst_glob, inst_path)) begin
          int w = ref_glob_weight(r.type_glob) + ref_glob_weight(r.inst_glob);
          if (w >= best_w) begin
            best = r;
            best_w = w;
          end
        end
      end
      if (best != null) return best.profile;
      return get_default();
    endfunction

    // +weave_profile=<profile>
    // +weave_impl=<profile>:<type_glob>[@<inst_glob>][,<profile>:<type_glob>[@<inst_glob>]...]
    static function void from_plusargs();
      string v;
      if (m_plusargs_read) return;
      m_plusargs_read = 1;
      if ($value$plusargs("weave_profile=%s", v)) m_plusarg_default = v;
      if ($value$plusargs("weave_impl=%s", v)) parse_impl_rules(v);
    endfunction

    static function void parse_impl_rules(string spec);
      int start = 0;
      for (int i = 0; i <= spec.len(); i++) begin
        if (i == spec.len() || spec[i] == ",") begin
          if (i > start) parse_impl_rule(spec.substr(start, i - 1));
          start = i + 1;
        end
      end
    endfunction

    static local function void parse_impl_rule(string rule);
      int colon = -1;
      int at = -1;
      string prof;
      string tglob;
      string iglob = "*";
      for (int i = 0; i < rule.len(); i++) begin
        if (rule[i] == ":" && colon == -1) colon = i;
        else if (rule[i] == "@" && colon != -1 && at == -1) at = i;
      end
      if (colon <= 0 || colon == rule.len() - 1) begin
        $display("reflib: WARNING: ignoring malformed +weave_impl rule '%s' ",
                 "(expected <profile>:<type_glob>[@<inst_glob>])", rule);
        return;
      end
      prof = rule.substr(0, colon - 1);
      if (at == -1) begin
        tglob = rule.substr(colon + 1, rule.len() - 1);
      end else begin
        tglob = rule.substr(colon + 1, at - 1);
        if (at < rule.len() - 1) iglob = rule.substr(at + 1, rule.len() - 1);
      end
      select(prof, tglob, iglob);
    endfunction
  endclass

  // ---------------------------------------------------------------------------
  // Compare reporting: woven compare() calls this for the first differing field.
  // Prints only with +weave_compare_verbose (or after ref_compare_verbose = 1).
  // ---------------------------------------------------------------------------
  bit ref_compare_verbose;
  bit ref_compare_verbose_read;
  /* verilator lint_off UNUSEDSIGNAL */
  string ref_last_miscompare;   // "<class>.<field>": read by user code and tests
  /* verilator lint_on UNUSEDSIGNAL */

  function automatic void ref_miscompare(string cls, string field);
    if (!ref_compare_verbose_read) begin
      ref_compare_verbose_read = 1;
      if ($test$plusargs("weave_compare_verbose")) ref_compare_verbose = 1;
    end
    ref_last_miscompare = {cls, ".", field};
    if (ref_compare_verbose) $display("reflib: compare: %s.%s differs", cls, field);
  endfunction

  // ---------------------------------------------------------------------------
  // Plain binding: root class and factory (design §8.3)
  // ---------------------------------------------------------------------------

  // Root class of the plain binding. Its virtual methods are the plain binding's
  // features; woven subclasses override them.
  virtual class ref_object;
    // Name of the woven implementation, "" when the object is not woven.
    virtual function string ref_impl_name();
      return "";
    endfunction

    // Feature 'copy': copy the fields of rhs into this object.
    virtual function void copy(ref_object rhs);
    endfunction

    // Feature 'compare': 1 when rhs has equal fields.
    virtual function bit compare(ref_object rhs);
      return 1;
    endfunction

    // Feature 'print': the fields as text.
    virtual function string sprint();
      return "";
    endfunction
  endclass

  // A user-level type override for the plain factory: create something else in
  // place of T.
  virtual class ref_override #(type T = int);
    /* verilator lint_off UNUSEDSIGNAL */
    pure virtual function T create(string inst_path);
    /* verilator lint_on UNUSEDSIGNAL */
  endclass

  typedef class ref_factory;

  // Override T with O. O is itself created through the factory, so O's own
  // overrides and its woven implementation apply.
  class ref_override_to #(type T = int, type O = int) extends ref_override #(T);
    static local ref_override_to #(T, O) m_inst;

    static function ref_override_to #(T, O) get();
      if (m_inst == null) m_inst = new();
      return m_inst;
    endfunction

    virtual function T create(string inst_path);
      O o = ref_factory #(O)::create(inst_path);
      return o;
    endfunction
  endclass

  // The plain factory. ref_factory#(T)::create() resolves the user's override for T
  // (if any), then the woven implementation for the active profile, then falls back
  // to T::new(). T must be a concrete class.
  class ref_factory #(type T = int);
    static local ref_override #(T) m_override;

    static function void set_override(ref_override #(T) o);
      m_override = o;
    endfunction

    static function T create(string inst_path = "");
      T obj;
      if (m_override != null) return m_override.create(inst_path);
      obj = ref_type #(T)::create(inst_path);
      if (obj == null) obj = new();
      return obj;
    endfunction
  endclass

endpackage

`endif
