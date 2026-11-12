# Changelog

## 0.2.0

Contribution API 0.2. The default plugin range (`Weaver.api`, `Binding.api`) moves
to `">=0.2,<0.3"`; a plugin that declares `">=0.1,<0.2"` is refused until it widens
its range (0.2 only adds to 0.1).

Added:

- `cls.decl`: a class's declaration as written (`SvDecl`: header, parameters,
  typedefs with packed-struct members, methods, properties). The `SvDecl*` types
  are exported from `sv_weave.api`.
- `sources.top` (config), `--top` (CLI), `top` (`svweave.Weave`): the modules
  slang elaborates.
- `DesignCtx.add_file(name, text)`: whole generated files (modules, interfaces)
  from an `on_design` handler, compiled after the woven packages.
- `init: false` (config; `init` param of `svweave.Weave`) and the task
  `svweave.Init`: one init for several Weave tasks feeding one image. The manifest
  lists the packages to register (`register`).
- `Weaver.fingerprint()` / `Binding.fingerprint()`: override what the input hash
  records for a plugin's code.

Changed:

- The init file is split: `sv_weave_init_pkg.sv` and `sv_weave_init_m.sv` replace
  `sv_weave_init.sv` (Verilator DECLFILENAME); `m_done` is lint-clean under
  `-Wall`. Flows that name the old file need updating.
- A woven package also imports the packages its user package wildcard-imports.
  A name that two of those packages export now needs qualifying in woven code,
  if woven code uses it.
- The run's input hash covers each plugin's source and sv-weave's own, not only
  their version strings, and `svweave.Weave` has an up-to-date check that uses
  it: editing a weaver or the `sv-weave.yaml` the task names re-weaves.
- A run with `init: true` over sources that already hold another run's init
  files is an error naming the fix.
