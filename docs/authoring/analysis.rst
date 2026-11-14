Read/write analysis
===================

A weaver that schedules or checks code needs to know what a method touches.
``sv_weave.analysis.rw`` walks a method's bound body and returns the members it reads
and writes. The results are conservative: a member the method might write is
reported as written.

On the model
------------

``SvMethod`` gives the analysis of its own body, computed on first use and cached:

``m.rw``
    An ``RwSets`` with ``reads``, ``writes`` and ``opaque``, each a frozen set of
    member paths.
``m.reads``, ``m.writes``
    Shorthand for ``m.rw.reads`` and ``m.rw.writes``.
``m.stmt_rw``
    A list with one ``RwSets`` per top-level statement of the body (sequential
    ``begin``/``end`` blocks are flattened), or ``None`` if the body declares a
    local, which can carry a value from one statement to another. Use it for
    per-output dependences: in ``x = a; y = b;``, ``x`` depends on ``a`` only.

Member paths
------------

A path is relative to ``this``: a field name followed by ``.member`` and
``[<const>]`` steps (``in.valid``, ``q.skid_valid``, ``arr[2].a``). A path covers
everything below it.

- A static property is named by its lexical path (``p::C::count``).
- A whole-struct read or write expands to every field, recursively: ``out.data`` of
  a struct type gives ``out.data.a`` and ``out.data.b``.
- A variable index covers the whole array: ``arr[i]`` gives ``arr``.
- Locals and arguments are not members and are not reported.

The conservative rules
----------------------

- A field written on any path counts as written. Both branches of every ``if`` are
  walked, so an ``if`` on a constant parameter gives a superset.
- Calls to methods of the same class and to static functions are followed
  transitively, with cycle detection.
- A call through a member handle (``in.get_valid()``) is followed with the handle's
  path as prefix. The static target is used; virtual dispatch is not resolved, so a
  weaver that relies on an override must check for one.
- A call that cannot be followed (a pure virtual or interface-class method, or a
  method of a handle that is not a member path, such as ``port.t.x()``) is
  reported in ``opaque`` as ``<receiver path>.<method>``. A weaver must treat an
  opaque call as touching anything.

Stopping at a boundary
----------------------

The functions take a pyslang ``SubroutineSymbol`` (``m.slang``) and an optional
callee summary:

.. code-block:: python

    from sv_weave.analysis.rw import RwSets, analyze, analyze_stmts

    def summary(callee):
        if callee.name == "get":
            return RwSets(frozenset({"@value"}), frozenset(), frozenset())
        return None          # follow the call as usual

    rw = analyze(m.slang, summary)
    per_stmt = analyze_stmts(m.slang, summary)

``summary(callee)`` is asked before a callee is followed. A returned ``RwSets``
stands for the callee's body and is prefixed with the receiver path like a followed
call; ``None`` follows the callee. Use it to stop at a library class whose effects
the weaver knows by other means, for example a port accessor tagged with an
attribute. ``m.rw`` and ``m.stmt_rw`` use no summary.

The pyslang AST lives only as long as its compilation: keep the model alive while
analysing.
