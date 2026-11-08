// profile_runtime: both profiles are built; plusargs choose between them.
//   +mode=default   no selection: release everywhere
//   +mode=profile   with +weave_profile=debug: debug everywhere it exists
//   +mode=type      with +weave_impl=debug:prof_pkg::pkt: only pkt is debug
//   +mode=inst      with +weave_impl=debug:*@tb.dbg*: only matching instances
module tb;
  import reflib_pkg::*;
  import prof_pkg::*;

  sv_weave_init_m u_init();

  initial begin
    string mode;
    pkt p, p2;
    other o;
    same s;
    if (!$value$plusargs("mode=%s", mode)) mode = "default";
    p = ref_factory #(pkt)::create("tb.p");
    o = ref_factory #(other)::create("tb.o");
    s = ref_factory #(same)::create("tb.s");
    p2 = ref_factory #(pkt)::create("tb.dbg1");
    `CHECK_EQ(s.ref_impl_name(), "Woven_same__release", "deduplicated class serves every profile")
    case (mode)
      "default": begin
        `CHECK_EQ(p.ref_impl_name(), "Woven_pkt__release", "default: pkt")
        `CHECK_EQ(o.ref_impl_name(), "Woven_other__release", "default: other")
      end
      "profile": begin
        `CHECK_EQ(p.ref_impl_name(), "Woven_pkt__debug", "profile: pkt")
        `CHECK_EQ(o.ref_impl_name(), "Woven_other__debug", "profile: other")
      end
      "type": begin
        `CHECK_EQ(p.ref_impl_name(), "Woven_pkt__debug", "type: pkt")
        `CHECK_EQ(o.ref_impl_name(), "Woven_other__release", "type: other")
      end
      "inst": begin
        `CHECK_EQ(p.ref_impl_name(), "Woven_pkt__release", "inst: tb.p")
        `CHECK_EQ(p2.ref_impl_name(), "Woven_pkt__debug", "inst: tb.dbg1")
        `CHECK_EQ(o.ref_impl_name(), "Woven_other__release", "inst: other")
      end
      default: check_pkg::fail({"unknown mode ", mode});
    endcase
    // Runtime selection from code also works: the most specific rule wins.
    ref_profiles::select("debug", "prof_pkg::other", "tb.code*");
    o = ref_factory #(other)::create("tb.code1");
    `CHECK_EQ(o.ref_impl_name(), "Woven_other__debug", "select() from code")
    check_pkg::pass();
    $finish;
  end
endmodule
