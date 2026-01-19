import pytest

pytest.importorskip("tree_sitter_language_pack")

from app.services.parsers import parse_java_file


def test_java_parser_extracts_symbols(tmp_path):
    code = """
public class Hello {
    public void say() {}
}
"""
    file_path = tmp_path / "Hello.java"
    file_path.write_text(code, encoding="utf-8")

    symbols, imports = parse_java_file(str(file_path))
    kinds = {s.kind for s in symbols}
    names = {s.name for s in symbols}

    assert "class" in kinds
    assert "method" in kinds
    assert "Hello" in names
    assert "say" in names
    assert imports == []
