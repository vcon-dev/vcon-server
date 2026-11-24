"""Guard the conserver image's ffmpeg packages.

`vcon` 0.9.2 requires the PyPI package `ffmpeg`, which is empty and, installed next to
ffmpeg-python, empties `ffmpeg/__init__.py`. Then `ffmpeg.probe` is missing and transcription
fails. The image is built by `uv sync --frozen` (docker/Dockerfile), so the lock and the
installed environment both have to keep `ffmpeg` out.
"""
import importlib.metadata as md
import pathlib
import tomllib

import pytest

LOCK = pathlib.Path(__file__).resolve().parents[1] / "uv.lock"


def test_empty_ffmpeg_distribution_not_installed():
    with pytest.raises(md.PackageNotFoundError):
        md.distribution("ffmpeg")


def test_ffmpeg_module_has_probe():
    import ffmpeg
    assert hasattr(ffmpeg, "probe")


def test_lock_never_installs_ffmpeg():
    lock = tomllib.loads(LOCK.read_text())
    for pkg in lock["package"]:
        for dep in pkg.get("dependencies", []):
            if dep["name"] == "ffmpeg":
                assert dep.get("marker") == "sys_platform == 'never'", pkg["name"]
