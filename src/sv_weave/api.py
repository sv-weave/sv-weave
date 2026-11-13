"""Public API of sv-weave.

Weavers and bindings import from this module only. Anything not re-exported
here is internal and may change without notice. ``API_VERSION`` follows the
rules in design §10: a minor bump adds, a major bump breaks.
"""
from .__version__ import __version__

from .api_version import API_VERSION
from .frontend.decl import (SvDecl, SvDeclArg, SvDeclMember, SvDeclMethod,
                            SvDeclProperty, SvDeclTypedef)
from .weave.templates import SvText

__all__ = ["API_VERSION", "__version__", "SvDecl", "SvDeclArg", "SvDeclMember",
           "SvDeclMethod", "SvDeclProperty", "SvDeclTypedef", "SvText"]
