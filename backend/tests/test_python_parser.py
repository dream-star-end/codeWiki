import pytest

pytest.importorskip("tree_sitter_language_pack")

from app.services.parsers import parse_python_file


def test_python_parser_extracts_symbols(tmp_path):
    code = """
class Foo:
    def method(self):
        pass

def func():
    return 1
"""
    file_path = tmp_path / "sample.py"
    file_path.write_text(code, encoding="utf-8")

    symbols, imports = parse_python_file(str(file_path))
    kinds = {s.kind for s in symbols}
    names = {s.name for s in symbols}

    assert "class" in kinds
    assert "function" in kinds
    assert "Foo" in names
    assert "func" in names
    assert imports == []
