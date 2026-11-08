Example libraries and bindings
==============================

sv-weave ships no SV runtime and no binding. It works *with* a class library: the
library's base class defines virtual methods that woven subclasses implement, and the
library's factory decides which class gets created. A binding describes one library
to sv-weave. These examples, under ``examples/`` in the repository, show how.

``examples/reflib``: a minimal reference library
-------------------------------------------------

``reflib_pkg.sv`` is the smallest library sv-weave can work with, and the one the
quickstart and the test suite use:

- ``ref_object``: the base class, with virtual hooks ``copy(rhs)``,
  ``compare(rhs)``, ``sprint()`` and ``ref_impl_name()``;
- ``ref_factory#(T)::create(inst)``: a factory with user overrides
  (``set_override(ref_override_to#(T, O)::get())``);
- profile selection at run time: ``+weave_profile=<p>``,
  ``+weave_impl=<profile>:<type_glob>[@<inst_glob>][,...]``,
  ``ref_profiles::select(...)``, and ``+weave_report`` to trace every resolution.

``reflib_binding.py`` maps the features onto those hooks and registers each woven
class with ``ref_factory`` for its profiles. Use it with:

.. code-block:: yaml

    sv-weave:
      binding: "reflib_binding:ReflibBinding"
      plugin-path: [path/to/examples/reflib]

``examples/uvm``: UVM
---------------------

``uvm_binding.py`` shows a binding for UVM. The real one belongs in the separate
``sv-weave-uvm`` library.

- Features map onto ``uvm_object``'s own hooks: ``copy`` → ``do_copy``,
  ``compare`` → ``do_compare``, ``print`` → ``convert2string``. UVM's ``copy()`` and
  ``compare()`` reach the woven code as usual.
- Each woven class gets `` `uvm_object_utils `` (or `` `uvm_component_utils ``) and
  is registered with ``sv_weave_uvm_factory`` (``sv_weave_uvm_pkg.sv``), a
  ``uvm_default_factory`` subclass the generated code installs. It overrides
  ``find_override_by_type`` / ``find_override_by_name``: UVM first resolves the
  requested type through the user's type and instance overrides, then the factory
  substitutes the woven class of the *resolved* type for the profile chosen with
  ``+weave_profile`` (default: the config's default profile). The result does not
  depend on the order in which overrides and woven classes are registered, which
  plain ``set_type_override`` calls would. Compile ``sv_weave_uvm_pkg.sv`` after UVM
  and before the design.
- Field weavers stop at the library boundary, so UVM's own fields are not copied
  or printed.

The test ``tests/sim/test_uvm_example.py`` runs it on Verilator's bundled UVM.

``examples/selector``: a design-wide weaver
-------------------------------------------

A weaver that registers every concrete subclass of a base so that a testbench can
count them and create one at random. It is the worked example of ``bus.on_design``.
Random selection is testbench-library policy, so it is an example here; a real
version belongs in a UVM utility library, built on ``uvm_factory``.
