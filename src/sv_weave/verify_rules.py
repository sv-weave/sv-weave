"""Rand-safety rules (design §6.6), run on the syntax tree of the woven code.

Each hit is attributed, through the render line map, to the fragment that produced
it. Fragments from an extension set whose flag is off are rejected. Framework and
binding code (no extension set) is exempt, and so is ``core`` unless its config
turns a flag off.

The rules are keyword- and call-level:
- ``allow_rand``: ``rand``/``randc``, ``constraint``, calls to ``randomize``,
  ``srandom``, ``set_randstate``, and the random system functions;
- ``allow_state``: class property declarations;
- ``allow_alloc``: ``new``, and calls to a method named ``create``;
- ``allow_threads``: ``fork``.
"""
from typing import List, Optional, Tuple

from pyslang import parsing as P
from pyslang import syntax as S

from .diag import Diag, Severity, SrcLoc

TK = P.TokenKind

RAND_CALLS = {"randomize", "srandom", "set_randstate"}
RAND_SYSTEM = {"$urandom", "$urandom_range", "$random", "$dist_uniform", "$dist_normal",
               "$dist_exponential", "$dist_poisson", "$dist_chi_square", "$dist_t",
               "$dist_erlang"}


def _hits(tree) -> List[Tuple[str, str, int]]:
    """(flag, what, line) for every rule hit in the tree."""
    sm = tree.sourceManager
    toks: List = []
    hits: List[Tuple[str, str, int]] = []

    main = sm.getFileName(tree.root.getFirstToken().location)

    def line(loc) -> int:
        """Line in the woven file; tokens from a macro expansion count at the line
        where the macro is used. 0 for anything outside the woven file."""
        if sm.isMacroLoc(loc):
            loc = sm.getFullyExpandedLoc(loc)
        if sm.getFileName(loc) != main:
            return 0
        return sm.getLineNumber(loc)

    def cb(node):
        if isinstance(node, P.Token):
            toks.append(node)
        elif node.kind == S.SyntaxKind.ClassPropertyDeclaration:
            hits.append(("allow_state", "a class property", line(node.getFirstToken().location)))

    tree.root.visit(cb)
    for i, t in enumerate(toks):
        k = t.kind
        nxt = toks[i + 1] if i + 1 < len(toks) else None
        is_call = nxt is not None and nxt.kind == TK.OpenParenthesis
        if k in (TK.RandKeyword, TK.RandCKeyword):
            hits.append(("allow_rand", "'%s'" % t.valueText, line(t.location)))
        elif k == TK.ConstraintKeyword:
            hits.append(("allow_rand", "a constraint", line(t.location)))
        elif k == TK.Identifier and t.valueText in RAND_CALLS and is_call:
            hits.append(("allow_rand", "a call to %s()" % t.valueText, line(t.location)))
        elif k == TK.SystemIdentifier and t.valueText in RAND_SYSTEM:
            hits.append(("allow_rand", "a call to %s" % t.valueText, line(t.location)))
        elif k == TK.NewKeyword:
            hits.append(("allow_alloc", "'new'", line(t.location)))
        elif k == TK.Identifier and t.valueText == "create" and is_call:
            hits.append(("allow_alloc", "a call to create()", line(t.location)))
        elif k == TK.ForkKeyword:
            hits.append(("allow_threads", "'fork'", line(t.location)))
    return hits


def check_rules(tree, rendered, cfg, woven_path: str) -> List[Diag]:
    diags = []
    seen = set()
    for flag, what, ln in _hits(tree):
        if ln == 0:
            continue
        origin = rendered.origin_at(ln)
        if origin is None or origin.ext_set is None:
            continue
        es = cfg.extension_sets.get(origin.ext_set)
        if es is None or getattr(es, flag):
            continue
        key = (flag, what, ln)
        if key in seen:
            continue
        seen.add(key)
        loc = SrcLoc(origin.file, origin.line) if origin.file else SrcLoc(woven_path, ln)
        diags.append(Diag(
            Severity.ERROR,
            "rand-safety: %s from %s is not allowed in extension set '%s' (%s is off) "
            "[woven code %s:%d]" % (what, origin.contributor, origin.ext_set, flag,
                                    woven_path, ln),
            loc, "rand-safety"))
    return diags
