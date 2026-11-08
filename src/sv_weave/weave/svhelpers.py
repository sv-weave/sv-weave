"""``w.sv``: helpers that produce SV fragments (design §7.2).

They deal with names, hygiene and the type knowledge every field weaver needs. The
field helpers (copy_field, compare_field, print_field) arrive in P5.
"""
from typing import Optional

from ..frontend.model import SvField, Visibility


class SvHelpers:
    def __init__(self, ctx):
        self._w = ctx

    def fresh(self, name: str) -> str:
        """A local name (``__w_<name>``) that collides with no member of the target or
        its ancestors, and with no other name issued for this woven class."""
        return self._w._b.fresh(name)

    def type_of(self, f: SvField) -> str:
        """The SV spelling of a field's type, valid inside the woven class. Raises if
        the type cannot be named there (an anonymous enum or struct)."""
        if not f.type.nameable:
            raise self._w._error("the type of %s.%s cannot be named outside its "
                                 "declaration (%s)" % (f.owner.qname, f.name, f.type.text))
        return str(f.type)

    def cast_rhs(self, slot, arg: Optional[str] = None) -> str:
        """Declares a handle of the target's type, ``$cast``s ``arg`` (default: the
        slot's ``rhs`` argument) into it, and returns the handle's name. Calling it
        again on the same slot returns the same handle."""
        cached = getattr(slot, "_cast_rhs", None)
        if cached is not None:
            return cached
        arg = arg or slot.rhs
        if arg is None:
            raise self._w._error("cast_rhs: slot '%s' has no rhs argument; pass one" % slot.name)
        local = self.fresh("rhs")
        slot.decl.add("%s %s;" % (self._w.cls.type_expr, local))
        slot.pre.add('if (!$cast(%s, %s)) begin\n'
                     '  $fatal(1, "sv-weave: %s.%s: argument is not a %s");\n'
                     'end' % (local, arg, self._w.woven.name, slot.name, self._w.cls.qname))
        slot._cast_rhs = local
        return local

    def accessible(self, f: SvField, report: bool = True) -> bool:
        """False for ``local`` fields, which no subclass can reach (design §6.4). With
        ``report``, emits a warning (an error when ``strict``) at the field's source."""
        if f.visibility != Visibility.LOCAL:
            return True
        if report:
            self._w.warning("%s.%s is local and cannot be reached from a woven subclass; "
                            "skipped (make it protected, or mark it (* weave_nocopy *))"
                            % (f.owner.qname, f.name), f.loc)
        return False

    # -- field helpers (P5) ------------------------------------------------------------
    # Each returns SV text for one field. ``rhs`` is a handle of the target's type
    # (from cast_rhs). Class-handle fields are shallow unless the field carries
    # (* weave_deep *).

    def _handle_class(self, t):
        return self._w.model.find_class(t.class_qname) if t.class_qname else None

    def _feature_method(self, feature: str) -> Optional[str]:
        spec = self._w.binding.features().get(feature)
        return spec.method if spec is not None else None

    def _new_expr(self, t) -> Optional[str]:
        """An expression creating a fresh object for a deep copy into type ``t``."""
        cls = self._handle_class(t)
        if cls is None or cls.is_abstract or t.spelling is None:
            return None
        made = self._w.binding.create_expr(cls)
        return made if made is not None else "new()"

    def _deep_handle(self, dst: str, src: str, t, f) -> str:
        copy = self._feature_method("copy")
        cls = self._handle_class(t)
        new = self._new_expr(t)
        if copy is None or cls is None or new is None or cls.find_method(copy) is None:
            self._w.warning("(* weave_deep *) on %s.%s: %s cannot be deep-copied here (needs a "
                            "concrete class with the binding's '%s' method); copied shallow"
                            % (f.owner.qname, f.name, t.text, copy), f.loc)
            return "%s = %s;" % (dst, src)
        if new == "new()":
            return ("if (%s == null) %s = null;\nelse begin\n  %s = new();\n  %s.%s(%s);\nend"
                    % (src, dst, dst, dst, copy, src))
        return ("if (%s == null) %s = null;\nelse begin\n  %s = %s;\n  %s.%s(%s);\nend"
                % (src, dst, dst, new, dst, copy, src))

    def _deep(self, dst: str, src: str, t, f, depth: int = 0) -> str:
        """Copy ``src`` into ``dst`` for a type containing class handles, deep."""
        from ..frontend.types import ArrayKind, TypeCat
        if t.cat == TypeCat.CLASS:
            return self._deep_handle(dst, src, t, f)
        if t.cat != TypeCat.ARRAY or not _has_class(t):
            return "%s = %s;" % (dst, src)
        i = self.fresh("i%d" % depth)
        inner = self._deep("%s[%s]" % (dst, i), "%s[%s]" % (src, i), t.elem, f, depth + 1)
        body = _indent(inner)
        k = t.array_kind
        if k == ArrayKind.FIXED:
            return "foreach (%s[%s]) begin\n%s\nend" % (src, i, body)
        if k == ArrayKind.DYNAMIC:
            return "%s = new[%s.size()];\nforeach (%s[%s]) begin\n%s\nend" % (dst, src, src, i, body)
        if k == ArrayKind.QUEUE:
            if t.elem.spelling is None or t.elem.unpacked:
                return "%s = %s;" % (dst, src)
            e = self.fresh("e%d" % depth)
            inner = self._deep(e, "%s[%s]" % (src, i), t.elem, f, depth + 1)
            return ("%s.delete();\nforeach (%s[%s]) begin\n  %s %s;\n%s\n  %s.push_back(%s);\nend"
                    % (dst, src, i, t.elem.spelling, e, _indent(inner), dst, e))
        # Associative.
        return "%s.delete();\nforeach (%s[%s]) begin\n%s\nend" % (dst, src, i, body)

    def copy_field(self, f: SvField, rhs: str) -> str:
        """``this.<f> = <rhs>.<f>``, deep for (* weave_deep *) class handles and arrays
        of them."""
        from ..frontend.types import TypeCat
        if f.type.cat == TypeCat.EVENT:
            return ""         # assigning an event aliases it; there is nothing to copy
        dst, src = "this.%s" % f.name, "%s.%s" % (rhs, f.name)
        if "weave_deep" in f.attrs:
            return self._deep(dst, src, f.type, f)
        return "%s = %s;" % (dst, src)

    def _ne(self, a: str, b: str, t, deep: bool) -> str:
        """A condition that is true when ``a`` and ``b`` (of type ``t``) differ."""
        from ..frontend.types import TypeCat
        if t.cat == TypeCat.CLASS and deep:
            cmp = self._feature_method("compare")
            cls = self._handle_class(t)
            if cmp is not None and cls is not None and cls.find_method(cmp) is not None:
                return "(%s == null) != (%s == null) || (%s != null && !%s.%s(%s))" % (
                    a, b, a, a, cmp, b)
        return "%s %s %s" % (a, "!==" if _four_state_leaf(t) else "!=", b)

    def compare_field(self, f: SvField, rhs: str, result: str, on_mismatch: str = "") -> str:
        """Clears ``result`` if the field differs (only while ``result`` is still 1, so
        ``on_mismatch`` runs for the first difference only). (* weave_deep *) class
        handles, and arrays of them, compare through the binding's compare method."""
        from ..frontend.types import ArrayKind, TypeCat
        a, b = "this.%s" % f.name, "%s.%s" % (rhs, f.name)
        fail = "begin\n  %s = 0;%s\nend" % (result, ("\n  " + on_mismatch) if on_mismatch else "")
        t = f.type
        deep = "weave_deep" in f.attrs
        if t.cat == TypeCat.STRUCT and not t.packed:
            self._w.warning("%s.%s: unpacked structs cannot be compared; skipped"
                            % (f.owner.qname, f.name), f.loc)
            return ""
        if t.cat == TypeCat.EVENT:
            return ""
        if t.cat == TypeCat.ARRAY and t.elem is not None and t.elem.cat != TypeCat.ARRAY:
            i = self.fresh("i")
            elem_ne = self._ne("%s[%s]" % (a, i), "%s[%s]" % (b, i), t.elem, deep)
            if t.array_kind == ArrayKind.ASSOC:
                cond = "!%s.exists(%s) || %s" % (b, i, elem_ne)
            else:
                cond = elem_ne
            size = "" if t.array_kind == ArrayKind.FIXED else \
                "if (%s && %s.size() != %s.size()) %s\n" % (result, a, b, fail)
            return ("%sforeach (%s[%s]) begin\n  if (%s && (%s)) %s\nend"
                    % (size, a, i, result, cond, _indent(fail).lstrip()))
        if t.cat == TypeCat.ARRAY:
            # Arrays of arrays compare whole elements; deep handles inside are not followed.
            size = "" if t.array_kind == ArrayKind.FIXED else \
                "if (%s && %s.size() != %s.size()) %s\n" % (result, a, b, fail)
            return "%sif (%s && %s %s %s) %s" % (size, result, a,
                                                 "!==" if _four_state_leaf(t) else "!=", b, fail)
        cond = self._ne(a, b, t, deep)
        if " || " in cond:
            cond = "(%s)" % cond
        return "if (%s && %s) %s" % (result, cond, fail)

    def print_field(self, f: SvField, acc: str) -> str:
        """Appends ``"<name>: <value>\\n"`` to the string variable ``acc``."""
        from ..frontend.types import TypeCat
        t = f.type
        a = "this.%s" % f.name
        if t.cat == TypeCat.ENUM and t.nameable:
            val = '$sformatf("%%s", %s.name())' % a
        elif t.cat == TypeCat.INTEGRAL:
            val = '$sformatf("\'h%%0h", %s)' % a
        elif t.cat == TypeCat.STRING:
            val = '$sformatf("\\"%%s\\"", %s)' % a
        elif t.cat == TypeCat.REAL:
            val = '$sformatf("%%g", %s)' % a
        elif t.cat == TypeCat.CLASS:
            pm = self._feature_method("print")
            cls = self._handle_class(t)
            if "weave_deep" in f.attrs and pm and cls is not None and cls.find_method(pm):
                val = '(%s == null) ? "null" : {"{", %s.%s(), "}"}' % (a, a, pm)
            else:
                val = '(%s == null) ? "null" : "<object>"' % a
        elif t.cat == TypeCat.EVENT or t.cat == TypeCat.CHANDLE:
            return ""
        else:
            val = '$sformatf("%%p", %s)' % a
        return '%s = {%s, "%s: ", %s, "\\n"};' % (acc, acc, f.name, val)


def _indent(text: str, n: int = 2) -> str:
    return "\n".join((" " * n + l) if l else l for l in text.split("\n"))


def _has_class(t) -> bool:
    from ..frontend.types import TypeCat
    while t is not None:
        if t.cat == TypeCat.CLASS:
            return True
        t = t.elem
    return False


def _four_state_leaf(t) -> bool:
    while t is not None and t.elem is not None:
        t = t.elem
    return bool(t is not None and t.four_state)
