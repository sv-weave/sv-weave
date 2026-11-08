// copy_arrays: every array kind; class handles shallow by default and deep with
// (* weave_deep *).
module tb;
  import reflib_pkg::*;
  import base_pkg::*;
  import mid_pkg::*;

  sv_weave_init_m u_init();

  initial begin
    child a, b;
    leaf l1, l2, l3;
    a = ref_factory #(child)::create();
    b = ref_factory #(child)::create();
    l1 = ref_factory #(leaf)::create(); l1.v = 11;
    l2 = ref_factory #(leaf)::create(); l2.v = 22;
    l3 = ref_factory #(leaf)::create(); l3.v = 33;
    a.fixed_a = '{1, 2, 3};
    a.dyn_a = new[2]; a.dyn_a[0] = 5; a.dyn_a[1] = 6;
    a.aa[10] = "ten"; a.aa[20] = "twenty";
    a.shallow_h = l1;
    a.deep_h = l2;
    a.deep_q.push_back(l3); a.deep_q.push_back(null);
    a.deep_aa["x"] = l1;
    a.shallow_q.push_back(l2);

    b.copy(a);
    `CHECK(b.fixed_a == a.fixed_a, "fixed array")
    `CHECK_EQ(b.dyn_a.size(), 2, "dynamic array size")
    `CHECK_EQ(b.dyn_a[1], 6, "dynamic array element")
    `CHECK_EQ(b.aa[20], "twenty", "associative array")
    `CHECK(b.shallow_h == l1, "shallow handle is the same object")
    `CHECK(b.deep_h != l2, "deep handle is a new object")
    `CHECK_EQ(b.deep_h.v, 22, "deep handle contents copied")
    `CHECK_EQ(b.deep_h.ref_impl_name(), "Woven_leaf__release", "deep copy made through the factory")
    `CHECK_EQ(b.deep_q.size(), 2, "deep queue size")
    `CHECK(b.deep_q[0] != l3 && b.deep_q[0].v == 33, "deep queue element")
    `CHECK(b.deep_q[1] == null, "deep queue null element")
    `CHECK(b.deep_aa["x"] != l1 && b.deep_aa["x"].v == 11, "deep assoc element")
    `CHECK(b.shallow_q[0] == l2, "shallow queue element is the same object")
    `CHECK(b.compare(a), "deep copy compares equal")

    b.deep_h.v = 99;
    `CHECK(!b.compare(a), "deep difference detected")
    `CHECK_EQ(ref_last_miscompare, "mid_pkg::child.deep_h", "deep difference reported")
    b.deep_h.v = 22;
    b.aa[30] = "extra";
    `CHECK(!b.compare(a), "associative array size difference detected")
    check_pkg::pass();
    $finish;
  end
endmodule
