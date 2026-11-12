"""``sv-weave.yaml``: the configuration model (design §9) and its loader.

Validation errors are reported at the YAML file and line of the offending key.
Relative paths in the config are resolved against the config file's directory.
"""
import fnmatch
import os
from typing import Any, Dict, List, Literal, Optional, Tuple, Union

import yaml
from pydantic import (BaseModel, ConfigDict, Field, PrivateAttr, ValidationError, field_validator,
                      model_validator)

from .diag import Diag, Severity, SrcLoc, SvWeaveError, error
from .filelist import SourceSpec, read_filelist


class RefError(ValueError):
    """A cross-reference error, with the config path it belongs to."""

    def __init__(self, path: Tuple, msg: str):
        super().__init__(msg)
        self.path = path


class _Model(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)


class SourcesCfg(_Model):
    filelists: List[str] = Field(default_factory=list,
                                 description="-f filelists, relative to the config file")
    files: List[str] = Field(default_factory=list, description="SystemVerilog source files")
    incdirs: List[str] = Field(default_factory=list, description="Include directories")
    defines: Dict[str, Union[str, int, None]] = Field(
        default_factory=dict, description="Preprocessor defines; null for a bare define")
    top: List[str] = Field(default_factory=list,
                           description="Top modules to elaborate (default: every "
                                       "uninstantiated module)")


class PackagesCfg(_Model):
    include: List[str] = Field(default_factory=lambda: ["*"],
                               description="Globs of user packages to weave")
    exclude: List[str] = Field(default_factory=list,
                               description="Globs of user packages not to weave")


class ExtensionSetCfg(_Model):
    """Safety flags of an extension set (design §6.6). They default to off, except in
    the set named ``core``, where any flag not given defaults to on."""
    allow_rand: bool = Field(False, description="rand/randc, constraints, randomize(), "
                             "srandom(), $urandom and friends")
    allow_state: bool = Field(False, description="Class property declarations")
    allow_alloc: bool = Field(False, description="new, and calls to create()")
    allow_threads: bool = Field(False, description="fork")


class WeaverCfg(_Model):
    name: str = Field(description="Weaver entry-point name, or module:Class")
    set: str = Field("core", description="Extension set the weaver belongs to")
    match: Optional[str] = Field(None, description="Match expression narrowing where the "
                                 "weaver applies")
    order: Optional[int] = Field(None, description="Dispatch order (lower first); then name")
    before: List[str] = Field(default_factory=list, description="Weavers whose content this "
                              "weaver's content must precede, in every method section")
    after: List[str] = Field(default_factory=list, description="Weavers whose content this "
                             "weaver's content must follow, in every method section")
    options: Dict[str, Any] = Field(default_factory=dict, description="Passed to the weaver")


class Config(_Model):
    version: Literal[1] = Field(1, description="Config format version")
    sources: SourcesCfg = Field(default_factory=SourcesCfg)
    packages: PackagesCfg = Field(default_factory=PackagesCfg)
    binding: Union[str, List[str], None] = Field(
        None, description="Binding name or module:Class, or a list (required to weave)")
    out_dir: str = Field("sv-weave-out", description="Output directory")
    registration: Literal["explicit", "static"] = Field(
        "explicit", description="How woven classes are registered (see design §8.4)")
    strict: bool = Field(False, description="Treat warnings as errors")
    verify: Literal["full", "syntax", "off"] = Field("full", description="Verification level")
    extension_sets: Dict[str, ExtensionSetCfg] = Field(
        default_factory=lambda: {"core": ExtensionSetCfg()}, alias="extension-sets",
        description="Named groups of weavers with safety flags; 'core' defaults to all on")
    weavers: List[WeaverCfg] = Field(default_factory=list, description="Weavers to run")
    plugin_path: List[str] = Field(
        default_factory=list, alias="plugin-path",
        description="Directories to import module:Class weavers and bindings from, "
                    "besides the config file's own")
    profiles: Dict[str, List[str]] = Field(
        default_factory=lambda: {"release": ["core"]},
        description="Profile name -> extension sets (globs allowed)")
    build_profiles: Optional[List[str]] = Field(
        default=None, alias="build-profiles",
        description="Profiles to generate (default: all)")
    default_profile: Optional[str] = Field(
        default=None, alias="default-profile",
        description="Profile used at run time unless chosen otherwise (default: the first "
                    "build profile)")

    # Not part of the YAML: the directory relative paths resolve against.
    _base_dir: str = PrivateAttr(default=".")

    @property
    def base_dir(self) -> str:
        return self._base_dir

    @field_validator("verify", mode="before")
    @classmethod
    def _verify_bool(cls, v):
        # YAML 1.1 reads a bare `off` as false (and `on` as true).
        if v is False:
            return "off"
        if v is True:
            return "full"
        return v

    @model_validator(mode="after")
    def _check_refs(self):
        core = self.extension_sets.get("core")
        if core is not None:
            for flag in ("allow_rand", "allow_state", "allow_alloc", "allow_threads"):
                if flag not in core.model_fields_set:
                    setattr(core, flag, True)
        sets = set(self.extension_sets)
        for i, w in enumerate(self.weavers):
            if w.set not in sets:
                raise RefError(("weavers", i, "set"), "weaver '%s' uses unknown extension set '%s'"
                               % (w.name, w.set))
        for prof, members in self.profiles.items():
            for i, pat in enumerate(members):
                if not fnmatch.filter(sets, pat):
                    raise RefError(("profiles", prof, i),
                                   "profile '%s' names '%s', which matches no extension set"
                                   % (prof, pat))
        if self.build_profiles is None:
            self.build_profiles = list(self.profiles)
        for i, p in enumerate(self.build_profiles):
            if p not in self.profiles:
                raise RefError(("build-profiles", i), "build-profiles names unknown profile '%s'" % p)
        if self.default_profile is None:
            self.default_profile = self.build_profiles[0] if self.build_profiles else None
        elif self.default_profile not in self.build_profiles:
            raise RefError(("default-profile",), "default-profile '%s' is not in build-profiles"
                           % self.default_profile)
        return self

    @property
    def bindings(self) -> List[str]:
        if self.binding is None:
            return []
        return [self.binding] if isinstance(self.binding, str) else list(self.binding)

    def profile_sets(self, profile: str) -> List[str]:
        """The extension sets a profile includes, with globs expanded, in config order."""
        out = []
        for pat in self.profiles[profile]:
            for s in self.extension_sets:
                if fnmatch.fnmatchcase(s, pat) and s not in out:
                    out.append(s)
        return out

    def plugin_dirs(self) -> List[str]:
        return [self.base_dir] + [self.resolve(d) for d in self.plugin_path]

    def resolve(self, path: str) -> str:
        return path if os.path.isabs(path) else os.path.normpath(os.path.join(self.base_dir, path))

    def source_spec(self) -> SourceSpec:
        spec = SourceSpec()
        for fl in self.sources.filelists:
            spec.extend(read_filelist(self.resolve(fl)))
        for f in self.sources.files:
            f = self.resolve(f)
            if f not in spec.files:
                spec.files.append(f)
        spec.incdirs.extend(self.resolve(d) for d in self.sources.incdirs)
        for k, v in self.sources.defines.items():
            spec.defines[k] = None if v is None else str(v)
        spec.tops.extend(t for t in self.sources.top if t not in spec.tops)
        return spec


TOP_KEY = "sv-weave"


def _line_of(node: yaml.Node, path: Tuple) -> Optional[int]:
    """1-based line of the deepest YAML node along ``path``."""
    line = node.start_mark.line + 1
    for key in path:
        if isinstance(node, yaml.MappingNode):
            nxt = None
            for k, v in node.value:
                if k.value == str(key):
                    line = k.start_mark.line + 1
                    nxt = v
                    break
            if nxt is None:
                return line
            node = nxt
        elif isinstance(node, yaml.SequenceNode) and isinstance(key, int) and key < len(node.value):
            node = node.value[key]
            line = node.start_mark.line + 1
        else:
            return line
    return line


def parse_config(text: str, path: str = "<string>", base_dir: Optional[str] = None) -> Config:
    try:
        node = yaml.compose(text)
        data = yaml.safe_load(text)
    except yaml.YAMLError as e:
        mark = getattr(e, "problem_mark", None)
        loc = SrcLoc(path, mark.line + 1, mark.column + 1) if mark else SrcLoc(path, 1)
        raise error("invalid YAML: %s" % getattr(e, "problem", e), loc)
    if not isinstance(data, dict) or TOP_KEY not in data:
        raise error("config must have a top-level '%s:' key" % TOP_KEY, SrcLoc(path, 1))
    body = data[TOP_KEY] or {}
    if base_dir is None:
        base_dir = os.path.dirname(os.path.abspath(path)) if path != "<string>" else os.getcwd()
    try:
        cfg = Config.model_validate(body)
    except ValidationError as e:
        diags = []
        for err in e.errors():
            ref = (err.get("ctx") or {}).get("error")
            err_loc = tuple(ref.path) if isinstance(ref, RefError) else tuple(err["loc"])
            err["loc"] = err_loc
            loc_path = (TOP_KEY,) + err_loc
            line = _line_of(node, loc_path) if node is not None else 1
            where = ".".join(str(p) for p in err["loc"]) or TOP_KEY
            msg = err["msg"]
            if msg.startswith("Value error, "):
                msg = msg[len("Value error, "):]
            diags.append(Diag(Severity.ERROR, "%s: %s" % (where, msg), SrcLoc(path, line)))
        raise SvWeaveError(diags)
    cfg._base_dir = base_dir
    return cfg


def load_config(path: str) -> Config:
    if not os.path.isfile(path):
        raise error("config file not found: %s" % path)
    with open(path) as fp:
        return parse_config(fp.read(), os.path.abspath(path))


def json_schema() -> dict:
    """JSON Schema of sv-weave.yaml (the top-level ``sv-weave:`` key included)."""
    inner = Config.model_json_schema(by_alias=True)
    defs = inner.pop("$defs", {})
    inner.get("properties", {}).pop("base_dir", None)
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "title": "sv-weave.yaml",
        "type": "object",
        "properties": {TOP_KEY: inner},
        "required": [TOP_KEY],
        "additionalProperties": False,
        "$defs": defs,
    }
