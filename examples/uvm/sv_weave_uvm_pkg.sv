// sv_weave_uvm_pkg: the UVM example binding's SV side (examples/uvm/). Not part of
// sv-weave; the real one belongs in sv-weave-uvm.
//
// A uvm_default_factory subclass. The UVM factory first resolves the requested type
// through its normal type and instance overrides; this factory then substitutes the
// woven class registered for the *resolved* type and the active profile:
//
//     tx --(user override)--> my_tx --(woven, profile)--> Woven_my_tx__release
//
// So the result does not depend on the order in which overrides and woven classes are
// registered (sv-weave handoff: "do not do this with plain UVM type overrides").
// Profile: +weave_profile=<p>, else the config's default-profile.
// Compile after uvm_pkg and before the woven packages.
`ifndef SV_WEAVE_UVM_PKG_SV
`define SV_WEAVE_UVM_PKG_SV

`include "uvm_macros.svh"

package sv_weave_uvm_pkg;
  import uvm_pkg::*;

  class sv_weave_uvm_factory extends uvm_default_factory;
    // resolved type -> profile -> woven class. Keyed by the type's wrapper (one per
    // type), not its name, so same-named classes in different packages stay apart.
    local uvm_object_wrapper m_woven[uvm_object_wrapper][string];
    local string m_config_default;
    local string m_plusarg_profile;
    local bit    m_plusargs_read;

    // Installs this factory in the core service (once) and returns it. Called by the
    // generated registration code, before the testbench creates anything.
    static function sv_weave_uvm_factory install();
      uvm_coreservice_t cs = uvm_coreservice_t::get();
      uvm_factory f = cs.get_factory();
      sv_weave_uvm_factory wf;
      if ($cast(wf, f)) return wf;
      wf = new();
      cs.set_factory(wf);
      return wf;
    endfunction

    function void set_config_default(string profile);
      m_config_default = profile;
    endfunction

    function void add(uvm_object_wrapper user_type, string profile,
                      uvm_object_wrapper woven_type);
      m_woven[user_type][profile] = woven_type;
    endfunction

    function string profile();
      if (!m_plusargs_read) begin
        m_plusargs_read = 1;
        void'($value$plusargs("weave_profile=%s", m_plusarg_profile));
      end
      return (m_plusarg_profile != "") ? m_plusarg_profile : m_config_default;
    endfunction

    // The woven class for an already-resolved type, or the type itself.
    function uvm_object_wrapper woven_of(uvm_object_wrapper t);
      string p;
      if (t == null || !m_woven.exists(t)) return t;
      p = profile();
      if (m_woven[t].exists(p)) return m_woven[t][p];
      if (m_woven[t].exists(m_config_default)) return m_woven[t][m_config_default];
      return t;
    endfunction

    virtual function uvm_object_wrapper find_override_by_type(
        uvm_object_wrapper requested_type, string full_inst_path);
      return woven_of(super.find_override_by_type(requested_type, full_inst_path));
    endfunction

    virtual function uvm_object_wrapper find_override_by_name(
        string requested_type_name, string full_inst_path);
      return woven_of(super.find_override_by_name(requested_type_name, full_inst_path));
    endfunction
  endclass

endpackage

`endif
