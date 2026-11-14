"""The manifest (``weave-manifest.json``) and its Markdown view (``weave-report.md``)."""
import json
from typing import Any, Dict, List

from .api_version import API_VERSION
from .__version__ import __version__
from .weave.ctx import spec_hash

SCHEMA_VERSION = 1


def build_manifest(res) -> Dict[str, Any]:
    cfg = res.cfg
    targets = []
    for t in res.selection.targets:
        c = t.cls
        entry: Dict[str, Any] = {
            "class": c.qname,
            "package": c.package,
            "binding": t.binding,
            "root": t.root.qname,
            "loc": str(c.loc) if c.loc else None,
            "woven": {},
        }
        if c.is_specialization:
            entry["specialization"] = {"generic": c.generic.qname, "params": c.params,
                                       "hash": spec_hash(c.qname)}
        for wc in res.woven:
            if wc.cls is not c:
                continue
            for prof in wc.profiles:
                entry["woven"][prof] = {
                    "name": wc.name,
                    "package": c.package + "_woven",
                    "registered": wc.concrete,
                    "contributors": ["%s[%s]" % (n, s) for n, s in wc.contributors if s],
                    "slots": list(wc.slots),
                }
        entry["woven"] = {p: entry["woven"][p] for p in cfg.build_profiles if p in entry["woven"]}
        targets.append(entry)
    return {
        "schema_version": SCHEMA_VERSION,
        "sv_weave_version": __version__,
        "api_version": ".".join(str(x) for x in API_VERSION),
        "plugins": res.plugin_versions,
        "input_hash": res.input_hash,
        "output_hash": res.output_hash,
        # Woven packages whose __register() an init calls, in order (svweave.Init).
        "register": res.register,
        # A cache hit means this exact output already passed full verification; the
        # manifest records that, so it does not change between runs.
        "verify": "full" if res.verify_status == "cached" else res.verify_status,
        "verified": res.verified,
        "profiles": {p: cfg.profile_sets(p) for p in cfg.build_profiles},
        "default_profile": cfg.default_profile,
        "targets": targets,
        "skipped": res.selection.skipped,
        "files": {
            "runtime": res.runtime_files,
            "generated": res.generated_names,
            "compile_order": res.compile_order,
            "pre": res.pre_files,
        },
        "diagnostics": [{"severity": d.severity.name.lower(), "msg": d.msg,
                         "loc": str(d.loc) if d.loc else None} for d in res.diags],
    }


def manifest_text(m: Dict[str, Any]) -> str:
    return json.dumps(m, indent=2, sort_keys=False) + "\n"


def render_report(m: Dict[str, Any]) -> str:
    out: List[str] = ["# sv-weave report", ""]
    out.append("sv-weave %s, API %s. Verify: %s." % (m["sv_weave_version"], m["api_version"],
                                                     m.get("verify", "?")))
    n_classes = len({w["name"] for t in m["targets"] for w in t["woven"].values()})
    n_err = sum(1 for d in m["diagnostics"] if d["severity"] == "error")
    n_warn = sum(1 for d in m["diagnostics"] if d["severity"] == "warning")
    out.append("")
    out.append("%d target%s, %d woven class%s, %d generated file%s; %d warning%s, %d error%s." % (
        len(m["targets"]), "" if len(m["targets"]) == 1 else "s",
        n_classes, "" if n_classes == 1 else "es",
        len(m["files"]["compile_order"]), "" if len(m["files"]["compile_order"]) == 1 else "s",
        n_warn, "" if n_warn == 1 else "s", n_err, "" if n_err == 1 else "s"))
    out.append("")
    out.append("## Profiles")
    out.append("")
    out.append("| Profile | Extension sets |")
    out.append("|---|---|")
    for p, sets in m["profiles"].items():
        mark = " (default)" if p == m.get("default_profile") else ""
        out.append("| %s%s | %s |" % (p, mark, ", ".join(sets)))
    out.append("")
    out.append("## Woven classes")
    out.append("")
    profiles = list(m["profiles"])
    out.append("| Class | Binding | " + " | ".join(profiles) + " |")
    out.append("|---|---|" + "---|" * len(profiles))
    for t in m["targets"]:
        cells = []
        for p in profiles:
            w = t["woven"].get(p)
            if w is None:
                cells.append("–")
            else:
                cell = "`%s` (%s)" % (w["name"], ", ".join(w["contributors"]))
                if not w["registered"]:
                    cell += " not registered: abstract"
                cells.append(cell)
        out.append("| `%s` | %s | %s |" % (t["class"], t["binding"], " | ".join(cells)))
    specs = [t for t in m["targets"] if "specialization" in t]
    if specs:
        out.append("")
        out.append("## Specialisations")
        out.append("")
        out.append("| Hash | Class | Parameters |")
        out.append("|---|---|---|")
        for t in specs:
            s = t["specialization"]
            params = ", ".join("%s=%s" % kv for kv in s["params"].items())
            out.append("| `%s` | `%s` | %s |" % (s["hash"], t["class"], params))
    # Classes in packages that were not selected (library and sv-weave packages
    # included) are left out here; the manifest lists them all.
    skipped = {k: v for k, v in m["skipped"].items() if "not selected" not in v
               and v != "not in a package"}
    if skipped:
        out.append("")
        out.append("## Not woven")
        out.append("")
        out.append("| Class | Reason |")
        out.append("|---|---|")
        for k, v in skipped.items():
            out.append("| `%s` | %s |" % (k, v))
    if m["diagnostics"]:
        out.append("")
        out.append("## Diagnostics")
        out.append("")
        for d in m["diagnostics"]:
            out.append("- **%s** %s%s" % (d["severity"], (d["loc"] + ": ") if d["loc"] else "",
                                          d["msg"]))
    out.append("")
    return "\n".join(out)
