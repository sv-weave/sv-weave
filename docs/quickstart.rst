Quickstart
==========

This example weaves a ``print`` method into a packet class, then runs it on Verilator.
The files are in ``examples/quickstart/``; the test suite runs this example, so it
works as written. It uses the example reference library ``reflib`` (see
:doc:`examples`); with UVM the steps are the same, with the UVM library and binding.

The design
----------

A plain class that derives from the library's base class, ``ref_object``:

.. literalinclude:: ../examples/quickstart/pkt_pkg.sv
   :language: systemverilog

The testbench creates the packet through the factory and prints it. Nothing in it
names generated code, apart from instantiating ``sv_weave_init_m``, which installs the
generated registration:

.. literalinclude:: ../examples/quickstart/tb.sv
   :language: systemverilog

A weaver
--------

The weaver implements the ``print`` feature by walking the class's fields; the
binding maps that feature onto the library's hook, ``sprint()``:

.. literalinclude:: ../examples/quickstart/my_weavers.py
   :language: python

The config names the binding and the weaver by ``module:Class``; modules are imported
from the config file's directory and from ``plugin-path``. Packaged weavers and
bindings are named by their entry-point names instead.

.. literalinclude:: ../examples/quickstart/sv-weave.yaml
   :language: yaml

Running with the CLI
--------------------

::

    $ cd examples/quickstart
    $ sv-weave gen -o woven pkt_pkg.sv tb.sv
    sv-weave: 1 woven class in 1 package -> .../woven (6 files changed; verify: full)
    $ verilator --binary --top-module tb \
        -f woven/sv_weave_rt.f pkt_pkg.sv tb.sv -f woven/sv_weave.f
    $ ./obj_dir/Vtb
    impl: Woven_packet__release
    addr=10
    data=cafe
    id=0

``sv_weave_rt.f`` lists the SV the binding needs ahead of the design (here the
reference library), and ``sv_weave.f`` the generated code, which compiles after it.

Running with dv-flow
--------------------

.. literalinclude:: ../examples/quickstart/flow.dv
   :language: yaml

::

    $ dfm run sim-run

``svweave.Weave`` passes its input sources through, followed by the woven ones, so the
image task needs only the weave task.
