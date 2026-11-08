"""The Sphinx docs build with warnings treated as errors."""
import os
import subprocess
import sys

import pytest

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))


@pytest.mark.docs
def test_docs_build(tmp_path):
    for mod in ("sphinx", "sphinx_rtd_theme", "sphinx_dv_flow"):
        pytest.importorskip(mod, reason="doc toolchain not installed (pip install .[docs])")
    log = tmp_path / "sphinx.log"
    with open(log, "w") as fp:
        r = subprocess.run(
            [sys.executable, "-m", "sphinx", "-W", "--keep-going", "-b", "html",
             os.path.join(ROOT, "docs"), str(tmp_path / "html")],
            stdout=fp, stderr=subprocess.STDOUT)
    if r.returncode != 0:
        lines = log.read_text().splitlines()
        bad = [l for l in lines if "WARNING" in l or "ERROR" in l]
        pytest.fail("sphinx-build failed (log: %s)\n%s" % (log, "\n".join(bad[:30] or lines[-30:])))
