"""Archive extraction for uploaded plugin packages.

Supports .zip archives. Extracts to a temporary directory and returns
the path. Only regular files and directories are extracted — symlinks
inside archives are preserved as symlinks so that check_symlinks can
detect them (issue #35), but extraction refuses paths that escape the
destination (zip-slip protection).
"""

from __future__ import annotations

import logging
import os
import shutil
import tempfile
import zipfile
from pathlib import Path

logger = logging.getLogger(__name__)

MAX_EXTRACTED_BYTES = 200 * 1024 * 1024  # 200 MB total extracted


def extract_plugin_archive(
    archive_path: Path,
    max_bytes: int = MAX_EXTRACTED_BYTES,
) -> Path:
    """Extract a .zip archive to a temporary directory.

    Returns the path to the extracted directory. Raises ValueError if
    the archive is not a valid zip or would exceed the size limit.
    """
    if not archive_path.exists():
        raise FileNotFoundError(f"Archive not found: {archive_path}")

    if not zipfile.is_zipfile(archive_path):
        raise ValueError(f"Not a valid zip archive: {archive_path}")

    extract_dir = Path(tempfile.mkdtemp(prefix="prism_lens_"))

    total_size = 0
    with zipfile.ZipFile(archive_path, "r") as zf:
        for info in zf.infolist():
            # Zip-slip protection
            target = (extract_dir / info.filename).resolve()
            if not str(target).startswith(str(extract_dir.resolve())):
                raise ValueError(f"Archive member escapes destination: {info.filename}")

            if info.is_dir():
                zf.extract(info, extract_dir)
                continue

            total_size += info.file_size
            if total_size > max_bytes:
                shutil.rmtree(extract_dir, ignore_errors=True)
                raise ValueError(
                    f"Archive exceeds maximum extracted size of {max_bytes} bytes"
                )
            zf.extract(info, extract_dir)

    logger.info("Extracted archive to %s", extract_dir)
    return extract_dir


def detect_plugin_root(extract_dir: Path) -> Path:
    """If the archive extracted a single top-level directory, return it.

    Otherwise return extract_dir itself (the plugin root is the extraction
    directory).
    """
    children = [c for c in extract_dir.iterdir() if not c.name.startswith(".")]
    if len(children) == 1 and children[0].is_dir():
        return children[0]
    return extract_dir


def cleanup_directory(path: Path) -> None:
    """Remove a temporary extraction directory."""
    if path.exists():
        shutil.rmtree(path, ignore_errors=True)