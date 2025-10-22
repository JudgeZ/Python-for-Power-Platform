"""Minimal solution source pack/unpack helpers for CLI compatibility."""

from __future__ import annotations

import os
import zipfile
from pathlib import Path


def pack_solution_folder(src_dir: str | os.PathLike[str], out_zip: str | os.PathLike[str]) -> str:
    src = Path(src_dir)
    outp = Path(out_zip)
    outp.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(outp, "w", zipfile.ZIP_DEFLATED) as z:
        for root, _, files in os.walk(src):
            for name in files:
                full = Path(root) / name
                z.write(full, arcname=str(full.relative_to(src)))
    return str(outp)


def unpack_solution_zip(zip_path: str | os.PathLike[str], out_dir: str | os.PathLike[str]) -> str:
    dest = Path(out_dir)
    dest.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(zip_path, "r") as z:
        z.extractall(dest)
    return str(dest)
