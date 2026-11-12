# sv-weave report

sv-weave @VERSION@, API 0.1. Verify: full.

1 target, 1 woven class, 3 generated files; 0 warnings, 0 errors.

## Profiles

| Profile | Extension sets |
|---|---|
| release (default) | core |

## Woven classes

| Class | Binding | release |
|---|---|---|
| `a_pkg::A` | reflib | `Woven_A__release` (t_build[core], t_build2[core]) |

## Not woven

| Class | Reason |
|---|---|
| `reflib_pkg::ref_creator` | no binding root among its base classes |
| `reflib_pkg::ref_object` | no binding root among its base classes |
| `reflib_pkg::ref_profile_rule` | no binding root among its base classes |
| `reflib_pkg::ref_profiles` | no binding root among its base classes |
| `reflib_pkg::ref_registry` | no binding root among its base classes |
