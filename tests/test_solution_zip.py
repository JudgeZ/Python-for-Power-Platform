from __future__ import annotations
from typer.testing import CliRunner
from pacx.cli import app

runner = CliRunner()

def test_solution_zip_unzip(tmp_path):
    src = tmp_path / "folder"
    src.mkdir()
    (src / "a.txt").write_text("hello")
    zpath = tmp_path / "out.zip"

    result = runner.invoke(app, ["solution", "zip", "--folder", str(src), "--file", str(zpath)])
    assert result.exit_code == 0 and zpath.exists()

    dest = tmp_path / "unpacked"
    result = runner.invoke(app, ["solution", "unzip", "--file", str(zpath), "--folder", str(dest)])
    assert result.exit_code == 0 and (dest / "a.txt").exists()
