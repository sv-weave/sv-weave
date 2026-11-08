sv-weave
========

sv-weave generates subclasses of your SystemVerilog classes and arranges for the
factory to hand them out instead of the originals. Copy, compare and print methods,
debug checks and similar boilerplate are generated once, by plugins, rather than
written by hand in every class.

.. toctree::
   :maxdepth: 2
   :caption: Contents

   overview
   quickstart
   examples
   concepts

.. toctree::
   :maxdepth: 2
   :caption: User guide

   user/config
   user/profiles
   user/attributes
   user/cli
   user/dvflow
   user/report

.. toctree::
   :maxdepth: 2
   :caption: Extending sv-weave

   authoring/weavers
   authoring/bindings
   authoring/verify-rules

.. toctree::
   :maxdepth: 2
   :caption: Reference

   reference/config-schema
   reference/dvflow-tasks
   glossary
