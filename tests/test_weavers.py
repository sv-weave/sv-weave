"""Weavers used only by tests. Registered in-process by fixtures; not entry points."""
from sv_weave import plugin
from sv_weave.match import any_class, has_method


class TBuild(plugin.Weaver):
    """Wraps build() with a display before and after super."""
    name = "t_build"

    def subscribe(self, bus):
        bus.on(has_method("build"), self.weave)

    def weave(self, w):
        tag = self.options.get("tag", self.name)
        s = w.override("build")
        s.pre.add('$display("%s: pre build %s");' % (tag, w.cls.name))
        s.post.add('$display("%s: post build %s");' % (tag, w.cls.name))


class TBuild2(TBuild):
    name = "t_build2"


class TCopy(plugin.Weaver):
    """Copies every reachable field through the binding's copy feature."""
    name = "t_copy"

    def subscribe(self, bus):
        bus.on(any_class(), self.weave)

    def weave(self, w):
        c = w.feature("copy")
        rhs = w.sv.cast_rhs(c)
        for f in w.fields():
            if f.static or f.const or "weave_nocopy" in f.attrs or not w.sv.accessible(f):
                continue
            c.body.add("this.%s = %s.%s;" % (f.name, rhs, f.name))


class TReplace(plugin.Weaver):
    """Replaces super in build()."""
    name = "t_replace"

    def subscribe(self, bus):
        bus.on(has_method("build"), self.weave)

    def weave(self, w):
        s = w.override("build")
        s.replace_super()
        s.body.add('$display("replaced");')


class TReplace2(TReplace):
    name = "t_replace2"


class TState(plugin.Weaver):
    """Adds a field (needs allow_state)."""
    name = "t_state"

    def subscribe(self, bus):
        bus.on(any_class(), self.weave)

    def weave(self, w):
        n = w.sv.fresh("seen")
        w.add_field("int unsigned %s;" % n)
        m = w.add_method("seen_count", ret="int unsigned")
        m.set_result(n)


class TBoom(plugin.Weaver):
    name = "t_boom"

    def subscribe(self, bus):
        bus.on(any_class(), self.weave)

    def weave(self, w):
        raise KeyError("oops")


ALL = [TBuild, TBuild2, TCopy, TReplace, TReplace2, TState, TBoom]


class TFrag(plugin.Weaver):
    """Adds options['body'] to build(), options['item'] as a class item. For Verify tests."""
    name = "t_frag"

    def subscribe(self, bus):
        bus.on(has_method("build"), self.weave)

    def weave(self, w):
        if "body" in self.options:
            w.override("build").body.add(self.options["body"])   # FRAG_BODY_LINE
        if "item" in self.options:
            w.add_item(self.options["item"])


ALL.append(TFrag)


class TPlace(plugin.Weaver):
    """Adds options['lines'] to sections of build(): each entry is
    {section: decl|pre|post, text, first, before, after}. For placement tests."""
    name = "t_place"

    def subscribe(self, bus):
        bus.on(has_method("build"), self.weave)

    def weave(self, w):
        s = w.override("build")
        for l in self.options.get("lines", []):
            getattr(s, l["section"]).add(l["text"], first=l.get("first", False),
                                         before=l.get("before", ()), after=l.get("after", ()))


class TPlaceA(TPlace):
    name = "t_place_a"


class TPlaceB(TPlace):
    name = "t_place_b"


class TPlaceC(TPlace):
    name = "t_place_c"


ALL.extend([TPlaceA, TPlaceB, TPlaceC])
