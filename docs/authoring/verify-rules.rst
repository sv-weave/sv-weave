Verification and rand safety
============================

Before writing anything, sv-weave checks the code it generated. How much it checks is
set by ``verify:`` in ``sv-weave.yaml`` or ``--verify`` on the command line.

.. list-table::
   :header-rows: 1
   :widths: 15 85

   * - Level
     - What runs
   * - ``full`` (default)
     - The design is elaborated again with the woven code, by pyslang. Every error in
       generated code is reported at the weaver call that produced the line, with the
       generated file and line in the message. Then the rand-safety rules, and two
       structural checks: every woven override really overrides a virtual method, and
       every registered woven class is concrete.
   * - ``syntax``
     - The generated files are parsed on their own, then the rand-safety rules run.
       Catches syntax errors and rule violations, not undeclared names or type errors.
   * - ``off``
     - Nothing.

When verification fails, nothing in ``out_dir`` changes; the generated files go to
``out_dir/.failed/`` for inspection. A ``full`` pass is recorded in the manifest
together with the input and output hashes, and the next run with the same hashes
skips verification. On a UVM testbench ``full`` costs well under a second.

Rand safety
-----------

Debug code must not change what a test does. In particular it must not consume random
numbers, or a seed that reproduced a failure in a release build would not reproduce it
in a debug build. Each extension set therefore carries four flags. They default to on
for the set named ``core`` and off for every other set:

.. list-table::
   :header-rows: 1
   :widths: 20 80

   * - Flag
     - Allows, in code from weavers of the set
   * - ``allow_rand``
     - ``rand``/``randc``, ``constraint``, calls to ``randomize()``, ``srandom()``,
       ``set_randstate()``, ``$urandom``, ``$urandom_range``, ``$random`` and the
       ``$dist_*`` functions
   * - ``allow_state``
     - class property declarations
   * - ``allow_alloc``
     - ``new`` and calls to a method named ``create``
   * - ``allow_threads``
     - ``fork``

.. code-block:: yaml

    extension-sets:
      core: {}
      debug.xcheck: {}                  # all flags off
      debug.trace: {allow_alloc: true}

The rules look at the generated code itself, whatever produced it, and attribute each
hit through the line map to the weaver and extension set of that line. Code the
framework and bindings generate is exempt. The rules are keyword- and call-level: a
fragment that calls a user function which itself calls ``randomize()`` is not caught.
