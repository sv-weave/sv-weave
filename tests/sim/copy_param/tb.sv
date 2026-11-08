// copy_param: two specialisations of one generic class each get their own woven class.
module tb;
  import reflib_pkg::*;
  import mid_pkg::*;

  sv_weave_init_m u_init();

  initial begin
    G#(8)  a8, b8;
    G#(16) a16, b16;
    a8 = ref_factory #(G#(8))::create();
    b8 = ref_factory #(G#(8))::create();
    a16 = ref_factory #(G#(16))::create();
    b16 = ref_factory #(G#(16))::create();
    `CHECK(a8.ref_impl_name() != "", "G#(8) is woven")
    `CHECK(a16.ref_impl_name() != "", "G#(16) is woven")
    `CHECK(a8.ref_impl_name() != a16.ref_impl_name(), "separate woven classes")
    a8.v = 8'hab;
    a16.v = 16'hbeef;
    b8.copy(a8);
    b16.copy(a16);
    `CHECK_EQ(b8.v, 8'hab, "G#(8) copied")
    `CHECK_EQ(b16.v, 16'hbeef, "G#(16) copied")
    `CHECK(b16.compare(a16), "G#(16) compares equal")
    check_pkg::pass();
    $finish;
  end
endmodule
