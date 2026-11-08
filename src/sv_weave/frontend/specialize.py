"""Finding every elaborated specialisation of a parameterised class (design §4.3).

pyslang has no API that lists them, so two passes cover the design:
1. a walk over every scope (packages, ``$unit``, class bodies, subroutines, module
   instance bodies and statement blocks), converting the type of every declaration
   (properties, variables, arguments, return types, typedefs, type parameters, base
   classes), unwrapping arrays;
2. pyslang's own visitor, which reaches types that appear only in expressions, such as
   ``G#(9)::create()``.

Every specialisation found is walked in turn, so nested ones (``G#(4, G#(2))``) and
those used only in an ``extends`` clause are found too. Results are deduplicated by
generic class and parameter values.

pyslang wrapper objects are temporaries: two different symbols can get the same
``id()`` once one is garbage-collected. The walker keeps a reference to every scope it
has visited, so its ``id()``-based visited set stays sound.
"""
from typing import Dict, List

from pyslang import ast as A

from .loader import Loaded

SK = A.SymbolKind

_TYPED = (SK.ClassProperty, SK.Variable, SK.FormalArgument, SK.Parameter, SK.Net)
_SKIP = (SK.TransparentMember, SK.GenericClassDef, SK.ProceduralBlock)


class _Finder:
    def __init__(self):
        self.found: Dict[tuple, object] = {}
        self.seen = set()
        self.keep: List[object] = []

    def key(self, ct) -> tuple:
        g = ct.genericClass
        return (g.lexicalPath or g.name, str(ct))

    def type(self, t):
        if t is None:
            return
        try:
            t = t.canonicalType
        except Exception:
            return
        if isinstance(t, A.ClassType):
            if t.genericClass is not None:
                k = self.key(t)
                if k not in self.found:
                    self.found[k] = t
                    self.scope(t)
            if t.baseClass is not None:
                self.type(t.baseClass)
            return
        elem = getattr(t, "elementType", None)
        if elem is not None:
            self.type(elem)
        idx = getattr(t, "indexType", None)
        if idx is not None:
            self.type(idx)

    def scope(self, s):
        if id(s) in self.seen:
            return
        self.seen.add(id(s))
        self.keep.append(s)
        for m in s:
            k = m.kind
            if k in _SKIP:
                continue
            if isinstance(m, A.ClassType):
                self.type(m)
                self.scope(m)
                continue
            if k == SK.Instance:
                self.scope(m.body)
                continue
            if k == SK.TypeAlias:
                self.type(m.targetType.type)
                continue
            if k == SK.TypeParameter:
                self.type(m.targetType.type)
            elif k in _TYPED:
                self.type(m.type)
            elif k in (SK.Subroutine, SK.MethodPrototype):
                self.type(m.returnType)
                for a in m.arguments:
                    self.type(a.type)
            if m.isScope:
                self.scope(m)

    def visit(self, root):
        def cb(obj):
            if isinstance(obj, A.Type):
                self.type(obj)
            else:
                t = getattr(obj, "type", None)
                if isinstance(t, A.Type):
                    self.type(t)
            return A.VisitAction.Advance
        root.visit(cb)


def find_specializations(loaded: Loaded) -> List[object]:
    """Every distinct specialisation in the design, in a stable order."""
    f = _Finder()
    f.scope(loaded.root)
    for unit in loaded.compilation.getCompilationUnits():
        f.scope(unit)
    f.visit(loaded.root)
    return [f.found[k] for k in sorted(f.found)]
