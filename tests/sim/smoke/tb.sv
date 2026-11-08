// Toolchain smoke: the SV class features the woven code relies on.
package smoke_pkg;
  class base;
    int a;
    function new(); a = 1; endfunction
    virtual function string name(); return "base"; endfunction
  endclass

  class derived extends base;
    int b;
    function new(); super.new(); b = 2; endfunction
    virtual function string name(); return {"derived<", super.name(), ">"}; endfunction
  endclass

  class box #(type T = int, int W = 8);
    T v;
    bit [W-1:0] w;
    static function string kind(); return $sformatf("box#(W=%0d)", W); endfunction
  endclass

  // A static class member with an initialiser that calls a function: the
  // pattern the opt-in static registration (D2) depends on.
  class registry;
    static int n_registered;
    static function bit register(string name);
      n_registered++;
      return 1;
    endfunction
  endclass

  class auto_reg;
    static bit m_registered = registry::register("auto_reg");
  endclass
endpackage

module tb;
  import smoke_pkg::*;

  initial begin
    base     b;
    derived  d;
    derived  d2;
    box #(int, 4) bx;

    d = new();
    b = d;
    `CHECK_EQ(b.name(), "derived<base>", "virtual dispatch with super call")
    `CHECK($cast(d2, b), "$cast down to derived")
    `CHECK_EQ(d2.b, 2, "derived field after $cast")

    b = new();
    `CHECK(!$cast(d2, b), "$cast of a base object to derived fails")

    bx = new();
    bx.w = '1;
    `CHECK_EQ(bx.w, 4'hf, "parameterised width")
    `CHECK_EQ(box#(int, 4)::kind(), "box#(W=4)", "parameterised static function")

    `CHECK_EQ(auto_reg::m_registered, 1'b1, "static initialiser ran")
    `CHECK_EQ(registry::n_registered, 1, "static initialiser registered once")

    check_pkg::pass();
    $finish;
  end
endmodule
