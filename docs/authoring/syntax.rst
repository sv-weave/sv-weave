Generating classes the sources name
===================================

A normal weaver works on the elaborated design, so every class the sources name must
already exist. Some weavers generate a class that the user's code itself names, most
often a base class:

.. code-block:: systemverilog

    (* my_attr = "ref_object" *)
    class foo #(int W = 4) extends foo_base #(W);
      ...
    endclass

``foo_base`` does not exist until the weaver writes it, so the design cannot be
elaborated first. The *syntax pre-pass* solves this: before elaboration, a weaver sees
the parsed sources, where attributes and class headers are already visible, and adds
source text. That text is parsed and elaborated together with the user's sources.

Subscribing
-----------

Call ``bus.on_syntax(handler)`` from ``Weaver.subscribe``. The handler is called once
per run, with a ``SyntaxCtx``. Syntax handlers run before elaboration, ordered by the
weaver's ``order``, then by weaver name. A weaver may use ``on_syntax`` alongside
``on``; the class it adds is then an ordinary class in the woven design.

.. code-block:: python

    class BaseGen(plugin.Weaver):
        name = "base_gen"

        def subscribe(self, bus):
            bus.on_syntax(self.gen)

        def gen(self, s):
            lines = ["package foo_base_pkg;", "  import reflib_pkg::*;"]
            for c in s.classes("my_attr"):
                lines += ["  virtual class %s_base %s extends %s;"
                          % (c.name, c.params, c.attr_string("my_attr")),
                          "  endclass"]
            lines.append("endpackage")
            s.add_source("foo_base_pkg.sv", "\n".join(lines) + "\n")

``SyntaxCtx``
-------------

``s.classes(attr=None)``
    The class declarations of all sources, in source order, as ``SyntaxClass``
    objects. With ``attr``, only the classes that carry that attribute.
``s.add_source(name, text)``
    Adds a source file. ``name`` is a bare file name (letters, digits, ``_``, ``.``,
    ``-``). Adding the same name twice in a run is an error, even from two weavers.
``s.trees``, ``s.source_manager``
    The pyslang syntax trees and their source manager, for anything ``classes`` does
    not cover.
``s.weaver``, ``s.options``
    The weaver's name and its configured options.

``SyntaxClass``
---------------

``name``, ``package``, ``qname``
    The class name, its enclosing package ("" outside a package), and
    ``package::name``.
``attrs``
    Each ``(* name = value *)`` on the declaration, mapped to the value's text
    (``None`` for a bare ``(* name *)``). ``attr_string(name)`` gives the value with
    string quotes removed.
``params``
    The parameter port list as written (``#(int W = 4)``), or "".
``base``, ``base_args``
    The base class name and its parameter text (``#(W)``), both "" without
    ``extends``.
``loc``, ``node``
    The source location of the name, and the pyslang syntax node.

These are syntax only: nothing is resolved, so a parameter type or base name is the
text the user wrote.

Where the generated text goes
-----------------------------

The added sources are written to the output directory and listed, in order, in
``sv_weave_pre.f``; the manifest lists them under ``files.pre`` and ``RunResult``
under ``pre_files``. They are **not** part of the woven compile order
(``woven_files``), because they must be compiled *before* the user sources that name
what they declare, while the woven packages compile after them.

So put the generated classes in a package of their own (``foo_base_pkg`` above),
which the user's package imports. A compile then reads, in order: the bindings'
runtime files, ``sv_weave_pre.f``, the user's sources, the woven files. The generated
package may import packages that the user's sources do not depend on (``reflib_pkg``
above), but not the user's own package, which compiles after it.

The test ``tests/unit/test_syntax.py`` shows a complete weaver, with a design that
elaborates only once the generated base exists.
