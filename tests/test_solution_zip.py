from __future__ import annotations

import zipfile
from pathlib import Path

from pacx.solution_sp import pack_from_source, unpack_to_source


def test_unpack_and_pack_solution(tmp_path):
    sol = tmp_path / "solution.zip"
    with zipfile.ZipFile(sol, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("WebResources/new_/script.js", "console.log('hi')")
        z.writestr("Workflows/sample.xaml", "<xaml />")
        z.writestr("customizations.xml", "<root />")

    src_dir = unpack_to_source(str(sol), tmp_path)
    assert (Path(src_dir) / "WebResources" / "new_" / "script.js").exists()
    assert (Path(src_dir) / "Workflows" / "sample.xaml").exists()

    repacked = tmp_path / "repacked.zip"
    pack_from_source(src_dir, repacked)
    with zipfile.ZipFile(repacked, "r") as z:
        names = set(z.namelist())
    assert "WebResources/new_/script.js" in names
    assert "Workflows/sample.xaml" in names
