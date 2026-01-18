"""Version information for the vCon server.

This module provides version information that is injected at Docker build time.
When running locally (outside Docker), it falls back to "dev" values.

Environment Variables (set during Docker build):
    VCON_SERVER_VERSION: CalVer version (e.g., "2026.01.16.1")
    VCON_SERVER_GIT_COMMIT: Git commit hash (short, e.g., "a1b2c3d")
    VCON_SERVER_BUILD_TIME: ISO timestamp of when the image was built

Usage:
    from version import get_version, get_version_info
    
    # Get just the version string
    version = get_version()  # "2026.01.16.1" or "dev"
    
    # Get full version info dict
    info = get_version_info()
    # {
    #     "version": "2026.01.16.1",
    #     "git_commit": "a1b2c3d",
    #     "build_time": "2026-01-16T10:30:00Z"
    # }
"""

import os
from typing import Dict


# Version info from environment (injected at Docker build time)
VERSION = os.environ.get("VCON_SERVER_VERSION", "dev")
GIT_COMMIT = os.environ.get("VCON_SERVER_GIT_COMMIT", "unknown")
BUILD_TIME = os.environ.get("VCON_SERVER_BUILD_TIME", "unknown")


def get_version() -> str:
    """Get the current version string.
    
    Returns:
        The CalVer version string (e.g., "2026.01.16.1") or "dev" if not set.
    """
    return VERSION


def get_git_commit() -> str:
    """Get the git commit hash.
    
    Returns:
        The short git commit hash (e.g., "a1b2c3d") or "unknown" if not set.
    """
    return GIT_COMMIT


def get_build_time() -> str:
    """Get the build timestamp.
    
    Returns:
        ISO timestamp of when the image was built, or "unknown" if not set.
    """
    return BUILD_TIME


def get_version_info() -> Dict[str, str]:
    """Get complete version information as a dictionary.
    
    Returns:
        Dictionary containing version, git_commit, and build_time.
    """
    return {
        "version": VERSION,
        "git_commit": GIT_COMMIT,
        "build_time": BUILD_TIME,
    }


def get_version_string() -> str:
    """Get a formatted version string for display.
    
    Returns:
        Formatted string like "vCon Server v2026.01.16.1 (a1b2c3d)"
    """
    if VERSION == "dev":
        return "vCon Server (development)"
    return f"vCon Server v{VERSION} ({GIT_COMMIT})"
