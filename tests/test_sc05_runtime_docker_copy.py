"""Protect SC05 source catalog availability in the Render Docker runtime."""
from pathlib import Path


def test_devstudio_dockerfile_includes_pinned_sc05_config():
    root=Path(__file__).resolve().parent.parent
    dockerfile=(root/"Dockerfile.devstudio-e2e").read_text(encoding="utf-8")
    catalog=root/"config/sc05_source_catalog_v1.json"
    assert catalog.is_file()
    assert "COPY config ./config" in dockerfile
    assert "config/" not in (root/".dockerignore").read_text(encoding="utf-8").splitlines()
