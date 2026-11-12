"""Stage 1, Load: parse and elaborate SystemVerilog sources with pyslang.

All files are parsed as one compilation unit, the way Verilator and most simulators
treat a file list by default, so macros defined in one file are visible in later ones.
Any error-severity diagnostic stops the run.
"""
import dataclasses as dc
import os
from typing import Dict, List, Optional, Sequence, Tuple

import pyslang
from pyslang import ast as A
from pyslang import parsing as P
from pyslang import syntax as S

from ..diag import Diag, Severity, SrcLoc, SvWeaveError, error
from ..filelist import SourceSpec


@dc.dataclass
class Loaded:
    compilation: A.Compilation
    trees: List[S.SyntaxTree]
    source_manager: pyslang.SourceManager
    root: A.RootSymbol
    spec: SourceSpec
    warnings: List[Diag] = dc.field(default_factory=list)
    # The tree of spec.files (None without files), and the in-memory (name, tree) pairs.
    file_tree: Optional[S.SyntaxTree] = None
    text_trees: List[Tuple[str, S.SyntaxTree]] = dc.field(default_factory=list)
    bag: Optional[pyslang.Bag] = None

    def loc(self, sloc) -> Optional[SrcLoc]:
        return slang_loc(self.source_manager, sloc)


def slang_loc(sm: pyslang.SourceManager, sloc) -> Optional[SrcLoc]:
    if sloc is None:
        return None
    try:
        sloc = sm.getFullyOriginalLoc(sloc)
        name = sm.getFileName(sloc)
        if not name:
            return None
        return SrcLoc(name, sm.getLineNumber(sloc), sm.getColumnNumber(sloc))
    except Exception:
        return None


def _pp_bag(spec: SourceSpec) -> pyslang.Bag:
    pp = P.PreprocessorOptions()
    pp.predefines = [k if v is None else "%s=%s" % (k, v) for k, v in spec.defines.items()]
    opts = A.CompilationOptions()
    if spec.tops:
        opts.topModules = set(spec.tops)
    return pyslang.Bag([pp, opts])


def convert_diags(sm: pyslang.SourceManager, diags) -> List[Diag]:
    engine = pyslang.DiagnosticEngine(sm)
    out = []
    for d in diags:
        sev = Severity.ERROR if d.isError() else Severity.WARNING
        code = str(d.code)
        if code.startswith("DiagCode(") and code.endswith(")"):
            code = code[len("DiagCode("):-1]
        out.append(Diag(sev, engine.formatMessage(d), slang_loc(sm, d.location), code))
    return out


def load(spec: SourceSpec,
         texts: Sequence[Tuple[str, str]] = ()) -> Loaded:
    """Parse ``spec.files`` (plus in-memory ``(name, text)`` pairs, used by tests).

    Raises SvWeaveError with every error diagnostic if the design does not
    elaborate cleanly.
    """
    sm = pyslang.SourceManager()
    sm.setDisableProximatePaths(True)
    for d in spec.incdirs:
        sm.addUserDirectories(d)
    bag = _pp_bag(spec)
    trees = []
    missing = [f for f in spec.files if not os.path.isfile(f)]
    if missing:
        raise SvWeaveError([Diag(Severity.ERROR, "source file not found: %s" % f) for f in missing])
    file_tree = None
    if spec.files:
        file_tree = S.SyntaxTree.fromFiles(list(spec.files), sm, bag)
        trees.append(file_tree)
    text_trees = []
    for name, text in texts:
        t = S.SyntaxTree.fromText(text, sm, name, name, bag)
        trees.append(t)
        text_trees.append((name, t))
    if not trees:
        raise error("no SystemVerilog sources given")

    comp = A.Compilation(bag)
    for t in trees:
        comp.addSyntaxTree(t)
    root = comp.getRoot()
    diags = convert_diags(sm, comp.getAllDiagnostics())
    errs = [d for d in diags if d.severity == Severity.ERROR]
    if errs:
        raise SvWeaveError(errs, "the input design does not elaborate cleanly")
    return Loaded(comp, trees, sm, root, spec,
                  warnings=[d for d in diags if d.severity != Severity.ERROR],
                  file_tree=file_tree, text_trees=text_trees, bag=bag)


def load_text(*texts: str, name: str = "inline.sv", files: Sequence[str] = ()) -> Loaded:
    """Convenience for tests: load inline SV texts, after any ``files``."""
    pairs = [(name if len(texts) == 1 else "inline%d.sv" % i, t) for i, t in enumerate(texts)]
    return load(SourceSpec(files=list(files)), pairs)
