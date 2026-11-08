import os
import textwrap

import pytest

from sv_weave.config import Config, load_config, parse_config
from sv_weave.diag import SvWeaveError


def cfg(text, **kw):
    return parse_config(textwrap.dedent(text), "sv-weave.yaml", **kw)


def test_defaults():
    c = cfg("sv-weave:\n  version: 1\n", base_dir="/x")
    assert c.binding is None and c.bindings == []
    assert c.verify == "full" and c.registration == "explicit"
    assert c.build_profiles == ["release"] and c.default_profile == "release"
    assert c.profile_sets("release") == ["core"]


def test_full_example():
    c = cfg("""
        sv-weave:
          version: 1
          sources:
            files: [a.sv]
            incdirs: [inc]
            defines: {SIM: 1, X: null}
          packages: {include: ["eth_*"], exclude: ["*_tb_pkg"]}
          binding: reflib
          out_dir: build/woven
          verify: syntax
          extension-sets:
            core: {}
            debug.xcheck: {}
            debug.trace: {allow_alloc: true}
          weavers:
          - {name: copy, set: core}
          - {name: xcheck, set: debug.xcheck, match: "extends(B)", options: {on_x: error}}
          profiles:
            release: [core]
            debug: [core, "debug.*"]
          build-profiles: [release, debug]
          default-profile: debug
        """, base_dir="/proj")
    assert c.extension_sets["debug.trace"].allow_alloc is True
    assert c.extension_sets["debug.xcheck"].allow_rand is False
    assert c.profile_sets("debug") == ["core", "debug.xcheck", "debug.trace"]
    assert c.weavers[1].options == {"on_x": "error"}
    assert c.default_profile == "debug"
    spec = c.source_spec()
    assert spec.files == ["/proj/a.sv"] and spec.incdirs == ["/proj/inc"]
    assert spec.defines == {"SIM": "1", "X": None}


@pytest.mark.parametrize("body,needle,line", [
    ("  verify: fast\n", "verify", 3),
    ("  bogus: 1\n", "bogus", 3),
    ("  weavers:\n  - name: copy\n    set: nope\n", "unknown extension set 'nope'", 5),
    ("  profiles:\n    debug: [core, 'dbg.*']\n", "matches no extension set", 4),
    ("  default-profile: debug\n", "not in build-profiles", 3),
])
def test_errors_have_line(body, needle, line):
    with pytest.raises(SvWeaveError) as e:
        cfg("sv-weave:\n  version: 1\n" + body)
    d = e.value.diags[0]
    assert needle in d.msg
    assert d.loc.file == "sv-weave.yaml" and d.loc.line == line


def test_missing_top_key():
    with pytest.raises(SvWeaveError, match="top-level 'sv-weave:'"):
        cfg("other: 1\n")


def test_bad_yaml_has_line():
    with pytest.raises(SvWeaveError) as e:
        cfg("sv-weave:\n  version: [1\n")
    assert e.value.diags[0].loc.line >= 2


def test_load_config_file(tmp_path):
    p = tmp_path / "sv-weave.yaml"
    p.write_text("sv-weave:\n  sources: {files: [x.sv]}\n")
    c = load_config(str(p))
    assert c.base_dir == str(tmp_path)
    assert c.source_spec().files == [str(tmp_path / "x.sv")]
