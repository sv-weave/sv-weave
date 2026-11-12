Configuration: ``sv-weave.yaml``
================================

.. code-block:: yaml

    sv-weave:
      version: 1
      sources:                    # optional when the dv-flow task supplies them
        filelists: [rtl/files.f]
        files: [tb/tb_pkg.sv]
        incdirs: [rtl/include]
        defines: {SIM: 1}
      packages:
        include: ["eth_*"]        # default ["*"]
        exclude: ["*_tb_pkg"]
      binding: "uvm_binding:UvmBinding"   # required: name or module:Class, or a list
      plugin-path: [tools/weavers]      # where module:Class plugins are imported from
      out_dir: build/woven        # default sv-weave-out
      registration: explicit      # explicit | static
      strict: false               # warnings become errors
      verify: full                # full | syntax | off
      extension-sets:
        core: {}
        debug: {allow_state: true}
      weavers:
      - name: copy                # entry-point name, or module:Class
        set: core                 # default core
        match: "extends(base_item)"   # narrows where the weaver applies
        order: 0                  # dispatch order; then by name
        before: [xcheck]          # this weaver's code goes before xcheck's code
        after: []                 # ... or after another weaver's
        options: {}               # passed to the weaver
      profiles:
        release: [core]
        debug: [core, "debug*"]   # globs over extension-set names
      build-profiles: [release, debug]   # default: every profile
      default-profile: release           # default: the first build profile

Relative paths are relative to the config file. Errors are reported at the file and
line of the offending key.

Keys
----

``sources``
    ``filelists`` (``-f`` format, see :doc:`cli`), ``files``, ``incdirs``,
    ``defines``, ``top``. Command-line and dv-flow sources are added after these.
    ``top`` lists the modules slang elaborates (``--top`` on the command line, the
    ``top`` parameter of ``svweave.Weave``); by default every uninstantiated module is
    a top. Set it when the sources hold a module that cannot elaborate on its own,
    for example one whose ``type`` parameter defaults to a type that is not a class.
``packages``
    Globs selecting which user packages are woven. ``std``, ``uvm_pkg``, sv-weave's
    own packages and ``*_woven`` are never woven.
``binding``
    Required. A binding name (entry point), a ``module:Class`` reference, or a
    list. sv-weave has no built-in binding; see :doc:`../examples`.
``registration``
    ``explicit``: the design installs registration with ``sv_weave_init_m`` or a call
    to ``sv_weave_init_pkg::sv_weave_init()``. ``static``: each woven package also
    registers itself from a static initialiser.
``init``
    ``true`` (the default) writes the init files, ``sv_weave_init_pkg.sv`` and
    ``sv_weave_init_m.sv``. ``false`` writes none; the manifest's ``register`` list
    still names the woven packages, for ``svweave.Init`` (see :doc:`dvflow`).
``strict``
    Makes warnings errors, for example a ``local`` field a weaver cannot reach.
``verify``
    See :doc:`../authoring/verify-rules`. YAML reads a bare ``off`` as false; sv-weave
    accepts that too.
``extension-sets``
    Named groups of weavers, with the safety flags ``allow_rand``, ``allow_state``,
    ``allow_alloc`` and ``allow_threads``. Default: ``{core: {}}``.
``weavers``
    The weavers to run. ``set`` must name an extension set.
``plugin-path``
    Directories to import ``module:Class`` weavers and bindings from, besides the
    config file's own directory.
``profiles``, ``build-profiles``, ``default-profile``
    A profile is a list of extension sets; each built profile gets its own woven
    classes. Only profiles that include a weaver's set run that weaver.
