dv-flow tasks
=============

The ``svweave`` package is registered with dv-flow-mgr when sv-weave is installed.

``svweave.Runtime``
-------------------

Outputs a ``systemVerilogSource`` FileSet with the SV each listed binding needs ahead
of the design, if any. sv-weave ships no SV runtime; the class library (for example
``hdlsim.vlt.SimLibUVM``) comes from the design's own flow.

.. list-table::
   :header-rows: 1

   * - Parameter
     - Default
     - Meaning
   * - ``binding``
     - ``[]``
     - Bindings (names or ``module:Class``).

``svweave.Weave``
-----------------

Runs the sv-weave pipeline over the upstream ``systemVerilogSource`` and
``verilogSource`` FileSets, in order (their include directories and defines too).
Outputs the upstream FileSets, then a ``systemVerilogSource`` FileSet of the generated
sources (woven packages, then ``sv_weave_init_pkg.sv`` and ``sv_weave_init_m.sv``),
then a ``jsonManifest`` FileSet holding ``weave-manifest.json``.

.. list-table::
   :header-rows: 1

   * - Parameter
     - Default
     - Meaning
   * - ``config``
     - none
     - ``sv-weave.yaml``, relative to the flow's directory. Without it, the defaults
       apply, which name no binding, so it fails.
   * - ``profiles``
     - config's ``build-profiles``
     - Profiles to generate.
   * - ``binding``
     - config's ``binding``
     - Bindings to use.
   * - ``verify``
     - config's ``verify``
     - Verification level: ``full``, ``syntax`` or ``off``.
   * - ``top``
     - none
     - Top modules to elaborate, added to the config's ``sources.top``.

Diagnostics become task markers at their source locations. When the generated output
is unchanged from the previous run, the task reports ``changed=False`` and rewrites no
file, so downstream builds stay up to date.

The task is skipped as up to date only when, besides dv-flow's own checks (parameters,
upstream FileSets, outputs present), the run's input hash still holds. That hash covers
the content of the ``config`` file and the source of every weaver and binding the
config names, and of sv-weave itself, so editing a weaver re-weaves even when its
``version`` is unchanged.

Registration
------------

Woven classes are registered with the library's factory by the generated
``sv_weave_init()``. The design runs it in one of three ways:

- instantiate ``sv_weave_init_m`` (as in the quickstart), or add it as an extra top: it
  registers from a static initialiser, before any ``initial`` block;
- call ``sv_weave_init_pkg::sv_weave_init()`` before the first object is created;
- set ``registration: static`` in the config. Each woven package then registers
  itself from a static initialiser of its own. This works on Verilator; see the design
  note ``docs/design/notes/registration-trigger.md`` for other simulators.

The design may refer to ``sv_weave_init_m`` and ``sv_weave_init_pkg`` before anything
has been generated: sv-weave supplies a stand-in for them while it reads the design.

With UVM, a typical flow is ``hdlsim.vlt.SimLibUVM`` → ``svweave.Weave`` (with the
design's FileSets) → ``hdlsim.vlt.SimImage``.
