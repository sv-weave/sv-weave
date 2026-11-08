// xezim 0.11.3 bug: a parameterized class specialized with a package-qualified
// type argument (P#(u_pkg::C)) gets a different specialization -- and so separate
// static storage -- than the same type spelled unqualified via import (P#(C)).
// IEEE 1800-2017 8.25: identical type parameter values => same specialization.
package u_pkg;
  class C; endclass
endpackage

module tb;
  class P #(type T = int);
    static int n;
  endclass
  import u_pkg::*;
  typedef u_pkg::C C_t;
  initial begin
    P#(u_pkg::C)::n = 5;
    $display("P#(C)::n   = %0d (expect 5)", P#(C)::n);
    $display("P#(C_t)::n = %0d (expect 5)", P#(C_t)::n);
    if (P#(C)::n != 5) $display("FAIL: P#(C) and P#(u_pkg::C) are distinct specializations");
    else               $display("PASS");
    $finish;
  end
endmodule
