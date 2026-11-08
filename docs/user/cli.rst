Command line
============

``sv-weave list``
-----------------

Loads the design, builds the class model and runs target selection, without generating
anything::

    sv-weave list [-c sv-weave.yaml] [-b BINDING] [-f files.f] [-I DIR] [-D NAME[=VAL]] [FILE ...]
                  [--targets | --classes] [--json] [--no-runtime]

Sources come from the config's ``sources`` section, from ``-f`` filelists and from
files on the command line, in that order. SV that the binding needs (if any) is added
ahead of them unless ``--no-runtime`` is given. ``-b BINDING`` sets the binding when
there is no config. If no ``-c`` is given, ``./sv-weave.yaml`` is used when it
exists.

``--targets`` (the default)
    One line per target class: the class, its binding and its source location.

``--classes``
    Every class in the model. Targets are marked ``*``; every other class shows why it
    is not a target.

``--json``
    The same information as JSON.

Example::

    $ sv-weave list -b reflib --classes a.sv
      reflib_pkg::ref_object      no binding root among its base classes
    * a_pkg::A                    binding reflib
      a_pkg::Off                  (* weave_off *)
    * a_pkg::P#(8)                binding reflib
      a_pkg::Plain                no binding root among its base classes

Filelists
---------

A filelist (``-f``) holds source files plus these options:

- ``-f FILE`` / ``-F FILE``: a nested filelist. Its paths are relative to its own
  directory.
- ``+incdir+DIR[+DIR...]``, ``-IDIR``, ``-I DIR``: include directories.
- ``+define+NAME[=VAL][+...]``, ``-DNAME[=VAL]``: defines.
- ``//`` and ``#`` comments, and ``$VAR`` / ``${VAR}`` environment variables.

Relative paths are resolved against the filelist's directory. Any other option is an
error, reported at its file and line.

All sources are parsed as one compilation unit, the way most simulators treat a file
list, so a macro defined in one file is visible in the files after it.
