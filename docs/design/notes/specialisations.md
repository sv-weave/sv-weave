# Specialisation discovery and pyslang notes (P1)

Findings from building the front end against pyslang 12.1.0. Code:
`src/sv_weave/frontend/specialize.py`, `model.py`, `types.py`.

## How specialisations are found

Two passes, merged and deduplicated by (generic class path, slang's type string):

1. **Scope walk** over the root, every compilation unit, class bodies (including each
   specialisation found), subroutines, instance bodies and statement blocks. It
   converts the type of each declaration (properties, variables, nets, arguments,
   return types, typedef targets, type parameters, base classes), unwrapping array
   element and index types.
2. **`Symbol.visit`** over the root, checking every `Type` and every object with a
   `.type`. This catches specialisations used only in expressions (`G#(9)::k()`).

Neither pass is enough alone. `visit` found 2 of 8 in the probe design; the scope walk
misses expression-only uses.

Covered by `tests/unit/test_specialize.py`: `extends` clause only, nested
(`G#(4, G#(2))`), property, subroutine local, return type, argument, typedef, a
specialisation reached through another one (`D#(3)` → `G#(6)`), array element, module
initial-block local, and expression only.

## Known limits

- A specialisation the design never names is not modelled. A factory that creates
  one at runtime gets the unwoven class (design §4.3). P3 adds the runtime warning.
- Not yet tested: specialisations inside `generate` blocks, in checkers, in
  covergroups, and in default values of parameters of other classes.

## pyslang quirks worth knowing

- pyslang 12 splits its API into submodules: `pyslang.syntax.SyntaxTree`,
  `pyslang.ast.Compilation`, `pyslang.parsing.PreprocessorOptions`.
- **Wrapper identity:** pyslang wrapper objects are temporaries. `id()` of two
  different symbols can collide once one is garbage-collected. Keep a reference to
  every object whose `id()` you store (the walker does), or key on stable data.
- **Missing base classes are not diagnosed.** `class A extends Missing;` gives no
  diagnostic, even from slang's own driver; `baseClass` is just an error type. The
  model builder reports it itself.
- **Attributes on classes:** `Compilation.getAttributes()` returns nothing for class
  declarations (generic or not), so class attributes are read from
  `ClassDeclarationSyntax.attributes`. For members, `getAttributes()` works, but a
  string value comes back as an integer `ConstantValue`, so values are read from
  `AttributeSymbol.syntax` instead.
- Generic class declarations are `GenericClassDefSymbol` (not `ClassType`);
  specialisations are `ClassType` with `genericClass` set and inherit nothing from
  the generic symbol's attributes.
- Members inherited from a base class appear in a derived class's scope as
  `TransparentMember`; skip them when listing a class's own members.
- Built-in methods (`randomize`, `srandom`, ...) are `Subroutine` members with
  `MethodFlags.BuiltIn`. Pure virtual and extern methods are `MethodPrototype`.
- An override declared without `virtual` reports `flags == 0` but `isVirtual == True`.
- `getPackages()` is not in source order; the model sorts by
  `(location.buffer.id, location.offset)`.
- `SourceManager.setDisableProximatePaths(True)` makes file names absolute.
