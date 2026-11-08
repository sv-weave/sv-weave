# Sphinx configuration for the sv-weave product documentation.
#
# Design and plan notes under design/ and plan/ are Markdown working documents,
# kept outside the Sphinx build.
import os
import sys

# Use the installed sv_weave when there is one (CI installs it); fall back to the source
# tree. Adding src/ unconditionally would expose a second copy of the package metadata
# (src/sv_weave.egg-info from a non-editable install), and dv-flow-mgr would then see
# the svweave entry point twice.
try:
    import sv_weave  # noqa: F401
except ImportError:
    sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src")))

from sv_weave.__version__ import __version__  # noqa: E402

project = "sv-weave"
author = "Matthew Ballance"
copyright = "2026, Matthew Ballance"
version = __version__
release = __version__

extensions = [
    "sphinx.ext.autodoc",
    "sphinx.ext.napoleon",
    "sphinx-jsonschema",
    "sphinx_dv_flow",
]

# The config reference is generated from the pydantic model, so it cannot drift.
import json  # noqa: E402

from sv_weave.config import json_schema  # noqa: E402

_GEN = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_generated")
os.makedirs(_GEN, exist_ok=True)
_schema_text = json.dumps(json_schema(), indent=2) + "\n"
_schema_path = os.path.join(_GEN, "sv-weave.schema.json")
if not os.path.isfile(_schema_path) or open(_schema_path).read() != _schema_text:
    with open(_schema_path, "w") as _fp:
        _fp.write(_schema_text)

# The dv-flow task reference is generated from the svweave package's flow.dv.
dvflow_root = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "src", "sv_weave", "dfm"))

exclude_patterns = ["_build", "_generated", "design", "plan", "Thumbs.db", ".DS_Store"]

html_theme = "sphinx_rtd_theme"
html_static_path = ["_static"]
