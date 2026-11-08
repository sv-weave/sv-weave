Outputs and report
==================

``sv-weave gen`` writes these files to ``out_dir``:

``<P>_woven.sv``
    One package per user package with woven classes.
``sv_weave_rt.f``
    SV the binding needs ahead of your sources, if any. Compile it first.
``sv_weave.f``
    The generated sources, in compile order. Compile them after your own sources.
``weave-manifest.json``
    Machine-readable: every target, its woven class per profile, the contributing
    weavers, specialisation hashes, input and output hashes, and diagnostics.
``weave-report.md``
    The manifest as Markdown. ``sv-weave report weave-manifest.json`` prints the same.

Output is deterministic, and a file whose content has not changed is not rewritten, so
simulator builds that depend on it stay up to date. A woven file that a previous run
wrote but this run no longer produces is removed.

Woven class names
-----------------

A woven class is named ``Woven_<C>__<profile>``. A specialisation of a parameterised
class gets a short hash of its parameters: ``Woven_G_6addb__release``. The report's
*Specialisations* table maps each hash back to the parameter values.

Diagnostics
-----------

Diagnostics point at a source location: the user's SV for problems in the design (such
as overriding a method that is not virtual), and the weaver's Python for problems in
what a weaver asked for.
