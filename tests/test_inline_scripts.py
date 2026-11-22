"""Inline page scripts must parse. A single unescaped apostrophe in
admin.html once left the whole admin page blank: the module never ran,
so neither the sign-in box nor the panel was ever shown."""

import re
import shutil
import subprocess
from pathlib import Path

import pytest

STATIC = Path(__file__).resolve().parents[1] / "src" / "ca_roads_demo" / "static"
PAGES = ["admin.html", "watch.html"]
SCRIPT = re.compile(r"<script(?P<attrs>[^>]*)>(?P<body>.*?)</script>", re.S)


def inline_scripts(page: str) -> list[str]:
    out = []
    for m in SCRIPT.finditer((STATIC / page).read_text()):
        attrs = m["attrs"]
        if "src=" in attrs or "application/" in attrs:
            continue
        if m["body"].strip():
            out.append(m["body"])
    return out


@pytest.mark.parametrize("page", PAGES)
def test_page_has_inline_scripts(page):
    assert inline_scripts(page)


@pytest.mark.skipif(shutil.which("node") is None, reason="node not installed")
@pytest.mark.parametrize("page", PAGES)
def test_inline_scripts_parse(page, tmp_path):
    for i, body in enumerate(inline_scripts(page)):
        f = tmp_path / f"{page}.{i}.mjs"
        f.write_text(body)
        r = subprocess.run(["node", "--check", str(f)], capture_output=True, text=True)
        assert r.returncode == 0, f"{page} inline script {i}: {r.stderr[-600:]}"
