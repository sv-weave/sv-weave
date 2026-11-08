# Stop writing UVM boilerplate: introducing sv-weave

*Your SystemVerilog classes are the spec. sv-weave turns them into expert
implementations, and only the people who build the library need to know how.*

---

Every UVM engineer has written this class:

```systemverilog
class bus_tx extends uvm_sequence_item;
  rand bit [31:0] addr;
  rand bit [31:0] data;
  rand bit [7:0]  payload[];
  rand bus_op_e   op;

  `uvm_object_utils_begin(bus_tx)
    `uvm_field_int(addr, UVM_ALL_ON)
    `uvm_field_int(data, UVM_ALL_ON)
    `uvm_field_array_int(payload, UVM_ALL_ON)
    `uvm_field_enum(bus_op_e, op, UVM_ALL_ON)
  `uvm_object_utils_end

  function new(string name = "bus_tx");
    super.new(name);
  endfunction
endclass
```

Four fields, four macros. The field macros make it short, but you pay for them at run
time and in the debugger. So many teams ban them and write `do_copy`, `do_compare`,
`convert2string` and `do_print` by hand instead. That's forty lines of code that has
to change every time a field does. Someone adds a `rand bit [3:0] prot` field six
months later and forgets `do_compare`. Nothing fails, and the scoreboard quietly
stops checking `prot`.

The third option is a code generator: describe the transaction in YAML, generate the
class, and then argue about where hand-written code is allowed to go. Now there are
two sources of truth, a generator to maintain, and a "do not edit below this line"
comment that someone eventually edits below.

All three approaches have the same flaw. **Everyone who writes a class has to know
how the mechanism works.** Every sequence-item author has to remember the macros, the
conventions or the YAML format. The expertise doesn't stay with the experts. It's
spread thinly across the whole team, and it wears thin.

## Your classes are the metadata

sv-weave takes a different approach. You write the class you meant to write:

```systemverilog
class bus_tx extends uvm_sequence_item;
  `uvm_object_utils(bus_tx)
  rand bit [31:0] addr;
  rand bit [31:0] data;
  rand bit [7:0]  payload[];
  rand bus_op_e   op;
  (* weave_nocopy *) int n_retries;   // bookkeeping, not data

  function new(string name = "bus_tx");
    super.new(name);
  endfunction
endclass
```

That's the whole class. There are no field macros and no hand-written `do_copy`.

At build time, sv-weave reads your sources with [slang](https://github.com/MikePopoloski/slang),
a complete SystemVerilog front end. For each class it generates a **woven subclass**
that implements the library's virtual hooks (`do_copy`, `do_compare`,
`convert2string` and so on) for exactly the fields that class has. The generated code
is plain, field-by-field SystemVerilog, the code an expert would write by hand.

Then the factory does the rest:

```systemverilog
bus_tx t = bus_tx::type_id::create("t");   // the factory hands out the woven class
bus_tx u = bus_tx::type_id::create("u");
u.copy(t);                                 // runs the generated do_copy()
```

UVM's factory already lets a library replace a class with a subclass everywhere it is
created. sv-weave uses that same mechanism. Your overrides resolve as they always
have, and the woven class is applied on top. Your code never names generated code,
your source is never edited, and there is nothing to merge.

Add `prot` six months from now and it is copied, compared and printed on the next
build. The "forgot to update `do_compare`" bug can't happen.

## Only the producer learns the generator

This is the part that changes how a team works.

Any class library has two kinds of user:

- **Producers**: the methodology team, VIP authors and protocol-package
  maintainers. They own the base classes and know how things *should* be done.
- **Consumers**: everyone else, the engineers writing testbenches and tests on top
  of the library.

With sv-weave, **producers write weavers**. A weaver is a small Python plugin that
contributes code to the classes it applies to. Here is a complete one, which
implements a library's `print` feature:

```python
from sv_weave import plugin
from sv_weave.match import extends_root

class PrintFields(plugin.Weaver):
    name = "print-fields"

    def subscribe(self, bus):
        bus.on(extends_root(), self.weave)

    def weave(self, w):
        p = w.feature("print")
        for f in w.fields():
            if f.static or not w.sv.accessible(f):
                continue
            p.body.add('%s = {%s, $sformatf("%s=%%0h\\n", %s)};'
                       % (p.ret_var, p.ret_var, f.name, f.name))
```

**Consumers learn nothing new.** They write ordinary classes. When they want
something other than the default, they add an attribute such as `(* weave_nocopy *)`
or `(* weave_deep *)`. The weave step is a task in the flow, next to compilation:

```yaml
- name: woven
  uses: svweave.Weave
  needs: [uvm, rtl]
  with:
    config: sv-weave.yaml
```

The difference is where the expertise lives. Whoever knows how deep copy should
treat object handles, or how `do_compare` should report a mismatch in a dynamic array,
puts that knowledge in a weaver **once**. From then on, every class in every
testbench that uses the library gets it. Fix a bug or speed up the generated code in
the weaver, and every consumer gets the change on the next build without touching a
line of their code.

**A library now ships with its generator.** A protocol package ships its transaction
base classes and the weavers that implement them for whatever transactions you
derive. You get the benefits of a code generator without ever seeing one.

## It doesn't cost you speed

Woven code is plain SystemVerilog, written field by field. There is no field-macro
machinery and no policy lookup at run time. In our measurements, woven classes run at
least as fast as hand-written hooks and faster than field macros, and simulators
compile them like any other SV class.

Because the generated code is ordinary SV in an ordinary package, you can read it,
set breakpoints in it and step through it. `sv-weave report` shows exactly what was
generated for each class and by which weaver.

## Checked before it's written

A code generator you can't trust is worse than none. Before sv-weave writes anything,
slang elaborates the generated code together with your design. If a weaver produces
bad code, you get an error that points at the weaver and the line it produced, not a
simulation failure three hours into a regression.

## Debug builds that keep your stimulus

Weavers are grouped into **extension sets**, and sets are grouped into **profiles**:
`release`, `debug`, whatever your team needs. Profiles are built side by side and
chosen when you run:

```
simv +UVM_TESTNAME=smoke +ntb_random_seed=1234                       # release
simv +UVM_TESTNAME=smoke +ntb_random_seed=1234 +weave_profile=debug  # same stimulus, full checking
```

The debug profile can add X-checking, tracing, transaction recording and verbose
printing. None of it is in your source, and none of it changes your random stimulus.
sv-weave enforces this:
- debug sets can't add `rand` fields or constraints;
- they can't call `randomize`;
- they can't start threads or add delays;
- each debug contribution runs inside an RNG fence that saves and restores the
  thread's random state, so even library calls that allocate objects don't shift
  your seeds.

That gives you a workflow regressions have needed for a long time: a seed fails
overnight, and you **rerun exactly that seed with full debug turned on** and see the
same failure, with every check enabled.

## Not just UVM

sv-weave isn't tied to UVM. A **binding** adapts it to a class library. The binding
says which base classes it covers, which hook each feature maps to, and how woven
classes register with the library's factory. A `copy` weaver is written once and works
with UVM, with an in-house class library, or with synthesizable class code. Your UVM
version is the binding's concern, so consumer code doesn't change when you move from
UVM 1.2 to IEEE 1800.2.

Adopting it is gradual. Woven code runs after `super`, so a class that already has a
hand-written `do_copy` keeps working while the rest of the codebase moves over.

## Reflection, finally

SystemVerilog has no reflection. Weavers can query the whole design, for example "all
concrete subclasses of `base_seq`" or "every class that implements this interface
class", and generate code across that set. A sequence library that registers every
subclass, or a selector that picks among all of them through the factory, stops being
a list someone has to keep up to date by hand.

This also points to where sv-weave is going. The same model can produce outputs that
aren't SystemVerilog:
- Python and C++ mirrors of your transactions, for cocotb and DPI reference models;
- covergroups whose bins come from what your constraints can actually reach;
- regression test lists;
- transaction documentation.

All of it comes from the SV classes you already wrote.

## Try it

- **Quickstart:** `docs/quickstart.rst`, with a working example in `examples/quickstart/`.
- **If you write classes:** `docs/user/attributes.rst` is all you need.
- **If you own a library:** `docs/authoring/weavers.rst` and `docs/authoring/bindings.rst`.

Write the class you meant to write. Let the people who know the library make it
right, once, for everyone.
