"""Minimal solution source pack/unpack helpers for CLI compatibility."""

from __future__ import annotations

import os
import shutil
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
    dest_root = dest.resolve()
    with zipfile.ZipFile(zip_path, "r") as z:
        for info in z.infolist():
            member_path = Path(info.filename)
            if member_path.is_absolute():
                raise ValueError(f"Archive member {info.filename!r} has an absolute path")
            target_path = (dest / member_path).resolve()
            if dest_root not in target_path.parents and target_path != dest_root:
                raise ValueError(
                    f"Archive member {info.filename!r} would extract outside {dest_root}"
                )
            if info.is_dir():
                target_path.mkdir(parents=True, exist_ok=True)
                continue
            target_path.parent.mkdir(parents=True, exist_ok=True)
            with z.open(info) as source, target_path.open("wb") as target:
                shutil.copyfileobj(source, target)
    return str(dest)
