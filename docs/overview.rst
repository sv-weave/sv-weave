Overview
========

What weaving is
---------------

You write plain SystemVerilog classes against plain base classes. Nothing in your code
refers to generated code. sv-weave reads your sources and, for each user package ``P``,
generates:

- a package ``P_woven`` holding one generated subclass per selected class, named
  ``Woven_<C>__<profile>``;
- the registrations that make the factory return the woven subclass whenever your code
  asks the factory for ``C``.

The woven subclass adds the code that plugins contribute, for example a ``copy``
method that walks every field up to the library's root class.

The factory precondition
------------------------

Weaving works only for objects that are created through a factory. An object created
with a plain ``new()`` is never woven, because nothing can substitute its type.

Plugins
-------

Two kinds of plugin decide what gets generated:

**Weavers**
    Decide *what* code to contribute, such as copy, compare, print or a debug check.
    A weaver is written once and works with any class library.

**Bindings**
    Decide *how* one class library or factory expects that code: which base classes
    are roots, which hook methods exist (for example ``do_copy`` in UVM), and how
    woven classes are registered.

Extension sets and profiles
---------------------------

Weavers are grouped into named **extension sets** such as ``core`` or
``debug.xcheck``. A **profile** is a named list of sets, such as ``release`` or
``debug``. You choose a profile when you build, or at runtime with a plusarg.

Pipeline
--------

One run of sv-weave goes through these stages:

1. **Load:** parse and elaborate the sources with pyslang.
2. **Model:** build a class model of packages, classes, fields and methods.
3. **Select:** choose the target classes.
4. **Weave:** plugins contribute code to one woven class per target and profile.
5. **Check:** model-level checks, such as overriding only virtual methods.
6. **Render:** turn the woven model into SystemVerilog text.
7. **Verify:** re-elaborate the user sources together with the woven code using
   pyslang. This stage is configurable.
8. **Write:** write the woven packages, the init file, a file list, a manifest and a
   report.

Where to go next
----------------

- :doc:`quickstart`: an example from source to simulation.
- :doc:`concepts`: targets, bindings, features, profiles and match expressions.
- :doc:`user/config` and :doc:`user/attributes`: configuring what gets woven.
- :doc:`authoring/weavers`: writing your own weavers.
- :doc:`glossary`.

The design documents, decisions and measurements live in the repository, under
``docs/design/`` (``initial-design.md`` and the notes in ``notes/``), and the
implementation plan with its status under ``docs/plan/``.
