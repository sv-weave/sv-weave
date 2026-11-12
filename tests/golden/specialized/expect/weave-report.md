# sv-weave report

sv-weave @VERSION@, API 0.2. Verify: full.

2 targets, 2 woven classes, 3 generated files; 0 warnings, 0 errors.

## Profiles

| Profile | Extension sets |
|---|---|
| release (default) | core |

## Woven classes

| Class | Binding | release |
|---|---|---|
| `g_pkg::G#(16)` | reflib | `Woven_G_27a85__release` (t_copy[core]) |
| `g_pkg::G#(8)` | reflib | `Woven_G_6addb__release` (t_copy[core]) |

## Specialisations

| Hash | Class | Parameters |
|---|---|---|
| `27a85` | `g_pkg::G#(16)` | W=16 |
| `6addb` | `g_pkg::G#(8)` | W=8 |

## Not woven

| Class | Reason |
|---|---|
| `reflib_pkg::ref_creator` | no binding root among its base classes |
| `reflib_pkg::ref_object` | no binding root among its base classes |
| `reflib_pkg::ref_profile_rule` | no binding root among its base classes |
| `reflib_pkg::ref_profiles` | no binding root among its base classes |
| `reflib_pkg::ref_registry` | no binding root among its base classes |
| `g_pkg::user` | no binding root among its base classes |
