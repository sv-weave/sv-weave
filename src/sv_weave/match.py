"""Match predicates over ``SvClass`` (design §5.1).

Predicates compose with ``&``, ``|`` and ``~``. Each one also has a text form, so
config rules can use them::

    extends(uvm_sequence_item) & ~has_attr(weave_nocopy)

``str(pred)`` gives the canonical text, and ``parse(str(pred))`` gives back an
equivalent predicate.

Names may be qualified (``p::A``) or bare (``A``). A generic class name matches all
of its specialisations. Names containing characters outside ``[A-Za-z0-9_:*?.$]``
(for example a specialisation ``"p::G#(8, int)"``) are written in double quotes.
"""
import fnmatch
import re
from typing import Callable, List, Optional, Union

from .diag import error

FieldTest = Union[str, Callable]


class Pred:
    def __init__(self, fn: Callable, text: str):
        self._fn = fn
        self.text = text

    def __call__(self, cls) -> bool:
        return bool(self._fn(cls))

    def __and__(self, other: "Pred") -> "Pred":
        return Pred(lambda c: self(c) and other(c), "%s & %s" % (_wrap(self, "&"), _wrap(other, "&")))

    def __or__(self, other: "Pred") -> "Pred":
        return Pred(lambda c: self(c) or other(c), "%s | %s" % (_wrap(self, "|"), _wrap(other, "|")))

    def __invert__(self) -> "Pred":
        return Pred(lambda c: not self(c), "~%s" % _wrap(self, "~"))

    def __str__(self):
        return self.text

    def __repr__(self):
        return "Pred(%s)" % self.text


def _wrap(p: Pred, op: str) -> str:
    t = p.text
    depth = 0
    for i, ch in enumerate(t):
        if ch == '"':
            continue
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
        elif depth == 0 and ch in "&|":
            if op == "~" or ch != op:
                return "(%s)" % t
    return t


_BARE = re.compile(r"^[A-Za-z0-9_:*?.$]+$")


def _arg(s: str) -> str:
    return s if _BARE.match(s) else '"%s"' % s


def _glob(pattern: str, *names: str) -> bool:
    return any(fnmatch.fnmatchcase(n, pattern) for n in names if n)


# -- predicates ----------------------------------------------------------------

def any_class() -> Pred:
    return Pred(lambda c: True, "any()")


def extends_root() -> Pred:
    """Any class a binding claimed. Handlers only ever see targets, and every target
    derives from its binding's root, so this matches all of them."""
    return Pred(lambda c: True, "extends_root()")


def extends(name: str) -> Pred:
    """Derives from ``name``, directly or not. Does not match ``name`` itself."""
    return Pred(lambda c: any(_name_hit(a, name) for a in c.ancestors()),
                "extends(%s)" % _arg(name))


def is_a(name: str) -> Pred:
    """``name`` itself, or a class derived from it."""
    return Pred(lambda c: c.is_a(name), "is_a(%s)" % _arg(name))


def implements(name: str) -> Pred:
    return Pred(lambda c: c.implements_iface(name), "implements(%s)" % _arg(name))


def named(pattern: str) -> Pred:
    """Class name glob, matched against the bare and the qualified name (and, for a
    specialisation, the generic class's names)."""
    def fn(c):
        names = [c.name, c.qname]
        if c.generic is not None:
            names.append(c.generic.qname)
        return _glob(pattern, *names)
    return Pred(fn, "named(%s)" % _arg(pattern))


def in_package(pattern: str) -> Pred:
    return Pred(lambda c: c.package is not None and _glob(pattern, c.package),
                "in_package(%s)" % _arg(pattern))


def has_attr(name: str) -> Pred:
    return Pred(lambda c: name in c.attrs, "has_attr(%s)" % _arg(name))


def has_method(name: str, virtual: Optional[bool] = None) -> Pred:
    """The class declares or inherits a method ``name`` (glob)."""
    def fn(c):
        for k in [c] + c.ancestors():
            for m in k.methods:
                if _glob(name, m.name) and (virtual is None or m.virtual == virtual):
                    return True
        return False
    text = "has_method(%s%s)" % (_arg(name), "" if virtual is None else
                                 ", virtual=%s" % ("true" if virtual else "false"))
    return Pred(fn, text)


def has_field(test: FieldTest = "*", **flags) -> Pred:
    """The class has a field (own or inherited) matching ``test``: a name glob or a
    callable ``f(SvField) -> bool``. Keyword filters: ``rand``, ``static``, ``attr``."""
    def ok(f) -> bool:
        if callable(test):
            if not test(f):
                return False
        elif not _glob(test, f.name):
            return False
        if "rand" in flags and (f.rand.value != "none") != bool(flags["rand"]):
            return False
        if "static" in flags and f.static != bool(flags["static"]):
            return False
        if "attr" in flags and flags["attr"] not in f.attrs:
            return False
        return True

    if callable(test):
        text = "has_field(<fn>)"
    else:
        parts = [_arg(test)] + ["%s=%s" % (k, _flag_text(v)) for k, v in sorted(flags.items())]
        text = "has_field(%s)" % ", ".join(parts)
    return Pred(lambda c: any(ok(f) for f in c.all_fields()), text)


def is_abstract() -> Pred:
    return Pred(lambda c: c.is_abstract, "is_abstract()")


def _flag_text(v) -> str:
    if isinstance(v, bool):
        return "true" if v else "false"
    return _arg(str(v))


def _name_hit(c, name: str) -> bool:
    from .frontend.model import _name_matches
    return _name_matches(c, name)


# -- text form ---------------------------------------------------------------------

_FUNCS = {
    "any": (any_class, 0, 0),
    "extends_root": (extends_root, 0, 0),
    "extends": (extends, 1, 1),
    "is_a": (is_a, 1, 1),
    "implements": (implements, 1, 1),
    "named": (named, 1, 1),
    "in_package": (in_package, 1, 1),
    "has_attr": (has_attr, 1, 1),
    "has_method": (has_method, 1, 1),
    "has_field": (has_field, 0, 1),
    "is_abstract": (is_abstract, 0, 0),
}

_TOKEN = re.compile(r'\s*(?:(?P<str>"[^"]*")|(?P<word>[A-Za-z0-9_:*?.$]+)|(?P<op>[&|~(),=]))')


class _Parser:
    def __init__(self, text: str, where: str):
        self.text = text
        self.where = where
        self.toks: List[tuple] = []
        pos = 0
        text = text.rstrip()
        while pos < len(text):
            m = _TOKEN.match(text, pos)
            if m is None or m.end() == pos:
                self.fail("unexpected character '%s'" % text[pos:].lstrip()[:1], pos)
            kind = m.lastgroup
            val = m.group(kind)
            if kind == "str":
                val = val[1:-1]
            self.toks.append((kind, val, m.start(kind)))
            pos = m.end()
        self.i = 0

    def fail(self, msg, pos=None):
        if pos is None:
            pos = self.toks[self.i][2] if self.i < len(self.toks) else len(self.text)
        raise error("bad match expression%s: %s at column %d: '%s'"
                    % (" (%s)" % self.where if self.where else "", msg, pos + 1, self.text))

    def peek(self, val=None):
        if self.i >= len(self.toks):
            return None
        t = self.toks[self.i]
        if val is not None and not (t[0] == "op" and t[1] == val):
            return None
        return t

    def take(self, val):
        if not self.peek(val):
            self.fail("expected '%s'" % val)
        self.i += 1

    def parse(self) -> Pred:
        p = self.or_()
        if self.i != len(self.toks):
            self.fail("unexpected '%s'" % self.toks[self.i][1])
        return p

    def or_(self):
        p = self.and_()
        while self.peek("|"):
            self.i += 1
            p = p | self.and_()
        return p

    def and_(self):
        p = self.unary()
        while self.peek("&"):
            self.i += 1
            p = p & self.unary()
        return p

    def unary(self):
        if self.peek("~"):
            self.i += 1
            return ~self.unary()
        if self.peek("("):
            self.i += 1
            p = self.or_()
            self.take(")")
            return p
        return self.call()

    def value(self):
        t = self.peek()
        if t is None or t[0] == "op":
            self.fail("expected a name")
        self.i += 1
        return t[1], t[0]

    def call(self):
        t = self.peek()
        if t is None or t[0] != "word":
            self.fail("expected a predicate")
        name = t[1]
        if name not in _FUNCS:
            self.fail("unknown predicate '%s' (known: %s)" % (name, ", ".join(sorted(_FUNCS))))
        self.i += 1
        fn, nmin, nmax = _FUNCS[name]
        self.take("(")
        args, kwargs = [], {}
        while not self.peek(")"):
            if self.peek() is None:
                self.fail("expected ')'")
            if args or kwargs:
                self.take(",")
            val, kind = self.value()
            if self.peek("="):
                self.i += 1
                v, vkind = self.value()
                if vkind == "word" and v in ("true", "false"):
                    v = v == "true"
                kwargs[val] = v
            else:
                args.append(val)
        self.take(")")
        if not (nmin <= len(args) <= nmax):
            self.fail("%s() takes %s argument%s" % (
                name, nmin if nmin == nmax else "%d-%d" % (nmin, nmax), "" if nmax == 1 else "s"))
        try:
            return fn(*args, **kwargs)
        except TypeError as e:
            self.fail("%s(): %s" % (name, e))


def parse(text: str, where: str = "") -> Pred:
    """Parse a match expression. ``where`` names the config location, for errors."""
    if not text or not text.strip():
        raise error("empty match expression" + (" (%s)" % where if where else ""))
    return _Parser(text, where).parse()
