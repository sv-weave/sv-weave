"""Conversion of slang types to ``SvType`` (design §4.2).

``SvType`` gives weavers a coarse category to pick a strategy from, plus an SV
spelling that is valid inside a woven class. A woven class lives in another package
(``<P>_woven``) but extends the user class, so:
- package-level names are spelled qualified (``p::pe_t``, ``p::C``);
- names declared inside a class are spelled bare (``e_t``): the woven subclass
  inherits them;
- anonymous enums and structs cannot be spelled at all (``spelling is None``).

An unpacked array type splits into ``spelling`` (the element type) and ``unpacked``
(the dimensions), because SV writes those dimensions after the variable name. Use
``declare(name)``.
"""
import dataclasses as dc
import enum
from typing import FrozenSet, Optional

from pyslang import ast as A


class TypeCat(enum.Enum):
    INTEGRAL = "integral"
    ENUM = "enum"
    STRING = "string"
    REAL = "real"
    CHANDLE = "chandle"
    EVENT = "event"
    CLASS = "class"
    ARRAY = "array"
    STRUCT = "struct"
    UNION = "union"
    VIRTUAL_IF = "virtual_interface"
    VOID = "void"
    OTHER = "other"


class ArrayKind(enum.Enum):
    FIXED = "fixed"
    DYNAMIC = "dynamic"
    QUEUE = "queue"
    ASSOC = "assoc"


@dc.dataclass(frozen=True)
class SvType:
    cat: TypeCat
    spelling: Optional[str]           # None: cannot be named outside its declaration
    unpacked: str = ""                # unpacked dimensions, written after the name
    width: int = 0
    signed: bool = False
    four_state: bool = False
    packed: bool = False              # packed struct/union
    elem: Optional["SvType"] = None   # array element
    array_kind: Optional[ArrayKind] = None
    index: Optional["SvType"] = None  # assoc index type; None for [*]
    class_qname: Optional[str] = None # class handles: qualified name of the class
    text: str = ""                    # slang's own rendering, for messages

    @property
    def nameable(self) -> bool:
        return self.spelling is not None

    def declare(self, name: str) -> str:
        if self.spelling is None:
            raise ValueError("type '%s' has no spelling outside its declaration" % self.text)
        return "%s %s%s" % (self.spelling, name, self.unpacked)

    def __str__(self):
        if self.spelling is None:
            return self.text
        return self.spelling + self.unpacked


VOID = SvType(TypeCat.VOID, "void", text="void")


class TypeConverter:
    """Converts slang types. ``packages`` is the set of package names in the design,
    used to tell package-scoped names from class- or module-scoped ones."""

    def __init__(self, packages: FrozenSet[str]):
        self.packages = packages

    # -- names ---------------------------------------------------------------
    def scoped_name(self, sym) -> Optional[str]:
        """How code in another package names ``sym``: ``pkg::name`` for package
        members, the bare name for class members, None for anything else."""
        path = sym.lexicalPath or sym.name
        parts = path.split("::")
        if len(parts) == 2 and parts[0] in self.packages:
            return path
        if len(parts) > 2 and parts[0] in self.packages:
            return sym.name
        if len(parts) == 1 and "." not in path:
            return path       # $unit scope
        return None

    def class_spelling(self, ct) -> Optional[str]:
        """``p::C`` or ``p::G#(16, int)`` for a class type."""
        if ct.genericClass is not None:
            base = self.scoped_name(ct.genericClass)
            if base is None:
                return None
            vals = []
            for m in ct:
                if m.kind == A.SymbolKind.Parameter and m.isPortParam:
                    vals.append(str(m.value))
                elif m.kind == A.SymbolKind.TypeParameter and m.isPortParam:
                    sub = self.convert(m.targetType.type)
                    if sub.spelling is None or sub.unpacked:
                        return None
                    vals.append(sub.spelling)
            return "%s#(%s)" % (base, ", ".join(vals))
        return self.scoped_name(ct)

    # -- conversion ----------------------------------------------------------
    def convert(self, t) -> SvType:
        text = str(t)
        if t.isAlias:
            inner = self.convert(t.canonicalType)
            name = self.scoped_name(t)
            if name is None:
                return dc.replace(inner, text=text)
            # The alias name covers any unpacked dimensions too.
            return dc.replace(inner, spelling=name, unpacked="", text=text)

        ct = t.canonicalType
        if isinstance(ct, A.ClassType):
            return SvType(TypeCat.CLASS, self.class_spelling(ct), text=text,
                          class_qname=self.class_qname(ct))
        if ct.isVoid:
            return VOID
        if ct.isEnum:
            # A named enum arrives as an alias (above); this one is anonymous.
            return SvType(TypeCat.ENUM, None, width=ct.bitWidth, signed=ct.isSigned,
                          four_state=ct.isFourState, text=text)
        if ct.isStruct or ct.isPackedUnion or ct.isUnpackedUnion:
            cat = TypeCat.STRUCT if ct.isStruct else TypeCat.UNION
            packed = ct.isIntegral
            return SvType(cat, None, width=ct.bitWidth if packed else 0, signed=ct.isSigned,
                          four_state=ct.isFourState, packed=packed, text=text)
        if ct.isIntegral:
            return SvType(TypeCat.INTEGRAL, _compact(text), width=ct.bitWidth,
                          signed=ct.isSigned, four_state=ct.isFourState, text=text)
        if ct.isString:
            return SvType(TypeCat.STRING, "string", text=text)
        if ct.isFloating:
            return SvType(TypeCat.REAL, text, width=ct.bitWidth, text=text)
        if ct.isCHandle:
            return SvType(TypeCat.CHANDLE, "chandle", text=text)
        if ct.isEvent:
            return SvType(TypeCat.EVENT, "event", text=text)
        if ct.isVirtualInterface:
            return SvType(TypeCat.VIRTUAL_IF, None, text=text)
        if ct.isUnpackedArray:
            return self._array(ct, text)
        return SvType(TypeCat.OTHER, None, text=text)

    def _array(self, ct, text) -> SvType:
        elem = self.convert(ct.elementType)
        index = None
        if isinstance(ct, A.FixedSizeUnpackedArrayType):
            kind = ArrayKind.FIXED
            r = ct.range
            dim = "[%d:%d]" % (r.left, r.right)
        elif isinstance(ct, A.DynamicArrayType):
            kind, dim = ArrayKind.DYNAMIC, "[]"
        elif isinstance(ct, A.QueueType):
            kind = ArrayKind.QUEUE
            dim = "[$:%d]" % ct.maxBound if ct.maxBound else "[$]"
        elif isinstance(ct, A.AssociativeArrayType):
            kind = ArrayKind.ASSOC
            if ct.indexType is None:
                dim = "[*]"
            else:
                index = self.convert(ct.indexType)
                dim = "[%s]" % index.spelling if index.spelling and not index.unpacked else None
        else:
            return SvType(TypeCat.OTHER, None, text=text)
        spelling = elem.spelling if dim is not None else None
        unpacked = dim + elem.unpacked if dim is not None else ""
        return SvType(TypeCat.ARRAY, spelling, unpacked=unpacked, elem=elem,
                      array_kind=kind, index=index, text=text)

    def class_qname(self, ct) -> str:
        if ct.genericClass is not None:
            return (ct.genericClass.lexicalPath or ct.genericClass.name) + _param_suffix(str(ct))
        return ct.lexicalPath or ct.name


def _param_suffix(text: str) -> str:
    i = text.find("#(")
    return text[i:] if i >= 0 else ""


def _compact(text: str) -> str:
    """slang writes ``bit[7:0]``; emit ``bit [7:0]``."""
    i = text.find("[")
    if i > 0 and text[i - 1] != " ":
        return text[:i] + " " + text[i:]
    return text
