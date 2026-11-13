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
from typing import Any, Dict, List, Optional, Sequence, Tuple

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
    ``tlines``     the template line of each line of the text (``text.split("\n")``),
                   or () when unknown (the whole text then maps to line 1)
    """
    template: str
    py_file: str
    py_line: int
    tlines: Tuple[int, ...]

    def __new__(cls, text: str, template: str = "", py_file: str = "", py_line: int = 0,
                tlines: Sequence[int] = ()):
        o = super().__new__(cls, text)
        o.template, o.py_file, o.py_line = template, py_file, py_line
        o.tlines = tuple(tlines)
        return o

    def __reduce__(self):
        return (SvText, (str(self), self.template, self.py_file, self.py_line, self.tlines))


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
        text, tlines = _render_mapped(t, ctx)
    except j.TemplateNotFound as e:
        raise SvWeaveError([Diag(Severity.ERROR, "template '%s' not found in %s"
                                 % (e.name, ", ".join(dirs) or "(no template directory)"),
                                 SrcLoc(*site) if site[0] else None)]) from e
    except j.TemplateError as e:
        raise SvWeaveError([Diag(Severity.ERROR, "%s (rendering %s, called at %s:%d)"
                                 % (e, template, site[0], site[1]),
                                 _template_loc(e, t.filename if t else None))]) from e
    return SvText(text, t.filename or template, site[0], site[1], tlines)


def _render_mapped(t, ctx) -> Tuple[str, Tuple[int, ...]]:
    """The text ``t.render(**ctx)`` gives, and the template line of each of its lines.

    Drives the template's render generator. After each chunk, the innermost generator's
    current Python line gives the chunk's template line: through the template's debug
    info for an expression, and for static text (which Jinja yields with no line
    marker of its own) the line of the template text it is, found between the markers
    around that Python line. A line of output takes the line of the chunk its first
    character comes from, plus the newlines before it in that chunk, so static text
    maps exactly and a line built by a loop maps to the loop body's line. Uses Jinja
    internals (``root_render_func``, ``new_context``, ``debug_info``; jinja2 3.1); if
    they fail, the plain render with no line map."""
    try:
        gen = t.root_render_func(t.new_context(dict(ctx)))
        dbg, data = _line_info(t)
    except Exception:
        return t.render(**ctx), ()
    chunks: List[Tuple[str, int]] = []
    try:
        for chunk in gen:
            g = gen
            while getattr(getattr(g, "gi_yieldfrom", None), "gi_frame", None) is not None:
                g = g.gi_yieldfrom
            ln = 0
            if g.gi_frame is not None and g.gi_code.co_filename == gen.gi_code.co_filename:
                ln = _chunk_line(chunk, g.gi_frame.f_lineno, dbg, data)
            chunks.append((chunk, ln))
    except Exception:
        t.environment.handle_exception()        # re-raises, as render() would
    text = "".join(c for c, _ in chunks)
    if any(ln <= 0 for _, ln in chunks):
        return text, ()
    return text, tuple(_line_map(chunks))


def _line_info(t):
    """The template's (code line, template line) markers, sorted, and the (line, text)
    of every piece of static text in it; kept on the template, which the environment
    caches (and reloads when its file changes)."""
    info = getattr(t, "_sv_weave_lines", None)
    if info is None:
        env = t.environment
        src = env.loader.get_source(env, t.name)[0]
        nodes = _jinja().nodes
        data = [(n.lineno, n.data) for n in env.parse(src, t.name, t.filename).find_all(
            nodes.TemplateData)]
        info = (sorted((code, tpl) for tpl, code in t.debug_info), data)
        t._sv_weave_lines = info
    return info


def _chunk_line(chunk: str, pyline: int, dbg, data) -> int:
    """The template line of a chunk yielded at ``pyline`` of the compiled template."""
    lo, hi = 0, None
    for code, tpl in dbg:
        if code <= pyline:
            lo = tpl
        else:
            hi = tpl
            break
    # Static text: a piece of template text between the marker before and after it,
    # the chunk itself, else the longest that starts it (Jinja joins adjacent
    # constants into one chunk).
    near = [(ln, d) for ln, d in data if d and ln >= lo and (hi is None or ln <= hi)]
    for ln, d in near:
        if chunk == d:
            return ln
    best = max((d for _, d in near if chunk.startswith(d)), key=len, default=None)
    if best is not None:
        return next(ln for ln, d in near if d == best)
    return lo


def _line_map(chunks: Sequence[Tuple[str, int]]) -> List[int]:
    lines: List[int] = []
    cur: Optional[int] = None
    last = 1
    for chunk, ln in chunks:
        for i, piece in enumerate(chunk.split("\n")):
            if i > 0:                           # a newline ends the current line
                lines.append(cur if cur is not None else ln + i - 1)
                cur = None
            if piece and cur is None:
                cur = ln + i
        last = ln + chunk.count("\n")
    lines.append(cur if cur is not None else last)
    return lines


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
