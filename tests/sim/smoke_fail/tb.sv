// Harness self-test: a failing check must make SimResult.assert_pass() fail.
module tb;
  initial begin
    `CHECK_EQ(1 + 1, 3, "deliberately wrong")
    check_pkg::pass();
    $finish;
  end
endmodule
