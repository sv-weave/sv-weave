// user_do_copy_coexists: a hand-written copy() in a parent still runs, through super,
// and the woven code copies the remaining fields.
module tb;
  import reflib_pkg::*;
  import user_pkg::*;

  sv_weave_init_m u_init();

  initial begin
    sub_copy a, b;
    a = ref_factory #(sub_copy)::create();
    b = ref_factory #(sub_copy)::create();
    a.set_secret(42); a.visible = 1; a.extra = 2;
    b.copy(a);
    `CHECK_EQ(b.n_user_copies, 1, "user copy() ran once")
    `CHECK_EQ(b.get_secret(), 42, "user copy() copied the local field")
    `CHECK_EQ(b.visible, 1, "woven copy: parent field")
    `CHECK_EQ(b.extra, 2, "woven copy: own field")
    check_pkg::pass();
    $finish;
  end
endmodule
