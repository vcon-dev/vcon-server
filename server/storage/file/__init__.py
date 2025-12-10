"""
File Storage Module

Provides local file system storage for vCon data with support for:
- UUID-based file organization
- Optional compression (gzip)
- Date-based directory structure
- Configurable file permissions
- File size limits
"""

import os
import json
import gzip
from glob import glob
from pathlib import Path
from typing import Optional
from lib.logging_utils import init_logger
from server.lib.vcon_redis import VconRedis
from datetime import datetime

logger = init_logger(__name__)

default_options = {
    "path": "/data/vcons",
    "organize_by_date": True,
    "compression": False,
    "max_file_size": 10485760,  # 10MB
    "file_permissions": 0o644,
    "dir_permissions": 0o755,
}


def _get_file_path(vcon_uuid: str, opts: dict, created_at: Optional[str] = None) -> Path:
    """
    Generate the file path for a vCon.

    If organize_by_date is True, files are stored in YYYY/MM/DD subdirectories.
    """
    base_path = Path(opts.get("path", default_options["path"]))
    extension = "json.gz" if opts.get("compression", False) else "json"

    if opts.get("organize_by_date", True) and created_at:
        try:
            dt = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
            date_path = dt.strftime("%Y/%m/%d")
            return base_path / date_path / f"{vcon_uuid}.{extension}"
        except (ValueError, AttributeError):
            pass

    return base_path / f"{vcon_uuid}.{extension}"


def _ensure_directory(file_path: Path, dir_permissions: int) -> None:
    """Ensure the parent directory exists with proper permissions."""
    file_path.parent.mkdir(parents=True, exist_ok=True)
    # Apply permissions to all directories in the path up to the base
    try:
        # Walk from the base path up to the parent directory
        base_path = file_path.anchor if file_path.is_absolute() else Path('.')
        for parent in file_path.parent.relative_to(base_path).parents:
            dir_to_chmod = base_path / parent
            if dir_to_chmod.exists():
                os.chmod(dir_to_chmod, dir_permissions)
        # Also chmod the immediate parent directory
        os.chmod(file_path.parent, dir_permissions)
    except Exception:
        pass  # May fail on some systems, not critical


def _find_vcon_file(vcon_uuid: str, opts: dict) -> Optional[Path]:
    """
    Find an existing vCon file by UUID.

    Searches both flat and date-organized directory structures.
    """
    base_path = Path(opts.get("path", default_options["path"]))
    compression = opts.get("compression", False)

    # Try both compressed and uncompressed extensions
    extensions = ["json.gz", "json"] if compression else ["json", "json.gz"]

    for ext in extensions:
        # Check flat structure first
        flat_path = base_path / f"{vcon_uuid}.{ext}"
        if flat_path.exists():
            return flat_path

        # Search date-organized directories
        pattern = str(base_path / "**" / f"{vcon_uuid}.{ext}")
        matches = glob(pattern, recursive=True)
        if matches:
            return Path(matches[0])

    return None


def save(vcon_uuid: str, opts: dict = None) -> None:
    """
    Save a vCon to file storage.

    Args:
        vcon_uuid: The UUID of the vCon to save
        opts: Storage options including:
            - path: Base directory for storage
            - organize_by_date: Whether to use YYYY/MM/DD subdirectories
            - compression: Whether to gzip compress the file
            - max_file_size: Maximum file size in bytes
            - file_permissions: Unix file permissions
            - dir_permissions: Unix directory permissions
    """
    if opts is None:
        opts = default_options

    logger.info("Saving vCon to file storage: %s", vcon_uuid)

    try:
        vcon_redis = VconRedis()
        vcon = vcon_redis.get_vcon(vcon_uuid)
        vcon_data = vcon.dumps()

        # Check file size limit
        max_size = opts.get("max_file_size", default_options["max_file_size"])
        vcon_size_bytes = len(vcon_data.encode("utf-8"))
        if vcon_size_bytes > max_size:
            raise ValueError(
                f"vCon data exceeds max file size: {vcon_size_bytes} bytes > {max_size} bytes"
            )

        # Get the file path
        created_at = getattr(vcon, "created_at", None)
        file_path = _get_file_path(vcon_uuid, opts, created_at)

        # Ensure directory exists
        dir_permissions = opts.get("dir_permissions", default_options["dir_permissions"])
        _ensure_directory(file_path, dir_permissions)

        # Write the file
        compression = opts.get("compression", default_options["compression"])
        file_permissions = opts.get("file_permissions", default_options["file_permissions"])

        if compression:
            with gzip.open(file_path, "wt", encoding="utf-8") as f:
                f.write(vcon_data)
        else:
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(vcon_data)

        # Set file permissions
        try:
            os.chmod(file_path, file_permissions)
        except OSError:
            pass  # May fail on some systems, not critical

        logger.info("file storage: saved vCon %s to %s", vcon_uuid, file_path)

    except Exception as e:
        logger.error("file storage: failed to save vCon %s: %s", vcon_uuid, e)
        raise


def get(vcon_uuid: str, opts: dict = None) -> Optional[dict]:
    """
    Get a vCon from file storage by UUID.

    Args:
        vcon_uuid: The UUID of the vCon to retrieve
        opts: Storage options

    Returns:
        The vCon data as a dictionary, or None if not found
    """
    if opts is None:
        opts = default_options

    try:
        file_path = _find_vcon_file(vcon_uuid, opts)

        if file_path is None:
            logger.debug("file storage: vCon not found: %s", vcon_uuid)
            return None

        # Read the file (handle both compressed and uncompressed)
        if file_path.suffix == ".gz" or str(file_path).endswith(".json.gz"):
            with gzip.open(file_path, "rt", encoding="utf-8") as f:
                data = json.load(f)
        else:
            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)

        logger.info("file storage: retrieved vCon %s from %s", vcon_uuid, file_path)
        return data

    except Exception as e:
        logger.error("file storage: failed to get vCon %s: %s", vcon_uuid, e)
        return None


def delete(vcon_uuid: str, opts: dict = None) -> bool:
    """
    Delete a vCon from file storage.

    Args:
        vcon_uuid: The UUID of the vCon to delete
        opts: Storage options

    Returns:
        True if the file was deleted, False otherwise
    """
    if opts is None:
        opts = default_options

    try:
        file_path = _find_vcon_file(vcon_uuid, opts)

        if file_path is None:
            logger.debug("file storage: vCon not found for deletion: %s", vcon_uuid)
            return False

        file_path.unlink()
        logger.info("file storage: deleted vCon %s from %s", vcon_uuid, file_path)

        # Clean up empty parent directories
        _cleanup_empty_dirs(file_path.parent, Path(opts.get("path", default_options["path"])))

        return True

    except Exception as e:
        logger.error("file storage: failed to delete vCon %s: %s", vcon_uuid, e)
        return False


def _cleanup_empty_dirs(dir_path: Path, base_path: Path) -> None:
    """Remove empty directories up to the base path."""
    try:
        while dir_path != base_path and dir_path.is_dir():
            if any(dir_path.iterdir()):
                break  # Directory not empty
            dir_path.rmdir()
            dir_path = dir_path.parent
    except OSError:
        pass  # Ignore errors during cleanup


def exists(vcon_uuid: str, opts: dict = None) -> bool:
    """
    Check if a vCon exists in file storage.

    Args:
        vcon_uuid: The UUID of the vCon to check
        opts: Storage options

    Returns:
        True if the vCon exists, False otherwise
    """
    if opts is None:
        opts = default_options

    return _find_vcon_file(vcon_uuid, opts) is not None


def list_vcons(opts: dict = None, limit: int = 100, offset: int = 0) -> list[str]:
    """
    List vCon UUIDs in storage.

    Args:
        opts: Storage options
        limit: Maximum number of UUIDs to return
        offset: Number of UUIDs to skip

    Returns:
        List of vCon UUIDs
    """
    if opts is None:
        opts = default_options

    base_path = Path(opts.get("path", default_options["path"]))

    try:
        # Find all vCon files
        pattern_json = str(base_path / "**" / "*.json")
        pattern_json_gz = str(base_path / "**" / "*.json.gz")
        all_files = glob(pattern_json, recursive=True) + glob(pattern_json_gz, recursive=True)

        # Extract UUIDs from filenames
        uuids = []
        for file_path in all_files:
            filename = Path(file_path).name
            # Remove extensions (.json or .json.gz)
            uuid = filename.replace(".json.gz", "").replace(".json", "")
            uuids.append(uuid)

        # Sort by modification time (newest first)
        uuids_with_mtime = [
            (uuid, os.path.getmtime(f))
            for uuid, f in zip(uuids, all_files)
        ]
        uuids_with_mtime.sort(key=lambda x: x[1], reverse=True)

        # Apply pagination
        paginated = uuids_with_mtime[offset:offset + limit]
        return [uuid for uuid, _ in paginated]

    except Exception as e:
        logger.error("file storage: failed to list vCons: %s", e)
        return []
