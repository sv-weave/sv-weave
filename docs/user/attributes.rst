Attributes and built-in weavers
===============================

Built-in weavers
----------------

.. list-table::
   :header-rows: 1
   :widths: 18 82

   * - Weaver
     - What it generates
   * - ``copy``
     - The binding's ``copy`` feature: copies every field of the class and its
       ancestors, up to the binding root.
   * - ``compare``
     - The binding's ``compare`` feature: compares every field; the first difference
       clears the result and is reported through the binding's hook (the UVM example
       reports it with ``uvm_report_info`` at ``UVM_HIGH``).
   * - ``print``
     - The binding's ``print`` feature: one ``name: value`` line per field.


.. code-block:: yaml

    weavers:
    - {name: copy}
    - {name: compare}
    - {name: print}

The field weavers handle the fields of the class and its ancestors in the user's
packages; the library's own fields (for UVM, those of ``uvm_sequence_item`` and above)
are left to the library. They skip static and ``const`` fields, and ``local`` fields of any class,
which a subclass cannot reach (a warning, or an error with ``strict: true``). A woven
class's code runs after ``super``, so a hand-written ``copy`` in a parent still runs;
fields it also copies are simply copied twice.

Attributes
----------

Attributes go on a class or a field, in the SV attribute syntax:

.. code-block:: systemverilog

    (* weave_nocopy *) class scratchpad extends uvm_object; ... endclass

    class packet extends uvm_sequence_item;
      (* weave_deep *)   payload body;
      (* weave_nocopy *) int     n_sent;    // bookkeeping, not data
    endclass

.. list-table::
   :header-rows: 1
   :widths: 22 12 66

   * - Attribute
     - On
     - Effect
   * - ``weave_off``
     - class
     - The class is not woven at all.
   * - ``weave_nocopy``
     - class, field
     - Skipped by ``copy``.
   * - ``weave_nocompare``
     - class, field
     - Skipped by ``compare``.
   * - ``weave_noprint``
     - class, field
     - Skipped by ``print``.
   * - ``weave_deep``
     - field
     - A class handle, or an array of them, is copied, compared and printed deep: the
       copy is a new object (created through the binding's factory) holding a copy of
       the original. Without it, handles are copied and compared as handles.

Field types
-----------

``copy`` assigns every kind of field. ``compare`` uses ``!==`` for four-state values,
compares arrays element by element (associative arrays by key), and skips unpacked
structs, which SV cannot compare (with a warning). Events are skipped by all three:
assigning an event aliases it. ``print`` shows integers in hex, enums by name,
strings quoted, and arrays and structs with ``%p``.
