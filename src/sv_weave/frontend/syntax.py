"""The syntax pre-pass (``Bus.on_syntax``): weavers see the parsed sources before
elaboration and may add source text, which is elaborated with them.

This lets a weaver generate a class that the user's sources name, such as a base class
(``(* my_attr *) class foo extends foo_base``): ``foo_base`` does not exist until the
weaver writes it, so the design cannot be elaborated first. Attributes and class
headers are visible in the syntax trees.

The added files are written to the output directory and listed in ``sv_weave_pre.f``.
They are not part of the woven compile order: they must be compiled *before* the user
sources that name what they declare.
"""
import dataclasses as dc
import re
from typing import Dict, List, Optional, Sequence, Tuple

import pyslang
from pyslang import ast as A
from pyslang import syntax as S

from ..diag import Diag, Severity, SrcLoc, SvWeaveError

_NAME = re.compile(r"^[A-Za-z0-9_][A-Za-z0-9_.\-]*$")


@dc.dataclass
class SyntaxClass:
    """A class declaration as written. ``attrs`` maps each ``(* name = value *)`` on the
    declaration to the value's text (None without ``= value``). ``params`` is the
    parameter port list text (``#(int W = 1)``, "" without); ``base`` the base class name
    and ``base_args`` its parameter text (``#(W)``), both "" without ``extends``."""
    name: str
    package: str
    attrs: Dict[str, Optional[str]]
    params: str
    base: str
    base_args: str
    loc: Optional[SrcLoc]
    node: S.SyntaxNode

    @property
    def qname(self) -> str:
        return "%s::%s" % (self.package, self.name) if self.package else self.name

    def attr_string(self, name: str) -> Optional[str]:
        """An attribute's value with string quotes removed; None if it is absent."""
        v = self.attrs.get(name)
        if v is None:
            return None
        return v[1:-1] if len(v) >= 2 and v[0] == v[-1] == '"' else v


def _text(node) -> str:
    return str(node).strip() if node is not None else ""


def _package_of(node) -> str:
    p = node.parent
    while p is not None:
        if p.kind == S.SyntaxKind.PackageDeclaration:
            return p.header.name.valueText
        p = p.parent
    return ""


def syntax_classes(trees: Sequence[S.SyntaxTree],
                   sm: Optional[pyslang.SourceManager] = None) -> List[SyntaxClass]:
    """Every class declaration in ``trees``, in source order."""
    from .loader import slang_loc
    out: List[SyntaxClass] = []
    for t in trees:
        found = []

        def cb(n):
            if n.kind == S.SyntaxKind.ClassDeclaration:
                found.append(n)
            return A.VisitAction.Advance
        t.root.visit(cb)
        for n in found:
            attrs: Dict[str, Optional[str]] = {}
            for inst in n.attributes:
                for spec in inst.specs:
                    if isinstance(spec, S.AttributeSpecSyntax):
                        attrs[spec.name.valueText] = (_text(spec.value.expr)
                                                      if spec.value is not None else None)
            ext = n.extendsClause
            base, base_args = "", ""
            if ext is not None:
                bn = ext.baseName
                if isinstance(bn, S.ClassNameSyntax):
                    base, base_args = bn.identifier.valueText, _text(bn.parameters)
                else:
                    base = _text(bn)
            out.append(SyntaxClass(n.name.valueText, _package_of(n), attrs, _text(n.parameters),
                                   base, base_args,
                                   slang_loc(sm or t.sourceManager, n.name.location), n))
    return out


class SyntaxCtx:
    """What an ``on_syntax`` handler gets: the parsed sources and a way to add text."""

    def __init__(self, trees: Sequence[S.SyntaxTree], sm: pyslang.SourceManager,
                 weaver: str, options: Dict, added: List[Tuple[str, str, str]]):
        self.trees = list(trees)
        self.source_manager = sm
        self.weaver = weaver
        self.options = options
        self._added = added
        self._classes: Optional[List[SyntaxClass]] = None

    def classes(self, attr: Optional[str] = None) -> List[SyntaxClass]:
        """Class declarations, optionally only those carrying attribute ``attr``."""
        if self._classes is None:
            self._classes = syntax_classes(self.trees, self.source_manager)
        return [c for c in self._classes if attr is None or attr in c.attrs]

    def add_source(self, name: str, text: str) -> None:
        """Adds a source file ``name`` (a bare file name) holding ``text``. It is parsed
        ahead of the user's sources and written to the output directory."""
        if not _NAME.match(name):
            raise SvWeaveError([Diag(Severity.ERROR, "add_source: bad file name '%s'" % name)])
        for n, _, w in self._added:
            if n == name:
                raise SvWeaveError([Diag(Severity.ERROR, "add_source: '%s' is added twice "
                                         "(by %s and %s)" % (name, w, self.weaver))])
        self._added.append((name, text, self.weaver))
