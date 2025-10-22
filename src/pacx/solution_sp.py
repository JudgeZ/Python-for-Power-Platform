
from __future__ import annotations

import os
import zipfile
from pathlib import Path


def unpack_to_source(solution_zip: str | os.PathLike[str], out_dir: str | os.PathLike[str]) -> str:
    """Unpack a solution zip into a SolutionPackager-like folder layout (approximate).

    - Puts customizations.xml and other root files under src/Other/
    - Puts WebResources/* under src/WebResources/
    This is a pragmatic transform for source control; adjust mapping as needed.
    """
    zpath = Path(solution_zip)
    outp = Path(out_dir)
    src = outp / "src"
    (src / "Other").mkdir(parents=True, exist_ok=True)
    (src / "WebResources").mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(zpath, "r") as z:
        for n in z.namelist():
            if n.lower().startswith("webresources/"):
                dest = src / "WebResources" / Path(n).relative_to("WebResources")
            elif n.lower().endswith("customizations.xml"):
                dest = src / "Other" / Path(n).name
            else:
                dest = src / "Other" / Path(n).name
            if n.endswith("/"):
                continue
            dest.parent.mkdir(parents=True, exist_ok=True)
            with z.open(n) as fin, open(dest, "wb") as fout:
                fout.write(fin.read())
    return str(src)


def pack_from_source(src_dir: str | os.PathLike[str], out_zip: str | os.PathLike[str]) -> str:
    """Pack a SolutionPackager-like source tree back into a solution zip (approximate)."""
    src = Path(src_dir)
    outp = Path(out_zip)
    outp.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(outp, "w", zipfile.ZIP_DEFLATED) as z:
        for root, _, files in os.walk(src):
            for f in files:
                full = Path(root) / f
                rel = full.relative_to(src)
                # Map back: WebResources/* -> WebResources/* ; Other/* -> root
                if str(rel).startswith("WebResources/"):
                    arc = str(rel)
                else:
                    arc = Path(str(rel).replace("Other/", "")).name
                z.write(full, arcname=arc)
    return str(outp)
