// copy_hier3: fields from all three levels (two packages) are copied and compared;
// a grandparent field difference makes compare fail, and is reported.
module tb;
  import reflib_pkg::*;
  import base_pkg::*;
  import mid_pkg::*;

  sv_weave_init_m u_init();

  initial begin
    child a, b;
    a = ref_factory #(child)::create();
    b = ref_factory #(child)::create();
    `CHECK_EQ(a.ref_impl_name(), "Woven_child__release", "woven child")
    a.g = 7; a.set_gs("grand"); a.p = 3; a.pq = '{1, 2}; a.c = BLUE;
    b.copy(a);
    `CHECK_EQ(b.g, 7, "grandparent field copied")
    `CHECK_EQ(b.get_gs(), "grand", "protected grandparent field copied")
    `CHECK_EQ(b.p, 3, "parent field copied")
    `CHECK_EQ(b.pq.size(), 2, "parent queue copied")
    `CHECK_EQ(b.c, BLUE, "own enum copied")
    `CHECK(b.compare(a), "copy compares equal")
    b.g = 8;
    `CHECK(!b.compare(a), "grandparent difference detected")
    `CHECK_EQ(ref_last_miscompare, "mid_pkg::child.g", "first difference reported")
    b.g = 7;
    b.set_gs("other");
    `CHECK(!b.compare(a), "protected grandparent difference detected")
    check_pkg::pass();
    $finish;
  end
endmodule
