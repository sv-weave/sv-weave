"""Class declarations as written in the source (``SvDecl``).

The elaborated model (``model.py``) describes classes the design specialises, with
types resolved. Generators that re-emit a parameterised class's API need the
opposite: the *generic* declaration, with its parameter header, typedefs, members and
argument types spelled as the source spells them (``ax_t``, not
``p::ty#(...)::ax_t``). That works for a parameterised class that nothing
specialises, and its output stays parameterised.

``SvDecl`` is built from the class's syntax only. Nothing is evaluated: widths are
the source expressions. Use ``SvGenericClass.decl`` / ``SvClass.decl``.
"""
import dataclasses as dc
from typing import Any, Dict, List, Optional

import pyslang
from pyslang import syntax as S

SK = S.SyntaxKind
Attrs = Dict[str, Any]


def _txt(node) -> str:
    """Source text of a node or token, without comments, whitespace collapsed to
    one space. Rebuilt from the tokens: a node's text would carry the comments
    in its first token's leading trivia."""
    if node is None:
        return ""
    if isinstance(node, pyslang.parsing.Token):
        return node.rawText
    toks = []
    node.visit(lambda x: toks.append(x)
               if isinstance(x, pyslang.parsing.Token) and not x.isMissing else None)
    out = []
    for t in toks:
        if out and len(t.trivia) > 0:
            out.append(" ")
        out.append(t.rawText)
    return "".join(out)


def _nodes(lst) -> list:
    """Elements of a separated syntax list, without the separators."""
    return [x for x in (lst or []) if isinstance(x, S.SyntaxNode)]


def attrs_of_syntax(attr_lists) -> Attrs:
    from .model import _attr_value
    out: Attrs = {}
    for al in attr_lists or []:
        for spec in getattr(al, "specs", None) or []:
            if hasattr(spec, "name") and not isinstance(spec.name, str):
                out[spec.name.valueText] = _attr_value(spec)
    return out


@dc.dataclass(eq=False)
class SvDeclArg:
    name: str
    dir: str                          # input | output | inout | ref | const ref
    type: str                         # as written, e.g. "ax_t", "logic [3:0]"
    dims: str = ""                    # unpacked dimensions as written, e.g. "[$]"
    default: Optional[str] = None

    def declare(self) -> str:
        t = "%s %s %s%s" % (self.dir, self.type, self.name, (" " + self.dims) if self.dims else "")
        return t + (" = %s" % self.default if self.default is not None else "")

    @property
    def is_output(self) -> bool:
        return self.dir in ("output", "inout")


@dc.dataclass(eq=False)
class SvDeclMethod:
    name: str
    kind: str                         # function | task
    ret: Optional[str]                # function return type as written; None for a task
    args: List[SvDeclArg]
    qualifiers: List[str]
    attrs: Attrs
    text: str

    @property
    def is_task(self) -> bool:
        return self.kind == "task"

    @property
    def is_void(self) -> bool:
        return self.ret is None or self.ret == "void"

    @property
    def inputs(self) -> List[SvDeclArg]:
        return [a for a in self.args if a.dir in ("input", "inout", "ref", "const ref")]

    @property
    def outputs(self) -> List[SvDeclArg]:
        return [a for a in self.args if a.is_output]

    def prototype(self, name: Optional[str] = None) -> str:
        """``task n(args)`` / ``function r n(args)``, without qualifiers or ``;``."""
        n = name or self.name
        args = ", ".join(a.declare() for a in self.args)
        if self.is_task:
            return "task %s(%s)" % (n, args)
        return "function %s %s(%s)" % (self.ret or "void", n, args)


@dc.dataclass(eq=False)
class SvDeclMember:
    """One member of a packed struct (a multi-name declaration gives one each)."""
    name: str
    type: str                         # as written, e.g. "logic [P.ID_W-1:0]"
    attrs: Attrs


@dc.dataclass(eq=False)
class SvDeclTypedef:
    name: str
    type: str                         # the aliased type as written
    text: str                         # the whole declaration, ending in ';'
    attrs: Attrs
    struct_kind: Optional[str] = None  # "struct packed", "union packed", ... or None
    members: List[SvDeclMember] = dc.field(default_factory=list)


@dc.dataclass(eq=False)
class SvDeclProperty:
    name: str
    type: str
    attrs: Attrs
    qualifiers: List[str]


@dc.dataclass(eq=False)
class SvDecl:
    name: str
    is_interface: bool
    is_virtual: bool
    header: str                       # parameter port list as written, "" if none
    param_names: List[str]
    extends: str                      # "" if none
    implements: List[str]
    attrs: Attrs
    typedefs: List[SvDeclTypedef] = dc.field(default_factory=list)
    methods: List[SvDeclMethod] = dc.field(default_factory=list)
    properties: List[SvDeclProperty] = dc.field(default_factory=list)

    @property
    def params_ref(self) -> str:
        """``#(P, T)``: the parameters passed straight through, "" for none."""
        return "#(%s)" % ", ".join(self.param_names) if self.param_names else ""

    def typedef(self, name: str) -> Optional[SvDeclTypedef]:
        for t in self.typedefs:
            if t.name == name:
                return t
        return None

    def method(self, name: str) -> Optional[SvDeclMethod]:
        for m in self.methods:
            if m.name == name:
                return m
        return None


def _params(plist) -> (str, List[str]):
    if plist is None:
        return "", []
    names = []
    for d in _nodes(plist.declarations):
        if d.kind == SK.ParameterDeclaration:
            names.extend(x.name.valueText for x in _nodes(d.declarators))
        elif d.kind == SK.TypeParameterDeclaration:
            names.extend(x.name.valueText for x in _nodes(d.declarators))
    return _txt(plist), names


def _method(item) -> SvDeclMethod:
    if item.kind == SK.ClassMethodPrototype:
        proto = item.prototype
    else:                                  # ClassMethodDeclaration
        proto = item.declaration.prototype
    kind = proto.keyword.valueText
    ret = _txt(proto.returnType) if kind == "function" else None
    args: List[SvDeclArg] = []
    last_dir, last_type = "input", "logic"
    if proto.portList is not None:
        for port in _nodes(proto.portList.ports):
            d = _txt(port.direction) or ""
            const = _txt(getattr(port, "constKeyword", None))
            if const and d == "ref":
                d = "const ref"
            t = _txt(port.dataType)
            if d:
                last_dir = d
                if not t:
                    t = "logic"
            elif t:
                pass
            else:
                t = last_type
            d = d or last_dir
            last_type = t
            dcl = port.declarator
            dims = "".join(_txt(x) for x in dcl.dimensions)
            default = None
            if dcl.initializer is not None:
                default = _txt(dcl.initializer.expr)
            args.append(SvDeclArg(dcl.name.valueText, d, t, dims, default))
    return SvDeclMethod(_txt(proto.name), kind, ret or None, args,
                        [_txt(q) for q in item.qualifiers], attrs_of_syntax(item.attributes),
                        _txt(item))


def _typedef(item, dcl) -> SvDeclTypedef:
    ty = dcl.type
    td = SvDeclTypedef(dcl.name.valueText, _txt(ty) + "".join(_txt(x) for x in dcl.dimensions),
                       _txt(dcl), {**attrs_of_syntax(item.attributes),
                                   **attrs_of_syntax(dcl.attributes)})
    if ty.kind in (SK.StructType, SK.UnionType):
        td.struct_kind = " ".join(x for x in (_txt(ty.keyword), _txt(ty.packed),
                                              _txt(getattr(ty, "signing", None))) if x)
        for mem in ty.members:
            a = attrs_of_syntax(mem.attributes)
            for d in _nodes(mem.declarators):
                dims = "".join(_txt(x) for x in d.dimensions)
                td.members.append(SvDeclMember(d.name.valueText, _txt(mem.type) + dims, a))
    return td


def build_decl(syn) -> Optional[SvDecl]:
    """An ``SvDecl`` from a ClassDeclarationSyntax, or None for anything else."""
    if syn is None or syn.kind != SK.ClassDeclaration:
        return None
    voi = _txt(syn.virtualOrInterface)
    header, names = _params(syn.parameters)
    ext = _txt(syn.extendsClause.baseName) if syn.extendsClause is not None else ""
    impls = []
    if syn.implementsClause is not None:
        impls = [_txt(x) for x in _nodes(syn.implementsClause.interfaces)]
    d = SvDecl(syn.name.valueText, voi == "interface", voi == "virtual", header, names,
               ext, impls, attrs_of_syntax(syn.attributes))
    for item in syn.items:
        k = item.kind
        if k in (SK.ClassMethodPrototype, SK.ClassMethodDeclaration):
            d.methods.append(_method(item))
        elif k == SK.ClassPropertyDeclaration:
            dcl = item.declaration
            if dcl.kind == SK.TypedefDeclaration:
                d.typedefs.append(_typedef(item, dcl))
            elif dcl.kind == SK.DataDeclaration:
                a = {**attrs_of_syntax(item.attributes), **attrs_of_syntax(dcl.attributes)}
                quals = [_txt(q) for q in item.qualifiers] + [_txt(m) for m in dcl.modifiers]
                for x in _nodes(dcl.declarators):
                    dims = "".join(_txt(y) for y in x.dimensions)
                    d.properties.append(SvDeclProperty(x.name.valueText,
                                                       _txt(dcl.type) + dims, a, quals))
    return d
