from __future__ import annotations

import zipfile
from pathlib import Path

from pacx.solution_source import pack_solution_folder, unpack_solution_zip
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
    assert "customizations.xml" in names
    assert "Other/customizations.xml" not in names


def test_pack_and_unpack_helpers(tmp_path):
    src = tmp_path / "src"
    (src / "nested").mkdir(parents=True)
    (src / "nested" / "file.txt").write_text("hello", encoding="utf-8")

    archive_path = pack_solution_folder(src, tmp_path / "packed.zip")
    assert Path(archive_path).exists()

    dest_dir = unpack_solution_zip(archive_path, tmp_path / "out")
    unpacked = Path(dest_dir) / "nested" / "file.txt"
    assert unpacked.exists()
    assert unpacked.read_text(encoding="utf-8") == "hello"
