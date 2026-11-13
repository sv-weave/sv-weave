Writing bindings
================

A binding adapts sv-weave to one class library or factory. It says which classes it
claims, what its features look like, and how woven classes get registered. Weavers
never depend on a binding directly; they contribute to its features.

.. code-block:: python

    from sv_weave import plugin

    class MyBinding(plugin.Binding):
        name = "mylib"
        api = ">=0.3,<0.4"
        roots = ("my_pkg::my_object",)

        def imports(self): return ["my_pkg"]

        def features(self):
            return {
                "copy": plugin.FeatureSpec(
                    "copy", "do_copy", args=("my_object rhs",), arg_names=("rhs",),
                    rhs="rhs"),
            }

        def finalize(self, w): ...
        def package_items(self, wpkg, cfg): ...
        def sv_runtime_files(self): return []

Register it under the ``sv_weave.bindings`` entry point and select it with
``binding:`` in ``sv-weave.yaml``.

What a binding provides
-----------------------

``roots``
    Qualified names of root classes. Every class derived from one of them is a
    candidate target. A class that two bindings claim is an error.
``features()``
    ``FeatureSpec`` objects: the hook method each feature becomes (``method``), its
    arguments (full declarations plus the names passed to ``super``), its return
    type, the argument weavers read from (``rhs``) and ``super_policy`` (``call`` or
    ``skip``). The root class should declare each hook method ``virtual``.
``prepare(w)`` / ``finalize(w)``
    Run before and after the weavers for each target and profile, with the same
    ``WeaveCtx`` weavers get. ``finalize`` runs only if some weaver contributed.
``package_items(wpkg, cfg)``
    Adds package-level items to a finished woven package: typically the creator
    classes and ``__register()``. Each woven package must define ``__register()``;
    the generated ``sv_weave_init()`` calls it.
``imports()``
    Packages the woven package imports, besides the user package and the packages
    the user package wildcard-imports (UVM: ``uvm_pkg``).
``preamble()``
    Lines before ``package`` in each woven file (UVM: the ``uvm_macros.svh`` include).
``create_expr(cls, inst)``
    An expression creating ``cls`` through the library's factory, used for deep copies.
``sv_runtime_files()``
    SV the binding needs ahead of the design, if any (listed in ``sv_weave_rt.f`` and
    output by ``svweave.Runtime``). Usually none: the library comes from the
    design's own flow.

Examples
--------

sv-weave has no built-in binding: a binding belongs with the library it adapts (the
UVM one in the separate ``sv-weave-uvm`` package). Two examples are in the repository,
described in :doc:`../examples`:

- ``examples/reflib/reflib_binding.py``: a minimal library and its binding;
- ``examples/uvm/uvm_binding.py``: UVM. Features map onto ``do_copy``,
  ``do_compare`` and ``convert2string``; a ``uvm_default_factory`` subclass hands out
  the woven class of the type UVM's own overrides resolve to.

``package_items`` returns the binding's registration statements; sv-weave places them
in each woven package's ``__register()``, which ``sv_weave_init()`` calls. The design
runs that by instantiating ``sv_weave_init_m`` or by calling it.
