"""Shared pytest configuration for sv-weave."""
import os

import pytest

# pytest-dfm has no pytest11 entry point; load its dvflow fixture explicitly. Without it
# (as in a plain CI venv) the sim tests are skipped; see tests/sim/conftest.py.
import importlib.util

pytest_plugins = ["pytest_dfm"] if importlib.util.find_spec("pytest_dfm") else []

TESTS_DIR = os.path.dirname(os.path.abspath(__file__))
EXAMPLES_DIR = os.path.join(os.path.dirname(TESTS_DIR), "examples")
REFLIB_DIR = os.path.join(EXAMPLES_DIR, "reflib")


@pytest.fixture(autouse=True, scope="session")
def reflib_binding():
    """The example reference library's binding, registered as 'reflib' for all tests."""
    import sys
    from sv_weave import plugin
    sys.path.insert(0, REFLIB_DIR)
    from reflib_binding import ReflibBinding
    plugin.register_binding(ReflibBinding)
    yield ReflibBinding


def pytest_addoption(parser):
    parser.addoption(
        "--update-golden", action="store_true", default=False,
        help="Rewrite golden expect/ files from the current output instead of comparing")


@pytest.fixture
def update_golden(request) -> bool:
    return request.config.getoption("--update-golden")


def data(*parts) -> str:
    """Path under tests/, e.g. data("sim", "smoke")."""
    return os.path.join(TESTS_DIR, *parts)


@pytest.fixture
def test_weavers():
    """Registers the weavers in tests/test_weavers.py for the duration of a test."""
    from sv_weave import plugin
    from tests.test_weavers import ALL
    for w in ALL:
        plugin.register_weaver(w)
    yield
    for w in ALL:
        plugin.unregister(w.name)
