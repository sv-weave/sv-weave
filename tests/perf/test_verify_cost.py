"""D9: what Load and Verify cost. Run with ``pytest -m perf -s tests/perf``.

Prints one row per scenario: stage timings in seconds. The results and the D9
proposal are in docs/design/notes/verify-cost.md.
"""
import os
import time

import pytest

from sv_weave.config import parse_config
from sv_weave.filelist import SourceSpec
from sv_weave.run import run

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
UVM_SRC = os.path.join(ROOT, "packages", "verilator", "share", "uvm", "src")

pytestmark = [pytest.mark.perf, pytest.mark.usefixtures("test_weavers")]

CFG = parse_config("sv-weave:\n  binding: reflib\n  weavers: [{name: t_copy}, {name: t_build}]\n")


def plain_classes(n: int) -> str:
    """n classes in a 4-deep hierarchy under ref_object, with a mix of field kinds."""
    out = ["package gen_pkg;", "  import reflib_pkg::*;"]
    for i in range(n):
        base = "ref_object" if i % 4 == 0 else "c%d" % (i - 1)
        out.append("  class c%d extends %s;" % (i, base))
        out.append("    rand bit [7:0] a%d; int q%d[$]; string s%d; protected int p%d;" % (i, i, i, i))
        out.append("    virtual function void build(); endfunction")
        out.append("  endclass")
    out.append("endpackage")
    return "\n".join(out) + "\n"


def uvm_env(n: int) -> str:
    """A small UVM testbench: n sequence items, a sequence, a driver, an env and a test."""
    out = ["`include \"uvm_macros.svh\"", "package env_pkg;", "  import uvm_pkg::*;"]
    for i in range(n):
        out += ["  class item%d extends uvm_sequence_item;" % i,
                "    rand bit [31:0] addr; rand bit [7:0] data[];",
                "    `uvm_object_utils_begin(item%d)" % i,
                "      `uvm_field_int(addr, UVM_ALL_ON)",
                "      `uvm_field_array_int(data, UVM_ALL_ON)",
                "    `uvm_object_utils_end",
                "    function new(string name = \"item%d\"); super.new(name); endfunction" % i,
                "  endclass"]
    out += ["  class seq extends uvm_sequence #(item0);",
            "    `uvm_object_utils(seq)",
            "    function new(string name = \"seq\"); super.new(name); endfunction",
            "    task body(); item0 it = item0::type_id::create(\"it\"); start_item(it);"
            " void'(it.randomize()); finish_item(it); endtask",
            "  endclass",
            "  class drv extends uvm_driver #(item0);",
            "    `uvm_component_utils(drv)",
            "    function new(string name, uvm_component parent); super.new(name, parent); endfunction",
            "    task run_phase(uvm_phase phase); forever begin seq_item_port.get_next_item(req);"
            " seq_item_port.item_done(); end endtask",
            "  endclass",
            "  class env extends uvm_env;",
            "    `uvm_component_utils(env)",
            "    drv d; uvm_sequencer #(item0) sqr;",
            "    function new(string name, uvm_component parent); super.new(name, parent); endfunction",
            "    function void build_phase(uvm_phase phase); d = drv::type_id::create(\"d\", this);"
            " sqr = uvm_sequencer#(item0)::type_id::create(\"sqr\", this); endfunction",
            "    function void connect_phase(uvm_phase phase);"
            " d.seq_item_port.connect(sqr.seq_item_export); endfunction",
            "  endclass",
            "  class test extends uvm_test;",
            "    `uvm_component_utils(test)",
            "    env e;",
            "    function new(string name, uvm_component parent); super.new(name, parent); endfunction",
            "    function void build_phase(uvm_phase phase); e = env::type_id::create(\"e\", this);"
            " endfunction",
            "  endclass",
            "endpackage",
            "module tb; import uvm_pkg::*; initial run_test(\"test\"); endmodule"]
    return "\n".join(out) + "\n"


def measure(name, tmp_path, texts, spec=None, verify="full", out=None):
    out = out or str(tmp_path / ("%s-%s" % (name, verify)))
    t0 = time.perf_counter()
    res = run(CFG, spec=spec, texts=texts, out_dir=out, verify=verify)
    total = time.perf_counter() - t0
    t = res.timings
    print("PERF %-28s verify=%-6s classes=%4d woven=%4d load=%.3f model=%.3f verify=%.3f total=%.3f"
          % (name, res.verify_status, len(res.model.classes()), len(res.woven),
             t["load"], t["model"], t["verify"], total), flush=True)
    return res, total


def test_small(tmp_path):
    for v in ("full", "syntax"):
        measure("small", tmp_path, [("g.sv", plain_classes(8))], verify=v)


def test_plain_400(tmp_path):
    for v in ("full", "syntax"):
        measure("plain-400", tmp_path, [("g.sv", plain_classes(400))], verify=v)


@pytest.mark.skipif(not os.path.isdir(UVM_SRC), reason="no UVM sources")
def test_uvm_env(tmp_path):
    spec = SourceSpec(files=[os.path.join(UVM_SRC, "uvm_pkg.sv")], incdirs=[UVM_SRC],
                      defines={"UVM_NO_DPI": None})
    texts = [("env.sv", uvm_env(200)), ("g.sv", plain_classes(200))]
    for v in ("full", "syntax"):
        measure("uvm+200items+200woven", tmp_path, texts, spec=spec, verify=v)
    # Second run with unchanged inputs: the cache skips Verify.
    res, _ = measure("uvm+200items+200woven", tmp_path, texts, spec=spec, verify="full",
                     out=str(tmp_path / "uvm+200items+200woven-full"))
    assert res.verify_status == "cached"
