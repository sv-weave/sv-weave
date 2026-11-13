"""Jinja templates for weaver text: ``render(template, **ctx) -> SvText``.

A weaver may build its SV text from Jinja templates instead of Python strings.
sv-weave owns the environment (one per template directory, fixed settings) and the
origin of the text, so the line map of the woven code can name the template. Jinja
is an optional dependency (``sv-weave[templates]``), imported on the first render.

Templates hold loops, conditions and substitutions; anything computed belongs in
the Python objects passed as context. Environment settings: ``trim_blocks``,
``lstrip_blocks``, ``keep_trailing_newline``, ``StrictUndefined`` (a missing name is
an error, naming the template line), no autoescape.
"""
import inspect
import os
from typing import Any, Dict, Optional, Sequence, Tuple

from ..diag import Diag, Severity, SrcLoc, SvWeaveError
from .model import call_site

TEMPLATE_DIR = "templates"

_ENVS: Dict[Tuple[str, ...], Any] = {}


class SvText(str):
    """SV text rendered from a template. A ``str``, so anything that takes text takes
    it; it also carries where it came from. ``add_item``, ``add_file`` and the class
    item calls read that origin. Text derived from it (``+``, ``strip()``, ...) is a
    plain ``str`` again and gets the origin of its own call site.

    ``template``   path of the template file
    ``py_file``, ``py_line``   the Python call of ``render``
    """
    template: str
    py_file: str
    py_line: int

    def __new__(cls, text: str, template: str = "", py_file: str = "", py_line: int = 0):
        o = super().__new__(cls, text)
        o.template, o.py_file, o.py_line = template, py_file, py_line
        return o

    def __reduce__(self):
        return (SvText, (str(self), self.template, self.py_file, self.py_line))


def _jinja():
    try:
        import jinja2
    except ImportError:
        raise SvWeaveError([Diag(Severity.ERROR,
                                 "templates need jinja2: pip install 'sv-weave[templates]'")])
    return jinja2


def environment(dirs: Sequence[str]):
    """The Jinja environment for a template search path (cached per path)."""
    key = tuple(os.path.abspath(d) for d in dirs)
    env = _ENVS.get(key)
    if env is None:
        j = _jinja()
        env = j.Environment(loader=j.FileSystemLoader(list(key)),
                            trim_blocks=True, lstrip_blocks=True, keep_trailing_newline=True,
                            undefined=j.StrictUndefined, autoescape=False)
        _ENVS[key] = env
    return env


def template_dirs(plugin: Any) -> Tuple[str, ...]:
    """Where a weaver's templates are: its ``templates`` attribute (a directory or a
    list, relative to the module that defines its class), else ``templates/`` next to
    that module."""
    try:
        base = os.path.dirname(os.path.abspath(inspect.getfile(type(plugin))))
    except (TypeError, OSError):
        return ()
    spec = getattr(plugin, "templates", None) or TEMPLATE_DIR
    if isinstance(spec, str):
        spec = [spec]
    return tuple(os.path.join(base, d) for d in spec)


def render(template: str, dirs: Sequence[str] = (), _site: Optional[Tuple[str, int]] = None,
           **ctx) -> SvText:
    """Renders ``template`` (a name under ``dirs``) with ``ctx``. Without ``dirs``, the
    ``templates/`` directory next to the calling module."""
    site = _site or call_site()
    if not dirs:
        dirs = (os.path.join(os.path.dirname(site[0]), TEMPLATE_DIR),) if site[0] else ()
    j = _jinja()
    env = environment(dirs)
    t = None
    try:
        t = env.get_template(template)
        text = t.render(**ctx)
    except j.TemplateNotFound as e:
        raise SvWeaveError([Diag(Severity.ERROR, "template '%s' not found in %s"
                                 % (e.name, ", ".join(dirs) or "(no template directory)"),
                                 SrcLoc(*site) if site[0] else None)]) from e
    except j.TemplateError as e:
        raise SvWeaveError([Diag(Severity.ERROR, "%s (rendering %s, called at %s:%d)"
                                 % (e, template, site[0], site[1]),
                                 _template_loc(e, t.filename if t else None))]) from e
    return SvText(text, t.filename or template, site[0], site[1])


def _template_loc(e: BaseException, filename: Optional[str]) -> Optional[SrcLoc]:
    """The template line an error is at: a syntax error says; for a render-time error
    (an undefined name), the innermost traceback frame in the template."""
    if getattr(e, "lineno", None) and getattr(e, "filename", None):
        return SrcLoc(e.filename, e.lineno)
    loc, tb = None, e.__traceback__
    while tb is not None:
        if filename and tb.tb_frame.f_code.co_filename == filename:
            loc = SrcLoc(filename, tb.tb_lineno)
        tb = tb.tb_next
    return loc
