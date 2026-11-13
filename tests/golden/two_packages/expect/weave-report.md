# sv-weave report

sv-weave @VERSION@, API 0.3. Verify: full.

2 targets, 2 woven classes, 4 generated files; 0 warnings, 0 errors.

## Profiles

| Profile | Extension sets |
|---|---|
| release (default) | core |

## Woven classes

| Class | Binding | release |
|---|---|---|
| `base_pkg::item` | reflib | `Woven_item__release` (t_copy[core]) |
| `ext_pkg::ext_item` | reflib | `Woven_ext_item__release` (t_copy[core]) |

## Not woven

| Class | Reason |
|---|---|
| `reflib_pkg::ref_creator` | no binding root among its base classes |
| `reflib_pkg::ref_object` | no binding root among its base classes |
| `reflib_pkg::ref_profile_rule` | no binding root among its base classes |
| `reflib_pkg::ref_profiles` | no binding root among its base classes |
| `reflib_pkg::ref_registry` | no binding root among its base classes |
