"""Utilities for parsing and comparing semantic versions."""

import re
from typing import Optional
from packaging.version import Version, InvalidVersion


def parse_semver(version: str) -> tuple[list[int], str]:
    """Parse a semantic version into numeric parts and prerelease suffix.

    Uses the standard packaging.version.Version for parsing. Invalid versions
    are marked with "invalid" prerelease so they get filtered out.

    Args:
        version: The version string to parse (e.g., "1.2.3", "v2.0.0-beta.1")

    Returns:
        A tuple of (numeric_parts, prerelease) where:
        - numeric_parts: List of integers from the version (e.g., [1, 2, 3])
        - prerelease: Empty string for stable versions, "prerelease" for prereleases,
                     or "invalid" for unparseable versions
    """
    try:
        parsed = Version(version)
        numeric_parts = list(parsed.release)
        prerelease = "" if not parsed.is_prerelease else "prerelease"
        return numeric_parts, prerelease
    except InvalidVersion:
        # Invalid versions are treated as prereleases so they get filtered out
        return [], "invalid"


def compare_semver(version1: str, version2: str) -> int:
    """Compare two semantic version strings.

    Uses the standard packaging.version.Version for comparison.

    Args:
        version1: First version string
        version2: Second version string

    Returns:
        -1 if version1 < version2
        0 if version1 == version2
        1 if version1 > version2
    """
    try:
        v1 = Version(version1)
        v2 = Version(version2)

        if v1 < v2:
            return -1
        elif v1 > v2:
            return 1
        return 0
    except InvalidVersion:
        # If either version is invalid, treat as equal
        return 0


def parse_docker_tag(tag: str) -> Optional[dict]:
    """Parse a Docker tag into its components.

    Args:
        tag: The Docker tag to parse

    Returns:
        A dictionary with parsed components, or None if the tag is invalid:
        - release: List of integer version parts
        - suffix: String suffix (e.g., 'alpine', 'slim')
        - prerelease: Prerelease identifier
        - original: The original tag
    """
    if not tag:
        return None

    # Ignore special tags like 'latest', 'stable', 'edge', etc.
    if tag.lower() in ('latest', 'stable', 'edge', 'nightly', 'dev', 'master', 'main'):
        return None

    # Ignore commit hashes (7-40 hex characters, but not purely numeric)
    if re.match(r'^[a-f0-9]{7,40}$', tag, re.IGNORECASE) and not re.match(r'^[0-9]+$', tag):
        return None

    # Remove leading 'v'
    clean_tag = re.sub(r'^v', '', tag)

    # Split on first '-' to separate version from suffix
    parts = clean_tag.split('-', 1)
    prefix = parts[0]
    suffix = parts[1] if len(parts) > 1 else ''

    # Match version pattern: numeric parts with optional prerelease
    match = re.match(r'^(?P<version>\d+(?:\.\d+)*)(?P<prerelease>\w*)$', prefix)
    if not match:
        return None

    version_str = match.group('version')
    prerelease = match.group('prerelease')

    # Ignore tags where version is only a large number (>=1000) without dots
    # This filters out date-based tags like 20260202, 20250115, etc.
    if '.' not in version_str:
        try:
            if int(version_str) >= 1000:
                return None
        except ValueError:
            pass

    # Split version into numeric parts
    release = [int(x) for x in version_str.split('.')]

    return {
        'release': release,
        'suffix': suffix,
        'prerelease': prerelease,
        'original': tag
    }
