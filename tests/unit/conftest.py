import pytest

from sv_weave.frontend.loader import load_text
from sv_weave.frontend.model import build_model
import os

REFLIB = os.path.join(os.path.dirname(__file__), "..", "..", "examples", "reflib",
                      "reflib_pkg.sv")


def model_of(*texts, runtime=True):
    """Build an SvModel from inline SV, with the reference library loaded first."""
    files = [os.path.abspath(REFLIB)] if runtime else ()
    return build_model(load_text(*texts, files=files))


@pytest.fixture
def mk_model():
    return model_of
