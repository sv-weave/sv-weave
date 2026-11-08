Concepts
========

Target classes
--------------

A **target class** is a user class that sv-weave generates a woven subclass for. A
class is a target when all of these hold:

1. Its package is selected by ``packages.include`` and ``packages.exclude`` in
   ``sv-weave.yaml``. Library and generated packages (``std``, ``uvm_pkg``,
   ``*_woven``) are never selected.
2. Exactly one binding claims it: the class derives from one of that binding's root
   classes, such as ``uvm_pkg::uvm_object`` for UVM.
3. It is not marked ``(* weave_off *)``.
4. At least one weaver applies to it.

Interface classes, and classes declared outside a package, are never targets.
Abstract classes can be targets. ``sv-weave list --classes`` shows every class with the
reason it is or is not a target.

Weavers, bindings and features
------------------------------

A **weaver** contributes code to woven classes: it is written once and works with any
class library. A **binding** describes one class library or factory: its root classes,
its hook methods and how woven classes are registered.

A **feature** is a named contribution point that a binding defines, such as ``copy``.
Each binding maps it to its library's own hook method. Weavers contribute to the feature,
never to a library's method by name, so a ``copy`` weaver works with every binding.

Extension sets and profiles
---------------------------

Weavers belong to **extension sets**, such as ``core`` or ``debug.xcheck``. A **profile**
is a named list of sets, such as ``release = [core]`` or ``debug = [core, debug.*]``.
Each profile that is built gets its own woven classes, and the profile is chosen at
compile time (build only one) or at run time (plusargs). Sets other than ``core`` are
restricted by default so that debug code cannot change randomisation. See
:doc:`user/profiles`.

Parameterised classes
---------------------

Each specialisation of a parameterised class that the design uses, such as
``G#(16)``, is a separate class to sv-weave and gets its own woven subclass. sv-weave
finds a specialisation wherever the design uses it: in declarations, typedefs,
``extends`` clauses, other specialisations' parameters and expressions such as
``G#(9)::create()``.

A specialisation that the design never names gets no woven subclass. If a factory
creates one at runtime, the factory returns the unwoven class.

Match expressions
-----------------

Config rules choose classes with match expressions. Predicates combine with ``&``
(and), ``|`` (or), ``~`` (not) and parentheses::

    extends(uvm_sequence_item) & ~has_attr(weave_nocopy)

.. list-table::
   :header-rows: 1
   :widths: 35 65

   * - Predicate
     - Matches a class that
   * - ``extends(N)``
     - derives from ``N``, directly or not (``N`` itself does not match)
   * - ``is_a(N)``
     - is ``N`` or derives from it
   * - ``implements(I)``
     - implements interface class ``I``, directly or through a base class
   * - ``named(GLOB)``
     - has a bare or qualified name matching ``GLOB``
   * - ``in_package(GLOB)``
     - is declared in a package matching ``GLOB``
   * - ``has_attr(A)``
     - carries the attribute ``(* A *)``
   * - ``has_method(GLOB[, virtual=true|false])``
     - declares or inherits a matching method
   * - ``has_field([GLOB][, rand=..., static=..., attr=A])``
     - has a matching field, its own or inherited
   * - ``is_abstract()``
     - is abstract (``virtual class``)
   * - ``any()``
     - always matches

Names can be qualified (``eth_pkg::pkt``) or bare (``pkt``). The name of a
parameterised class matches every specialisation of it. Write a name that contains
other characters in double quotes, for example ``is_a("p::G#(8, int)")``.
