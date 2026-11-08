// uvm_basic: the UVM example binding. The UVM factory hands out the woven class; UVM's
// copy(), compare() and convert2string() reach the woven do_copy/do_compare; a user
// override is resolved first, then woven -- whatever the registration order.
`include "uvm_macros.svh"
module tb;
  import uvm_pkg::*;
  import tx_pkg::*;

  sv_weave_init_m u_init();

  initial begin
    tx a, b, c, d;
    alt_pkg::alt_tx alt;
    a = tx::type_id::create("a");
    `CHECK_EQ(a.get_type_name(), "Woven_tx__release", "factory returns the woven class")
    a.addr = 8'h12; a.data = 32'hcafe; a.payload = '{1, 2, 3};
    b = tx::type_id::create("b");
    b.copy(a);
    `CHECK_EQ(b.addr, 8'h12, "do_copy: addr")
    `CHECK_EQ(b.payload.size(), 3, "do_copy: queue")
    `CHECK(b.compare(a), "do_compare: equal after copy")
    b.data = 0;
    `CHECK(!b.compare(a), "do_compare: difference detected")
    $display("STRING %s", a.convert2string());

    // Same type name, different class: woven classes are looked up by type, not name.
    alt = alt_pkg::alt_tx::type_id::create("alt");
    `CHECK_EQ(alt.get_type_name(), "alt_tx", "another class with UVM type name 'tx' stays unwoven")

    // An instance override, set after the woven classes were registered.
    uvm_factory::get().set_inst_override_by_type(tx::get_type(), my_tx::get_type(), "d");
    d = tx::type_id::create("d");
    `CHECK_EQ(d.get_type_name(), "Woven_my_tx__release", "instance override, then woven")
    c = tx::type_id::create("c");
    `CHECK_EQ(c.get_type_name(), "Woven_tx__release", "other instances unaffected")

    uvm_factory::get().set_type_override_by_type(tx::get_type(), my_tx::get_type());
    c = tx::type_id::create("c");
    `CHECK_EQ(c.get_type_name(), "Woven_my_tx__release", "type override, then woven")
    check_pkg::pass();
    $finish;
  end
endmodule
