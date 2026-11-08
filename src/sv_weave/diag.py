"""Diagnostics shared by every stage.

A ``Diag`` carries a severity, a message and an optional source location. Stages
collect diagnostics; ``SvWeaveError`` stops a run and carries the ones that caused it.
"""
import dataclasses as dc
import enum
from typing import Iterable, List, Optional


class Severity(enum.IntEnum):
    NOTE = 0
    WARNING = 1
    ERROR = 2


@dc.dataclass(frozen=True)
class SrcLoc:
    file: str
    line: int
    col: int = 0

    def __str__(self):
        if self.col > 0:
            return "%s:%d:%d" % (self.file, self.line, self.col)
        return "%s:%d" % (self.file, self.line)


@dc.dataclass(frozen=True)
class Diag:
    severity: Severity
    msg: str
    loc: Optional[SrcLoc] = None
    code: str = ""

    def __str__(self):
        sev = self.severity.name.lower()
        code = " [%s]" % self.code if self.code else ""
        if self.loc is not None:
            return "%s: %s: %s%s" % (self.loc, sev, self.msg, code)
        return "%s: %s%s" % (sev, self.msg, code)


class SvWeaveError(Exception):
    """Stops a run. ``diags`` holds the diagnostics that caused it."""

    def __init__(self, diags: Iterable[Diag], summary: str = ""):
        self.diags: List[Diag] = list(diags)
        text = "\n".join(str(d) for d in self.diags)
        if summary:
            text = summary + ("\n" + text if text else "")
        super().__init__(text)


def error(msg: str, loc: Optional[SrcLoc] = None, code: str = "") -> SvWeaveError:
    return SvWeaveError([Diag(Severity.ERROR, msg, loc, code)])
