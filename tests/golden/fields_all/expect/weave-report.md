# sv-weave report

sv-weave @VERSION@, API 0.1. Verify: full.

2 targets, 2 woven classes, 2 generated files; 4 warnings, 0 errors.

## Profiles

| Profile | Extension sets |
|---|---|
| release (default) | core |

## Woven classes

| Class | Binding | release |
|---|---|---|
| `f_pkg::all_fields` | reflib | `Woven_all_fields__release` (compare[core], copy[core], print[core]) |
| `f_pkg::leaf` | reflib | `Woven_leaf__release` (compare[core], copy[core], print[core]) |

## Not woven

| Class | Reason |
|---|---|
| `reflib_pkg::ref_creator` | no binding root among its base classes |
| `reflib_pkg::ref_object` | no binding root among its base classes |
| `reflib_pkg::ref_profile_rule` | no binding root among its base classes |
| `reflib_pkg::ref_profiles` | no binding root among its base classes |
| `reflib_pkg::ref_registry` | no binding root among its base classes |

## Diagnostics

- **warning** in/f.sv:21:18: compare: f_pkg::all_fields.rec: unpacked structs cannot be compared; skipped
- **warning** in/f.sv:36:18: compare: f_pkg::all_fields.hidden is local and cannot be reached from a woven subclass; skipped (make it protected, or mark it (* weave_nocopy *))
- **warning** in/f.sv:36:18: copy: f_pkg::all_fields.hidden is local and cannot be reached from a woven subclass; skipped (make it protected, or mark it (* weave_nocopy *))
- **warning** in/f.sv:36:18: print: f_pkg::all_fields.hidden is local and cannot be reached from a woven subclass; skipped (make it protected, or mark it (* weave_nocopy *))
