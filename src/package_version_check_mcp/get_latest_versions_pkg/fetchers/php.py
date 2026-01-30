"""PHP/Packagist package version fetcher using the Packagist v2 API."""

import re
from typing import Optional

import httpx

from ..structs import PackageVersionResult, Ecosystem
from ..utils.version_parser import parse_semver, compare_semver


def parse_php_version_hint(version_hint: Optional[str]) -> Optional[str]:
    """Parse a PHP version hint like 'php:8.1' to extract the version.

    Args:
        version_hint: Version hint in format 'php:X.Y' or just 'X.Y'

    Returns:
        The PHP version string (e.g., '8.1') or None if not parseable
    """
    if not version_hint:
        return None

    # Handle 'php:8.1' format
    if version_hint.lower().startswith("php:"):
        return version_hint[4:].strip()

    # Handle plain version like '8.1'
    if re.match(r"^\d+\.\d+", version_hint):
        return version_hint.strip()

    return None


def check_php_constraint(php_constraint: str, target_php_version: str) -> bool:
    """Check if a target PHP version satisfies the package's PHP constraint.

    The package's constraint (like '>=8.1' or '^8.1') specifies the minimum PHP version
    it requires. We check if the caller's PHP version meets this minimum requirement.

    Args:
        php_constraint: Composer constraint like '>=8.1', '^8.1', '~8.1', etc.
        target_php_version: The PHP version the caller is using (e.g., '8.1')

    Returns:
        True if the target PHP version satisfies the constraint
    """
    # Handle common constraint formats
    # Remove any spaces
    constraint = php_constraint.replace(" ", "")

    # Handle OR constraints (e.g., '>=7.2 || >=8.0')
    # If any part matches, return True
    if "||" in constraint:
        parts = constraint.split("||")
        return any(check_php_constraint(part, target_php_version) for part in parts)

    # Handle AND constraints (comma-separated)
    if "," in constraint:
        parts = constraint.split(",")
        return all(check_php_constraint(part, target_php_version) for part in parts)

    # Extract operator and version
    match = re.match(r"^([<>=^~!]*)(.+)$", constraint)
    if not match:
        return True  # Can't parse, assume compatible

    operator = match.group(1)
    version_str = match.group(2)

    # Handle special version formats like '>=8.1.0-beta'
    # Extract just the numeric part before any prerelease suffix
    version_str = re.split(r"[-@]", version_str)[0]

    # Use compare_semver for version comparison
    cmp = compare_semver(target_php_version, version_str)

    if operator in (">=", "^", "~"):
        # >= means target must be at least this version
        # ^ and ~ have more complex semantics but for PHP compatibility,
        # we just check if target meets the minimum
        return cmp >= 0
    elif operator == ">":
        return cmp > 0
    elif operator == "<=":
        return cmp <= 0
    elif operator == "<":
        return cmp < 0
    elif operator == "==" or operator == "=":
        return cmp == 0
    elif operator == "!=":
        return cmp != 0
    else:
        # No operator or unknown operator, assume minimum version requirement
        return cmp >= 0


async def fetch_php_version(
    package_name: str, version_hint: Optional[str] = None
) -> PackageVersionResult:
    """Fetch the latest stable version of a PHP/Packagist package.

    Uses the Packagist v2 API (repo.packagist.org/p2/) which returns
    minified package metadata.

    Args:
        package_name: The package name in 'vendor/package' format (e.g., 'monolog/monolog')
        version_hint: Optional PHP version hint like 'php:8.1' to filter versions
                     that are compatible with the specified PHP version

    Returns:
        PackageVersionResult with the latest stable version information

    Raises:
        Exception: If the package cannot be found or fetched
    """
    # Normalize package name (should be vendor/package)
    if "/" not in package_name:
        raise ValueError(
            f"Invalid PHP package name '{package_name}'. "
            "Expected format: 'vendor/package' (e.g., 'monolog/monolog')"
        )

    url = f"https://repo.packagist.org/p2/{package_name}.json"
    target_php_version = parse_php_version_hint(version_hint)

    async with httpx.AsyncClient(timeout=10.0) as client:
        response = await client.get(
            url,
            headers={
                "User-Agent": "package-version-check-mcp/1.0"
            },
        )
        response.raise_for_status()
        data = response.json()

        packages = data.get("packages", {})
        versions_list = packages.get(package_name, [])

        if not versions_list:
            raise ValueError(f"No versions found for package '{package_name}'")

        # The v2 API returns versions in a minified format.
        # The first entry has full data, subsequent entries only have changed fields.
        # We need to "expand" the data by carrying forward unchanged fields.
        # For our purposes, we mainly care about version, time, and require.php

        latest_version = None
        latest_time = None

        # Track the "current" full record as we iterate
        current_record = {}

        for version_data in versions_list:
            # Merge with current record (version_data overrides)
            current_record = {**current_record, **version_data}

            version = current_record.get("version", "")

            # Skip non-stable versions (those with prerelease suffix)
            _, prerelease = parse_semver(version)
            if prerelease:
                continue

            # Check PHP version compatibility if a hint was provided
            if target_php_version:
                require = current_record.get("require", {})
                php_constraint = require.get("php", "")
                if php_constraint and not check_php_constraint(
                    php_constraint, target_php_version
                ):
                    continue

            # Take the first stable version that matches (they're ordered newest first)
            latest_version = version
            latest_time = current_record.get("time")
            break

        if not latest_version:
            if target_php_version:
                raise ValueError(
                    f"No stable version found for package '{package_name}' "
                    f"compatible with PHP {target_php_version}"
                )
            raise ValueError(f"No stable version found for package '{package_name}'")

        return PackageVersionResult(
            ecosystem=Ecosystem.PHP,
            package_name=package_name,
            latest_version=latest_version,
            digest=None,  # Not returning digest as per requirements
            published_on=latest_time,
        )
