"""sv-weave's generated init files are clean under Verilator's -Wall lint."""
import subprocess

import pytest

from sv_weave.render import INIT_FILES, render_init

pytestmark = pytest.mark.sim

WOVEN = """package p_woven;
  function automatic void __register();
  endfunction
endpackage : p_woven
"""


def test_init_lint_clean(tmp_path):
    (tmp_path / "p_woven.sv").write_text(WOVEN)
    files = [str(tmp_path / "p_woven.sv")]
    for name, text in render_init(["p_woven"]).items():
        (tmp_path / name).write_text(text)
        files.append(str(tmp_path / name))
    assert [f.rsplit("/", 1)[1] for f in files[1:]] == list(INIT_FILES)
    log = tmp_path / "lint.log"
    with open(log, "w") as fp:
        r = subprocess.run(["verilator", "--lint-only", "-Wall", "--top-module", "sv_weave_init_m"]
                           + files, stdout=fp, stderr=subprocess.STDOUT, cwd=str(tmp_path))
    out = log.read_text()
    assert r.returncode == 0 and "%Warning" not in out, out[-3000:]
