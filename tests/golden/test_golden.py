"""Golden tests: rendered woven packages and report, compared with expect/.

Run ``pytest tests/golden --update-golden`` to rewrite expect/ from the current output.
Every case's output is also elaborated by pyslang together with its sources.
"""
import os

import pytest

from sv_weave.config import load_config
from sv_weave.filelist import SourceSpec
from sv_weave.frontend.loader import load
from sv_weave.run import REPORT, run

HERE = os.path.dirname(os.path.abspath(__file__))
CASES = sorted(d for d in os.listdir(HERE)
               if os.path.isfile(os.path.join(HERE, d, "sv-weave.yaml")))


def produced(case_dir, res):
    """Generated files, with the sv-weave version (in headers and the report) replaced
    by @VERSION@, so that a version bump or a CI dev build does not change them."""
    from sv_weave import __version__
    out = {r.name: r.text for r in res.rendered}
    out.update(res.extra_files)
    with open(os.path.join(res.out_dir, REPORT)) as fp:
        out[REPORT] = fp.read().replace(case_dir + os.sep, "")
    return {k: v.replace(__version__, "@VERSION@") for k, v in out.items()}


@pytest.mark.usefixtures("test_weavers")
@pytest.mark.parametrize("case", CASES)
def test_golden(case, tmp_path, update_golden):
    case_dir = os.path.join(HERE, case)
    cfg = load_config(os.path.join(case_dir, "sv-weave.yaml"))
    res = run(cfg, out_dir=str(tmp_path))
    got = produced(case_dir, res)
    expect_dir = os.path.join(case_dir, "expect")

    if update_golden:
        os.makedirs(expect_dir, exist_ok=True)
        for name in os.listdir(expect_dir):
            os.remove(os.path.join(expect_dir, name))
        for name, text in got.items():
            with open(os.path.join(expect_dir, name), "w") as fp:
                fp.write(text)
    else:
        assert os.path.isdir(expect_dir), "no expect/ for %s; run with --update-golden" % case
        want = {}
        for name in sorted(os.listdir(expect_dir)):
            with open(os.path.join(expect_dir, name)) as fp:
                want[name] = fp.read()
        assert sorted(got) == sorted(want)
        for name in want:
            assert got[name] == want[name], "%s/%s differs (rerun with --update-golden " \
                                            "if the change is intended)" % (case, name)

    srcs = cfg.source_spec().files
    load(SourceSpec(files=res.runtime_files + srcs + res.woven_files))
