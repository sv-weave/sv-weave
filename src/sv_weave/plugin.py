"""Plugins: weavers and bindings (design §10).

Plugins are found through the entry-point groups ``sv_weave.weavers`` and
``sv_weave.bindings``. Tests and scripts can also register classes in-process with
``register_weaver`` / ``register_binding``; an in-process registration wins over an
entry point of the same name.

Each plugin declares the contribution-API range it works with (``api``, for example
``">=0.1,<0.2"``). A plugin whose range excludes ``API_VERSION`` is refused at load time.
"""
import dataclasses as dc
import re
from importlib.metadata import entry_points
from typing import Any, Dict, List, Optional, Sequence, Tuple, Type

from .api_version import API_VERSION
from .diag import error

WEAVER_GROUP = "sv_weave.weavers"
BINDING_GROUP = "sv_weave.bindings"


class Weaver:
    """Base class for weavers. Subclasses set ``name`` and implement ``subscribe``.

    ``order`` is the default dispatch order (lower runs first, so its ``pre`` code is
    outermost and its ``post`` code runs last); a config entry's ``order`` overrides it.
    ``before`` / ``after`` name other weavers (or bindings) whose content this weaver's
    content must precede / follow, in every method section it contributes to; a config
    entry's ``before`` / ``after`` add to them."""
    name: str = ""
    api: str = ">=0.1,<0.2"
    version: str = "0"
    order: int = 0
    before: Sequence[str] = ()
    after: Sequence[str] = ()

    def __init__(self, options: Optional[Dict[str, Any]] = None):
        self.options: Dict[str, Any] = dict(options or {})

    def subscribe(self, bus) -> None:
        raise NotImplementedError


@dc.dataclass(frozen=True)
class FeatureSpec:
    """A named contribution point a binding defines (design §2), and the method it
    becomes in the woven class.

    ``args`` are full SV argument declarations; ``arg_names`` the names passed on to
    ``super``. ``rhs`` names the argument a weaver reads from (for copy/compare), if any.
    ``ret`` is the return type for a function, None for void or a task.
    ``super_policy`` is ``call`` (call ``super`` first) or ``skip``.
    """
    name: str
    method: str
    args: Tuple[str, ...] = ()
    arg_names: Tuple[str, ...] = ()
    ret: Optional[str] = None
    task: bool = False
    rhs: Optional[str] = None
    super_policy: str = "call"


class Binding:
    """Base class for bindings: one class library or factory (design §2, §8.3)."""
    name: str = ""
    api: str = ">=0.1,<0.2"
    version: str = "0"
    roots: Sequence[str] = ()

    def __init__(self, options: Optional[Dict[str, Any]] = None):
        self.options: Dict[str, Any] = dict(options or {})

    def features(self) -> Dict[str, FeatureSpec]:
        return {}

    def create_expr(self, cls, inst: str = "") -> Optional[str]:
        """An SV expression that creates a new object of ``cls`` (an SvClass) through
        this binding's factory, ``inst`` being an SV string expression for the instance
        path (may be empty). None means plain ``new()``."""
        return None

    def miscompare_stmt(self, cls, field: str) -> str:
        """SV statement reporting the first field that differs in a compare; "" for none."""
        return ""

    def preamble(self) -> List[str]:
        """Lines before ``package`` in each woven file, e.g. an ``include`` of the
        library's macros."""
        return []

    def imports(self) -> List[str]:
        """Packages the woven package imports, besides sv_weave_pkg and the user package."""
        return []

    def sv_runtime_files(self) -> List[str]:
        return []

    def prepare(self, w) -> None:
        """Runs before any weaver for each (target, profile)."""

    def finalize(self, w) -> None:
        """Runs after every weaver for each (target, profile)."""

    def package_items(self, wpkg, cfg) -> List[str]:
        """Adds package-level items (such as creator classes) to a finished woven
        package, and returns the SV statements that register them. sv-weave puts the
        statements of every binding into the package's ``__register()``."""
        return []

    def init_files(self, woven_pkgs, cfg) -> Dict[str, str]:
        """Extra generated files, as {file name: text}, e.g. the init package."""
        return {}


# -- version ranges ---------------------------------------------------------------

_CMP = re.compile(r"^\s*(>=|<=|==|>|<)\s*(\d+(?:\.\d+)*)\s*$")


def _ver(text: str) -> Tuple[int, ...]:
    return tuple(int(x) for x in text.split("."))


def _pad(a: Tuple[int, ...], b: Tuple[int, ...]):
    n = max(len(a), len(b))
    return a + (0,) * (n - len(a)), b + (0,) * (n - len(b))


def api_compatible(spec: str, version: Tuple[int, ...] = API_VERSION) -> bool:
    """True if ``version`` satisfies a range such as ``">=0.1,<0.2"``."""
    for part in spec.split(","):
        m = _CMP.match(part)
        if m is None:
            raise ValueError("bad API range '%s'" % spec)
        op, v = m.group(1), _ver(m.group(2))
        a, b = _pad(tuple(version), v)
        ok = {">=": a >= b, "<=": a <= b, "==": a == b, ">": a > b, "<": a < b}[op]
        if not ok:
            return False
    return True


def check_api(kind: str, cls: type) -> None:
    spec = getattr(cls, "api", "")
    try:
        ok = api_compatible(spec)
    except ValueError:
        raise error("%s '%s' declares an invalid API range '%s'" % (kind, cls.name, spec))
    if not ok:
        raise error("%s '%s' needs sv-weave API %s, but this sv-weave provides %s"
                    % (kind, cls.name, spec, ".".join(str(x) for x in API_VERSION)))


# -- registry ---------------------------------------------------------------------

_local: Dict[str, Dict[str, type]] = {WEAVER_GROUP: {}, BINDING_GROUP: {}}


def register_weaver(cls: Type[Weaver]) -> Type[Weaver]:
    """Registers a weaver class in-process. Usable as a decorator."""
    _local[WEAVER_GROUP][cls.name] = cls
    return cls


def register_binding(cls: Type[Binding]) -> Type[Binding]:
    _local[BINDING_GROUP][cls.name] = cls
    return cls


def unregister(name: str) -> None:
    for g in _local.values():
        g.pop(name, None)


def _builtin(group: str) -> Dict[str, type]:
    if group == BINDING_GROUP:
        from .bindings import BUILTIN
    else:
        from .weavers import BUILTIN
    return {c.name: c for c in BUILTIN}


def available(group: str) -> Dict[str, type]:
    """Every plugin class of a group: built-in, then entry points, then in-process."""
    out = dict(_builtin(group))
    for ep in entry_points(group=group):
        out.setdefault(ep.name, ep)
    out.update(_local[group])
    return out


def _import_ref(kind: str, ref: str, search: Sequence[str]) -> type:
    """``module:Class``, imported with ``search`` directories on sys.path."""
    import importlib
    import sys
    mod_name, _, attr = ref.partition(":")
    added = [d for d in search if d not in sys.path]
    sys.path[:0] = added
    try:
        mod = importlib.import_module(mod_name)
        return getattr(mod, attr)
    except (ImportError, AttributeError) as e:
        raise error("cannot load %s '%s': %s" % (kind, ref, e))
    finally:
        for d in added:
            sys.path.remove(d)


def find(group: str, name: str, search: Sequence[str] = ()) -> type:
    """A plugin class by name, or by ``module:Class`` reference (``search`` lists
    extra directories to import from, such as the config file's directory)."""
    kind = "weaver" if group == WEAVER_GROUP else "binding"
    if ":" in name:
        obj = _import_ref(kind, name, search)
        base = Weaver if group == WEAVER_GROUP else Binding
        if not (isinstance(obj, type) and issubclass(obj, base)):
            raise error("%s '%s' is not a %s subclass" % (kind, name, base.__name__))
        check_api(kind, obj)
        return obj
    avail = available(group)
    if name not in avail:
        raise error("unknown %s '%s' (available: %s)" % (kind, name, ", ".join(sorted(avail)) or "none"))
    obj = avail[name]
    if not isinstance(obj, type):
        try:
            obj = obj.load()
        except Exception as e:
            raise error("cannot load %s '%s' from entry point: %s" % (kind, name, e))
    base = Weaver if group == WEAVER_GROUP else Binding
    if not (isinstance(obj, type) and issubclass(obj, base)):
        raise error("%s '%s' is not a %s subclass" % (kind, name, base.__name__))
    check_api(kind, obj)
    return obj
