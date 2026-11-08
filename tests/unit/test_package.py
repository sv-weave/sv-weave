"""Package-level checks: version, public API, CLI and dv-flow registration."""
from importlib.metadata import entry_points

import sv_weave
from sv_weave import api, cli


def test_version():
    assert sv_weave.__version__ == api.__version__


def test_api_version():
    assert isinstance(api.API_VERSION, tuple) and len(api.API_VERSION) == 2


def test_cli_version(capsys):
    try:
        cli.main(["--version"])
    except SystemExit as e:
        assert e.code == 0
    assert "sv-weave" in capsys.readouterr().out


def test_dvflow_entry_point():
    eps = [e for e in entry_points(group="dv_flow.mgr") if e.name == "svweave"]
    assert len(eps) == 1
    pkgs = eps[0].load().dvfm_packages()
    assert set(pkgs) == {"svweave"}
