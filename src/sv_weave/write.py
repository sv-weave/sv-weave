"""Stage 8, Write: put the outputs in ``out_dir`` (design §7.4).

Files whose content is unchanged are not rewritten, so incremental simulator builds
stay warm. Files a previous run wrote (per its manifest) that this run no longer
produces are removed.
"""
import json
import os
from typing import Dict, List

MANIFEST = "weave-manifest.json"


def write_if_changed(path: str, text: str) -> bool:
    if os.path.isfile(path):
        with open(path) as fp:
            if fp.read() == text:
                return False
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w") as fp:
        fp.write(text)
    os.replace(tmp, path)
    return True


def previous_files(out_dir: str) -> List[str]:
    path = os.path.join(out_dir, MANIFEST)
    try:
        with open(path) as fp:
            return list(json.load(fp).get("files", {}).get("generated", []))
    except (OSError, ValueError):
        return []


def write_outputs(out_dir: str, files: Dict[str, str]) -> List[str]:
    """Writes ``{file name: text}`` into ``out_dir``; returns the names that changed."""
    os.makedirs(out_dir, exist_ok=True)
    stale = set(previous_files(out_dir)) - set(files)
    for name in sorted(stale):
        p = os.path.join(out_dir, name)
        if os.path.isfile(p):
            os.remove(p)
    changed = []
    for name in files:
        if write_if_changed(os.path.join(out_dir, name), files[name]):
            changed.append(name)
    return changed
