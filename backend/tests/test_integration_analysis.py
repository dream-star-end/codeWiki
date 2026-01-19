import pytest

pytest.importorskip("tree_sitter_language_pack")

from app.services.analysis import run_analysis
from app.services.db import read_summary, read_docs


def test_run_analysis_end_to_end(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()

    py_file = repo_root / "main.py"
    py_file.write_text("""
import os

def hello():
    return "hi"
""", encoding="utf-8")

    java_dir = repo_root / "src"
    java_dir.mkdir()
    java_file = java_dir / "App.java"
    java_file.write_text("""
public class App {
    public static void main(String[] args) {}
}
""", encoding="utf-8")

    repo_id = "test_repo"
    run_analysis(repo_id, str(repo_root), include=None, exclude=None)

    summary = read_summary(repo_id)
    docs = read_docs(repo_id)

    assert summary is not None
    assert "python" in summary.get("languages", [])
    assert "java" in summary.get("languages", [])
    assert isinstance(docs, list)
