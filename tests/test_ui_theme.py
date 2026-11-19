"""The theme embeds the two background photos and still runs if they are missing."""

from capex.llm import repo_root
from capex.ui_theme import apply_theme


def test_backgrounds_are_embedded_when_the_assets_are_present():
    css = apply_theme(repo_root() / "assets")
    assert css.count("data:image/webp;base64") == 2


def test_missing_assets_do_not_raise(tmp_path):
    css = apply_theme(tmp_path)
    assert "data:image/webp;base64" not in css


def test_shipped_assets_are_under_150kb():
    root = repo_root() / "assets"
    limit = 150 * 1024
    shipped = [
        path
        for path in root.rglob("*")
        if path.is_file() and "source" not in path.relative_to(root).parts
    ]
    assert shipped
    for path in shipped:
        assert path.stat().st_size < limit, path.name
