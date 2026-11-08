"""sv-weave command-line entry point."""
import argparse
import json
import os
import sys
from typing import List, Optional

from .__version__ import __version__
from .diag import SvWeaveError


def _add_source_args(p: argparse.ArgumentParser):
    p.add_argument("-c", "--config", help="sv-weave.yaml (default: ./sv-weave.yaml if present)")
    p.add_argument("-f", dest="filelists", action="append", default=[], metavar="FILELIST",
                   help="add a filelist (repeatable)")
    p.add_argument("-I", dest="incdirs", action="append", default=[], metavar="DIR",
                   help="add an include directory (repeatable)")
    p.add_argument("-D", dest="defines", action="append", default=[], metavar="NAME[=VAL]",
                   help="add a define (repeatable)")
    p.add_argument("-b", "--binding", action="append", default=[],
                   help="binding name or module:Class (repeatable; overrides the config)")
    p.add_argument("--no-runtime", action="store_true",
                   help="do not add the bindings' SV sources ahead of the design")
    p.add_argument("files", nargs="*", help="SystemVerilog sources")


def get_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="sv-weave",
        description="Factory weaving for SystemVerilog class libraries")
    parser.add_argument("--version", action="version", version="%(prog)s " + __version__)
    sub = parser.add_subparsers(dest="cmd")

    lst = sub.add_parser("list", help="show what would be woven")
    _add_source_args(lst)
    what = lst.add_mutually_exclusive_group()
    what.add_argument("--targets", action="store_true", help="target classes (default)")
    what.add_argument("--classes", action="store_true",
                      help="every modelled class, with the reason it is or is not a target")
    lst.add_argument("--json", action="store_true", help="JSON output")

    gen = sub.add_parser("gen", help="run the full pipeline and write the woven sources")
    _add_source_args(gen)
    gen.add_argument("-o", "--out-dir", help="output directory (default: the config's out_dir)")
    gen.add_argument("--verify", choices=["full", "syntax", "off"],
                     help="verification level (default: the config's verify)")

    sub.add_parser("schema", help="print the JSON Schema of sv-weave.yaml")

    rep = sub.add_parser("report", help="render a weave-manifest.json as Markdown")
    rep.add_argument("manifest", help="path to weave-manifest.json")
    return parser


def _load_config(args):
    from .config import Config, load_config
    path = args.config
    if path is None and os.path.isfile("sv-weave.yaml"):
        path = "sv-weave.yaml"
    cfg = load_config(path) if path else Config()
    if getattr(args, "binding", None):
        cfg.binding = list(args.binding)
    return cfg


def _cli_spec(args):
    """Sources given on the command line (the config's own come on top in run())."""
    from .filelist import SourceSpec, read_filelist

    spec = SourceSpec()
    for fl in args.filelists:
        spec.extend(read_filelist(fl))
    spec.extend(SourceSpec(files=[os.path.abspath(f) for f in args.files],
                           incdirs=[os.path.abspath(d) for d in args.incdirs]))
    for d in args.defines:
        name, _, val = d.partition("=")
        spec.defines[name] = val if val else None
    return spec


def _bindings(cfg):
    from . import plugin
    return [plugin.find(plugin.BINDING_GROUP, n, cfg.plugin_dirs())() for n in cfg.bindings]


def _source_spec(args, cfg, bindings):
    spec = cfg.source_spec()
    spec.extend(_cli_spec(args))
    if not args.no_runtime:
        user_names = {os.path.basename(f) for f in spec.files}
        rt = []
        for b in bindings:
            rt.extend(f for f in b.sv_runtime_files()
                      if f not in rt and os.path.basename(f) not in user_names)
        spec.files[:0] = rt
    return spec


def cmd_list(args) -> int:
    from .frontend.loader import load
    from .frontend.model import build_model
    from .select import select

    cfg = _load_config(args)
    bindings = _bindings(cfg)
    loaded = load(_source_spec(args, cfg, bindings))
    model = build_model(loaded)
    sel = select(model, cfg, bindings)

    if args.classes:
        rows = []
        tmap = {t.cls.qname: t for t in sel.targets}
        for c in model.classes():
            t = tmap.get(c.qname)
            rows.append({
                "class": c.qname,
                "target": t is not None,
                "reason": ("binding %s" % t.binding) if t else sel.skipped.get(c.qname, ""),
                "loc": str(c.loc) if c.loc else None,
            })
        if args.json:
            print(json.dumps({"classes": rows}, indent=2))
        else:
            w = max([len(r["class"]) for r in rows] + [5])
            for r in rows:
                print("%s %-*s  %s" % ("*" if r["target"] else " ", w, r["class"], r["reason"]))
        return 0

    rows = []
    for t in sel.targets:
        rows.append({
            "class": t.cls.qname,
            "package": t.cls.package,
            "binding": t.binding,
            "root": t.root.qname,
            "abstract": t.cls.is_abstract,
            "params": t.cls.params,
            "loc": str(t.cls.loc) if t.cls.loc else None,
        })
    if args.json:
        print(json.dumps({"targets": rows}, indent=2))
    else:
        if not rows:
            print("no target classes")
        w = max([len(r["class"]) for r in rows] + [5])
        for r in rows:
            print("%-*s  %s  %s" % (w, r["class"], r["binding"], r["loc"] or ""))
    return 0


def _print_diags(diags):
    for d in diags:
        print(str(d), file=sys.stderr)


def cmd_gen(args) -> int:
    from .run import run

    cfg = _load_config(args)
    res = run(cfg, spec=_cli_spec(args), out_dir=args.out_dir, add_runtime=not args.no_runtime,
              verify=args.verify)
    _print_diags(res.diags)
    n_cls = len(res.woven)
    print("sv-weave: %d woven class%s in %d package%s -> %s (%d file%s changed; verify: %s)" % (
        n_cls, "" if n_cls == 1 else "es", len(res.packages), "" if len(res.packages) == 1 else "s",
        res.out_dir, len(res.changed), "" if len(res.changed) == 1 else "s", res.verify_status))
    return 0


def cmd_report(args) -> int:
    from .report import render_report

    with open(args.manifest) as fp:
        m = json.load(fp)
    sys.stdout.write(render_report(m))
    return 0


def main(argv: Optional[List[str]] = None) -> int:
    parser = get_parser()
    args = parser.parse_args(argv)
    if args.cmd is None:
        parser.print_help()
        return 1
    try:
        if args.cmd == "list":
            return cmd_list(args)
        if args.cmd == "gen":
            return cmd_gen(args)
        if args.cmd == "report":
            return cmd_report(args)
        if args.cmd == "schema":
            from .config import json_schema
            print(json.dumps(json_schema(), indent=2))
            return 0
    except SvWeaveError as e:
        print(str(e), file=sys.stderr)
        return 1
    except OSError as e:
        print("sv-weave: %s" % e, file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
