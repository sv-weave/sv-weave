Extension sets and profiles
===========================

Weavers are grouped into **extension sets**; a **profile** is a list of sets. Each
built profile gets its own woven classes, so a debug profile can add checks that a
release build never contains.

.. code-block:: yaml

    sv-weave:
      extension-sets:
        core: {}
        debug.xcheck: {}
      weavers:
      - {name: copy}                          # set: core
      - {name: xcheck, set: debug.xcheck}
      profiles:
        release: [core]
        debug: [core, "debug.*"]
      build-profiles: [release, debug]
      default-profile: release

A weaver runs for a profile only if the profile includes the weaver's set. When a
class comes out the same in two profiles (no weaver of the extra sets applies to it),
one woven class is emitted and registered for both. Classes are named after the first
profile that produced them, so ``Woven_A__release`` may serve ``debug`` too.

Compile-time selection
----------------------

``build-profiles: [release]`` generates only the release classes: a release build
contains no debug code at all. Asking for an unbuilt profile at run time falls back to
the config's default profile.

Run-time selection
------------------

With several profiles built, which woven class the factory hands out is chosen through
the binding, with the library's own factory:

- the UVM example installs a ``uvm_default_factory`` subclass that, after UVM's own
  override resolution, hands out the woven class for the profile named by
  ``+weave_profile=<p>`` (default: the config's default profile);
- the example reference library chooses per type and instance path
  (``+weave_profile``, ``+weave_impl=<profile>:<type_glob>[@<inst_glob>]``,
  ``ref_profiles::select(...)``), see :doc:`../examples`.

Rand safety
-----------

Debug code must not change what a test does. Sets other than ``core`` may not, by
default, randomise, add properties, allocate or fork; Verify rejects such code (see
:doc:`../authoring/verify-rules`). The test suite checks that the same seed gives the
same randomised values in release and in debug.

The ``xcheck`` weaver
---------------------

A built-in debug weaver: it reports X/Z values in four-state fields after
``randomize()`` (rand fields) and after ``copy`` (all copied fields). Options:
``on_x: error | warning | fatal``. ``(* weave_noxcheck *)`` skips a field. It passes the
rand-safety rules with every flag off.
