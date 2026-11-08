Glossary
========

.. glossary::

   target class
      A user class sv-weave generates a woven subclass for. See :doc:`concepts`.

   woven class
      The generated subclass of a target, ``Woven_<C>[_<hash>]__<profile>``, in the
      package ``<P>_woven``. The factory returns it in place of the target.

   binding
      A plugin for one class library or factory: its root classes, its features,
      and how woven classes are registered. See :doc:`authoring/bindings`.

   feature
      A named contribution point a binding defines, such as ``copy``, mapped to that
      library's hook method.

   weaver
      A plugin that contributes code to woven classes. See :doc:`authoring/weavers`.

   slot
      One method of a woven class, composed from several weavers' contributions:
      declarations, code before ``super``, code after it.

   extension set
      A named group of weavers, with safety flags that limit what its code may do.

   profile
      A named list of extension sets. Each built profile gets its own woven classes.
      See :doc:`user/profiles`.

   design handler
      A weaver handler registered with ``bus.on_design``; it sees the whole design
      and can add code about sets of classes.

   specialisation
      One parameterisation of a parameterised class, such as ``G#(16)``. Each one the
      design uses is a separate target, named with a short hash of its parameters.

   registration
      Adding woven classes to the runtime, in the generated ``__register()``
      functions, called through ``sv_weave_init()``.

   rand safety
      The rule that debug extension sets must not change randomisation, checked by
      Verify. See :doc:`authoring/verify-rules`.
