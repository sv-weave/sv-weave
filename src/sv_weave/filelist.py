"""Filelist (``-f``) expansion.

Supported:
- source files, one or more per line;
- ``-f <file>`` / ``-F <file>``: nested filelists. Paths in the nested file are
  resolved relative to that file's directory (both forms, which is what most users
  expect; ``-f`` relative-to-cwd semantics are not reproduced);
- ``+incdir+<dir>[+<dir>...]`` and ``-I<dir>`` / ``-I <dir>``;
- ``+define+<NAME>[=<val>][+...]`` and ``-D<NAME>[=<val>]``;
- ``//`` and ``#`` comments, and ``$VAR`` / ``${VAR}`` environment references.

Anything else that starts with ``-`` or ``+`` is an error, reported at its file and line.
"""
import dataclasses as dc
import os
import re
import shlex
from typing import Dict, List, Optional, Set

from .diag import SrcLoc, error

_ENV_RE = re.compile(r"\$\{(\w+)\}|\$(\w+)")


@dc.dataclass
class SourceSpec:
    """Sources plus preprocessor settings, in compile order."""
    files: List[str] = dc.field(default_factory=list)
    incdirs: List[str] = dc.field(default_factory=list)
    defines: Dict[str, Optional[str]] = dc.field(default_factory=dict)
    # Top modules to elaborate. Empty: slang's default, every uninstantiated
    # module. Set it when the sources hold a module that cannot elaborate on
    # its own (e.g. a default `type` parameter that is not a class).
    tops: List[str] = dc.field(default_factory=list)

    def extend(self, other: "SourceSpec"):
        for f in other.files:
            if f not in self.files:
                self.files.append(f)
        for d in other.incdirs:
            if d not in self.incdirs:
                self.incdirs.append(d)
        self.defines.update(other.defines)
        for t in other.tops:
            if t not in self.tops:
                self.tops.append(t)


def _expand_env(tok: str, loc: SrcLoc) -> str:
    def sub(m):
        name = m.group(1) or m.group(2)
        if name not in os.environ:
            raise error("environment variable '%s' is not set" % name, loc)
        return os.environ[name]
    return _ENV_RE.sub(sub, tok)


def _split_define(text: str):
    if "=" in text:
        name, val = text.split("=", 1)
        return name, val
    return text, None


def read_filelist(path: str, _active: Optional[Set[str]] = None) -> SourceSpec:
    path = os.path.abspath(path)
    active = set() if _active is None else _active
    if path in active:
        raise error("filelist includes itself: %s" % path)
    if not os.path.isfile(path):
        raise error("filelist not found: %s" % path)
    active.add(path)
    base = os.path.dirname(path)
    spec = SourceSpec()

    def resolve(p):
        return p if os.path.isabs(p) else os.path.normpath(os.path.join(base, p))

    with open(path) as fp:
        lines = fp.read().splitlines()

    for lineno, raw in enumerate(lines, 1):
        loc = SrcLoc(path, lineno)
        line = raw.split("//", 1)[0]
        if line.lstrip().startswith("#"):
            continue
        try:
            toks = shlex.split(line, comments=False)
        except ValueError as e:
            raise error("cannot parse filelist line: %s" % e, loc)
        i = 0
        while i < len(toks):
            tok = _expand_env(toks[i], loc)
            if tok in ("-f", "-F"):
                if i + 1 >= len(toks):
                    raise error("%s needs a file argument" % tok, loc)
                spec.extend(read_filelist(resolve(_expand_env(toks[i + 1], loc)), active))
                i += 2
                continue
            if tok == "-I":
                if i + 1 >= len(toks):
                    raise error("-I needs a directory argument", loc)
                spec.incdirs.append(resolve(_expand_env(toks[i + 1], loc)))
                i += 2
                continue
            if tok.startswith("+incdir+"):
                spec.incdirs.extend(resolve(d) for d in tok[len("+incdir+"):].split("+") if d)
            elif tok.startswith("-I"):
                spec.incdirs.append(resolve(tok[2:]))
            elif tok.startswith("+define+"):
                for d in tok[len("+define+"):].split("+"):
                    if d:
                        name, val = _split_define(d)
                        spec.defines[name] = val
            elif tok.startswith("-D"):
                name, val = _split_define(tok[2:])
                spec.defines[name] = val
            elif tok.startswith("-") or tok.startswith("+"):
                raise error("unsupported filelist option '%s'" % tok, loc)
            else:
                f = resolve(tok)
                if f not in spec.files:
                    spec.files.append(f)
            i += 1
    active.discard(path)
    return spec
