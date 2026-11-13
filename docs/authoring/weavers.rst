Writing weavers
===============

A weaver is a Python class that subscribes to classes and contributes SV code to their
woven subclasses. Weavers write SV text; sv-weave handles the structure around it:
method skeletons, ordering, names, indentation and where each line came from.

A minimal weaver
----------------

.. code-block:: python

    from sv_weave import plugin
    from sv_weave.match import has_method

    class TraceBuild(plugin.Weaver):
        name = "trace-build"
        api = ">=0.2,<0.3"

        def subscribe(self, bus):
            bus.on(has_method("build"), self.weave)

        def weave(self, w):
            slot = w.override("build")
            slot.pre.add('$display("enter build: %s");' % w.cls.name)
            slot.post.add('$display("leave build");')

Register it under the ``sv_weave.weavers`` entry point and list it in
``sv-weave.yaml``:

.. code-block:: toml

    [project.entry-points."sv_weave.weavers"]
    trace-build = "my_pkg.weavers:TraceBuild"

.. code-block:: yaml

    sv-weave:
      weavers:
      - name: trace-build
        set: core

``api`` is the range of the sv-weave contribution API the weaver works with. sv-weave
refuses to load a weaver whose range excludes its own API version.

A run's input hash, which decides whether ``svweave.Weave`` is up to date, covers each
weaver's ``version`` and its source: every ``.py`` file of the weaver's top-level
package (or its one module), read from disk. A weaver whose output depends on other
code or on data files overrides the classmethod ``fingerprint()`` to return a digest
of them (bindings likewise).

The bus
-------

``bus.on(pred, handler)`` calls ``handler(w)`` for every target class that ``pred``
matches. Predicates are the ones described in :doc:`../concepts`. The config entry's
``match`` narrows a subscription further, and ``options`` reach the weaver as
``self.options``.

Handlers run in a fixed order, so output is the same on every run:

1. the binding's ``prepare``;
2. weavers, by config ``order`` (default 0), then by weaver name;
3. the binding's ``finalize``.

A handler runs once per target and profile, and only for profiles that include the
weaver's extension set.

The weave context
-----------------

``w`` gives the handler:

``w.fields()``
    The fields a field weaver handles: those of the class and its ancestors in the
    user's packages, root-most first. The library's own fields are left out.
``w.cls``
    The target class (``SvClass``): ``name``, ``qname``, ``fields``, ``methods``,
    ``ancestors()``, ``all_fields(upto=...)``, ``find_method(name)``, ``attrs``.
``w.binding``, ``w.binding_root``
    The binding that claimed the class, and the root class it derives from.
``w.profile``, ``w.ext_set``, ``w.options``
    The profile being woven, the weaver's extension set, its config options.
``w.model``
    The whole class model, for design-wide queries.
``w.feature(name)``
    The method slot for a binding feature, such as ``copy``. It is an error if the
    binding has no such feature.
``w.override(method)``
    A method slot overriding a method of the target or an ancestor. The signature is
    copied from that method, with argument directions and defaults.
``w.add_method(name, ret=None, args=(), task=False)``
    A new method in the woven class.
``w.add_field(decl)``
    A new non-rand property. The extension set must allow state.
``w.add_item(text)``
    Any other class item.
``w.warning(msg, loc)``, ``w.error(msg, loc)``
    Diagnostics. With ``strict: true`` in the config, warnings become errors.

The declaration as written
--------------------------

The model gives resolved types. A weaver that copies code from the user's class
(a method prototype, a typedef, a parameter list) needs the text as the user wrote
it instead: ``cls.decl`` (on ``SvClass`` and ``SvGenericClass``; a specialisation
gives its generic class's declaration) is an ``SvDecl``, built on first use from
the class's syntax. Import the types from ``sv_weave.api``.

``decl.name``, ``decl.is_interface``, ``decl.is_virtual``, ``decl.attrs``
    The class name, ``interface class`` or ``virtual class``, and its attributes.
``decl.header``, ``decl.param_names``, ``decl.params_ref``
    The parameter port list as written (``""`` for none), the parameter names, and
    ``#(P, T)`` passing them straight through.
``decl.extends``, ``decl.implements``
    The base class and interface classes as written.
``decl.typedefs``, ``decl.typedef(name)``
    ``SvDeclTypedef``: ``name``, ``type``, the whole ``text``, ``attrs``; for a
    packed struct or union, ``struct_kind`` and ``members`` (``SvDeclMember``:
    ``name``, ``type``, ``attrs``).
``decl.methods``, ``decl.method(name)``
    ``SvDeclMethod``: ``name``, ``kind`` (``function``/``task``), ``ret``, ``args``
    (``SvDeclArg``: ``name``, ``dir``, ``type``, ``dims``, ``default``,
    ``declare()``), ``qualifiers``, ``attrs``, ``inputs``, ``outputs`` and
    ``prototype(name=None)``.
``decl.properties``
    ``SvDeclProperty``: ``name``, ``type``, ``attrs``, ``qualifiers``.

Text is rebuilt from the tokens, so comments in the declaration are left out.

Method slots
------------

Every woven method is a slot that several weavers can contribute to. It is rendered
as::

    virtual function <ret> <name>(<args>);
      <decl>          declarations, in contributor order
      <pre>           contributor order
      super.<name>(<args>);
      <post>          reverse contributor order
      return <result>;
    endfunction : <name>

- ``slot.decl``, ``slot.pre``, ``slot.post`` (also ``slot.body``) each take
  ``.add(text)``. Text is dedented and re-indented, so a triple-quoted block can be
  indented however is convenient.
- ``post`` runs in reverse contributor order, so two weavers nest like wrappers.
- ``add(text, first=False, before=(), after=())`` controls placement within the
  section (also ``append(text)`` and ``prepend(text)``, which is ``first=True``):

  - ``first=True`` puts the text ahead of every appended text in that section;
  - ``before=["other"]`` / ``after=["other"]`` put it textually before / after
    everything the named weaver (or binding) contributed to that section.

  A weaver can declare the same relationships for all its content with the class
  attributes ``before`` and ``after``, and a user can add them in the config entry
  (``before: [xcheck]``), so two weavers from different authors can be ordered
  without changing either. Relationships always mean text order in the section,
  including ``post``. Contradictory relationships are reported as an error.
- For a function with a return value, super's result is in ``slot.ret_var``.
  ``slot.set_result(expr)`` returns something else.
- ``slot.replace_super()`` drops the ``super`` call. Only one contributor may do so.
- The ``super`` call is also left out when the base method is pure virtual.

The method being overridden must be virtual. If it is not, sv-weave stops with an error
at the user's declaration of the method.

SV helpers
----------

``w.sv`` holds helpers that produce SV fragments:

``w.sv.fresh(name)``
    A local name, ``__w_<name>``, that collides with no member of the class or its
    ancestors.
``w.sv.cast_rhs(slot)``
    Declares a handle of the target's type, casts the slot's ``rhs`` argument into it
    (``$fatal`` on mismatch) and returns the handle's name.
``w.sv.type_of(field)``
    The field's type, spelled so that it is valid inside the woven class.
``w.sv.accessible(field)``
    False for ``local`` fields, which no subclass can reach, with a warning.
``w.sv.copy_field(f, rhs)``, ``w.sv.compare_field(f, rhs, result, on_mismatch)``, ``w.sv.print_field(f, acc)``
    The statements for one field, chosen by the field's type category, with
    ``weave_deep`` handled. Third-party weavers reuse these instead of re-deriving
    the type rules.

Worked example: ``copy``
------------------------

The built-in ``copy`` weaver, in full:

.. code-block:: python

    class CopyWeaver(Weaver):
        name = "copy"

        def subscribe(self, bus):
            bus.on(extends_root() & ~has_attr("weave_nocopy"), self.weave)

        def weave(self, w):
            slot = w.feature("copy")          # the binding's copy method
            rhs = w.sv.cast_rhs(slot)         # typed handle to the argument
            for f in w.fields():               # user fields, up to the library
                if f.static or f.const or "weave_nocopy" in f.attrs:
                    continue
                if not w.sv.accessible(f):    # local: warn and skip
                    continue
                text = w.sv.copy_field(f, rhs)
                if text:
                    slot.body.add(text)

It never names a library method: the binding maps the ``copy`` feature to
``do_copy`` for UVM and to ``copy`` for the example reference library.

Inheritance
-----------

Each woven class covers every user field from the target up to the library boundary:
``w.fields()``. A woven ``B`` does not derive from a woven
``A``, so ``Woven_B`` must handle ``A``'s fields itself.

Design-wide weavers
-------------------

Some code is about a *set* of classes, such as a selector that picks among every
concrete subclass of a base. ``bus.on_design(handler)`` runs ``handler(d)`` once per
profile, after every per-class handler and before the bindings' ``finalize``.

.. code-block:: python

    def subscribe(self, bus):
        bus.on_design(self.design)

    def design(self, d):
        base = d.model.find_class("eth_pkg::pkt")
        for sub in d.model.subclasses_of(base, concrete=True):
            d.add_item(base.package, "// code about %s" % sub.qname,
                       imports=[sub.package])

``d.model``
    The whole class model. Queries: ``classes(pred)``, ``subclasses_of(T,
    concrete=True, transitive=True)``, ``implementors_of(I)``, ``packages()``,
    ``find_class(name)``, ``generic(name)``. Results include specialisations and are
    not filtered by target selection.
``d.feature_of(T, name)``, ``d.override_of(T, method)``
    Slots of ``T``'s woven class, exactly as in a per-class handler. ``T`` must be a
    target (when any design handler is configured, every class a binding claims is
    one).
``d.add_item(pkg, text, imports=(), uses_woven=())``, ``d.add_class(...)``
    Package-level code in ``<pkg>_woven``. The woven package already imports ``pkg``
    and every package ``pkg`` wildcard-imports; ``imports`` lists further user packages
    the code needs. ``uses_woven`` lists user packages whose *woven* package it references; if
    that makes woven packages import each other in a cycle, the code moves to
    ``sv_weave_gen_pkg``, which compiles after all of them. Identical text added for
    several profiles is kept once.
``d.add_registration(pkg, stmt)``
    A statement for ``<pkg>_woven``'s ``__register()``.
``d.add_file(name, text)``
    A whole generated file, for code that is not package-level (a module, an
    interface). ``name`` is a plain file name ending in ``.sv``, ``.svh`` or ``.v``.
    The file is written next to the woven packages, listed in ``sv_weave.f`` after
    them and after the init files (so it may import any woven package), and
    verified with them; its diagnostics point back at the weaver. The same name added
    again with the same text is kept once; with different text, or a name sv-weave
    generates itself, it is an error.
``d.binding_of(cls)``
    The binding whose root ``cls`` derives from; ``binding.create_expr(cls, inst)``
    gives an expression that creates it through that binding's factory.

Templates
---------

A weaver whose text is mostly literal SV can keep it in Jinja templates instead of
Python strings. ``d.render(template, **ctx)`` (and ``w.render(...)`` in a per-class
handler) renders a template of the weaver and returns its text:

.. code-block:: python

    class MyWeaver(Weaver):
        name = "my"
        # templates = "templates"     # the default: <dir of this module>/templates

        def design(self, d):
            for b in bundles(d.model):
                d.add_file("%s_xtor.sv" % b.name, d.render("xtor.sv.j2", b=BundleView(b)))

.. code-block:: jinja

    // {{ b.name }}: the pins of one link
    module {{ b.name }}_xtor (
    {% for p in b.ports %}
        {{ p }}
    {% endfor %}
    );
    endmodule

Install the extra: ``pip install 'sv-weave[templates]'`` (Jinja 3.1; it is imported on
the first ``render``). sv-weave owns the environment, one per template directory:

- ``trim_blocks`` and ``lstrip_blocks``: a line holding only a block tag
  (``{% for %}``, ``{% if %}``) leaves nothing in the output; indent tags freely.
- ``keep_trailing_newline``.
- ``StrictUndefined``: a name or attribute the context lacks is an error that names
  the template line, not an empty string.
- No autoescape: ``<`` and ``&`` are SV, not HTML.

The templates are found in ``templates/`` next to the module that defines the
weaver class, or in the directories its ``templates`` attribute names (a string or a
list, relative to that module). Ship them as package data. Template files ending in
``.j2`` or ``.jinja`` count towards the weaver's source fingerprint, so editing one
re-runs the weave.

``render`` returns an ``SvText``: a ``str`` that also records the template file and
the Python call of ``render``. ``add_item``, ``add_file``, ``add_field``,
``w.add_item`` and slot code (``slot.body.add(...)``) read it, so the line map of the
woven code, and so every diagnostic verify reports in it, names the template line
(and, in brackets, the ``render`` call): ``xtor.sv.j2:12: error: expected ';' [woven
code .../my_xtor.sv:80, from my[core] at xtor.sv.j2:12 (rendered at
my_weaver.py:41)]``. Static template text maps to its own line; a line produced
inside a ``{% for %}`` maps to the line of the loop body that produced it. Text derived from an ``SvText`` (``+``,
``.strip()``, ``"\n".join(...)``) is a plain ``str`` again and maps to the Python call
that adds it.

Keep templates to loops, conditions and substitutions. Build lists, joins and
expressions in Python, in a small view object passed as context, and write
``{{ v.conns|join(", ") }}`` rather than ``{% for %}`` with ``loop.last`` on one line.

The worked example is ``examples/selector/``: a weaver that makes the concrete
subclasses of a base selectable at random. It is an example, not a built-in: sv-weave
keeps no type registry of its own, and works with the class library's (for UVM,
``uvm_factory``).
