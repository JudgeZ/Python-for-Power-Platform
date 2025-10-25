from __future__ import annotations

import os
import zipfile
from pathlib import Path

COMPONENT_MAP: dict[str, str] = {
    "WebResources": "WebResources",
    "CanvasApps": "CanvasApps",
    "Workflows": "Workflows",
    "Customizations": "Other",
    "PluginAssemblies": "PluginAssemblies",
    "Other": "Other",
}


def _resolve_destination(root: Path, src_root: Path) -> Path:
    if not root.parts:
        raise ValueError("Archive entry has no path components to unpack.")

    component, *remainder_parts = root.parts
    mapped = COMPONENT_MAP.get(component, "Other")
    remainder = Path(*remainder_parts) if remainder_parts else Path(root.name)
    candidate = (src_root / mapped / remainder).resolve(strict=False)

    try:
        candidate.relative_to(src_root)
    except ValueError:
        raise ValueError(
            f"Archive entry '{root.as_posix()}' would extract outside '{src_root}'."
        ) from None
    return candidate


def unpack_to_source(solution_zip: str | os.PathLike[str], out_dir: str | os.PathLike[str]) -> str:
    """Unpack a solution zip into a SolutionPackager-like folder layout."""

    zpath = Path(solution_zip)
    outp = Path(out_dir)
    src = outp / "src"
    for folder in set(COMPONENT_MAP.values()) | {"Other"}:
        (src / folder).mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(zpath, "r") as z:
        for n in z.namelist():
            if n.endswith("/"):
                continue
            rel = Path(n)
            dest = _resolve_destination(rel, src)
            dest.parent.mkdir(parents=True, exist_ok=True)
            with z.open(n) as fin, open(dest, "wb") as fout:
                fout.write(fin.read())
    return str(src)


ROOT_LEVEL_FILES = {"customizations.xml", "solution.xml", "solutionmanifest.xml"}


def pack_from_source(src_dir: str | os.PathLike[str], out_zip: str | os.PathLike[str]) -> str:
    """Pack a SolutionPackager-like source tree back into a solution zip."""

    src = Path(src_dir)
    outp = Path(out_zip)
    outp.parent.mkdir(parents=True, exist_ok=True)
    reverse_map = {v: k for k, v in COMPONENT_MAP.items()}
    with zipfile.ZipFile(outp, "w", zipfile.ZIP_DEFLATED) as z:
        for root, _, files in os.walk(src):
            for f in files:
                full = Path(root) / f
                rel = full.relative_to(src)
                if not rel.parts:
                    arc = f
                else:
                    component = rel.parts[0]
                    original = reverse_map.get(component, "Other")
                    remainder = Path(*rel.parts[1:]) if len(rel.parts) > 1 else Path(f)
                    if (
                        component == "Other"
                        and len(rel.parts) == 2
                        and rel.parts[1].lower() in ROOT_LEVEL_FILES
                    ):
                        arc = rel.parts[1]
                    else:
                        arc = str(Path(original) / remainder)
                z.write(full, arcname=arc)
    return str(outp)
