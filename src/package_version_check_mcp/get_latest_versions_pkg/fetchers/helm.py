"""Helm chart version fetcher."""

from typing import Optional
import urllib.parse
import httpx
import tempfile
import os
import asyncio
import json
import functools

from docker_registry_client_async import DockerRegistryClientAsync, ImageName

from ..structs import PackageVersionResult, Ecosystem
from ..utils.version_parser import compare_semver, parse_semver
from .docker import get_docker_image_tags, determine_latest_image_tag


def parse_helm_chart_name(package_name: str) -> tuple[str, str, str]:
    """Parse a Helm chart name into its components.

    Supports two formats:
    1. ChartMuseum URL: "https://host/path/chart-name"
    2. OCI reference: "oci://host/path/chart-name"

    Args:
        package_name: The Helm chart reference

    Returns:
        A tuple of (registry_type, registry_url, chart_name)
        - registry_type: Either "chartmuseum" or "oci"
        - registry_url: The base URL for the registry (without chart name)
        - chart_name: The name of the chart

    Raises:
        ValueError: If the chart name format is invalid
    """
    if package_name.startswith("oci://"):
        # OCI format: oci://host/path/chart-name
        rest = package_name[6:]  # Remove "oci://"
        if "/" not in rest:
            raise ValueError(
                f"Invalid Helm OCI chart reference: '{package_name}'. "
                "Expected format: 'oci://host/path/chart-name'"
            )
        # Split to get registry and chart path
        last_slash = rest.rfind("/")
        registry_url = rest[:last_slash]
        chart_name = rest[last_slash + 1:]

        if not registry_url or not chart_name:
            raise ValueError(
                f"Invalid Helm OCI chart reference: '{package_name}'. "
                "Expected format: 'oci://host/path/chart-name'"
            )

        return "oci", registry_url, chart_name

    elif package_name.startswith("https://") or package_name.startswith("http://"):
        # ChartMuseum format: https://host/path/chart-name
        # We need to extract chart name from the end of the URL
        parsed = urllib.parse.urlparse(package_name)
        path = parsed.path.rstrip("/")

        if not path or "/" not in path:
            raise ValueError(
                f"Invalid Helm ChartMuseum URL: '{package_name}'. "
                "Expected format: 'https://host/path/chart-name'"
            )

        # Extract chart name from the last segment
        last_slash = path.rfind("/")
        chart_name = path[last_slash + 1:]
        base_path = path[:last_slash]

        if not chart_name:
            raise ValueError(
                f"Invalid Helm ChartMuseum URL: '{package_name}'. "
                "Expected format: 'https://host/path/chart-name'"
            )

        # Reconstruct the base registry URL
        registry_url = f"{parsed.scheme}://{parsed.netloc}{base_path}"

        return "chartmuseum", registry_url, chart_name

    else:
        raise ValueError(
            f"Invalid Helm chart reference: '{package_name}'. "
            "Expected format: 'https://host/path/chart-name' (ChartMuseum) or 'oci://host/path/chart-name' (OCI)"
        )


async def fetch_helm_chart_version(
    package_name: str, version_hint: Optional[str] = None
) -> PackageVersionResult:
    """Fetch the latest version of a Helm chart.

    Supports both ChartMuseum (https://) and OCI (oci://) registries.

    Args:
        package_name: The Helm chart reference in one of these formats:
            - ChartMuseum: "https://host/path/chart-name"
            - OCI: "oci://host/path/chart-name"
        version_hint: Optional version hint for compatibility matching

    Returns:
        PackageVersionResult with the latest version information

    Raises:
        Exception: If the chart cannot be found or fetched
    """
    registry_type, registry_url, chart_name = parse_helm_chart_name(package_name)

    if registry_type == "oci":
        return await fetch_helm_oci_version(registry_url, chart_name, package_name, version_hint)
    else:
        return await fetch_helm_chartmuseum_version(registry_url, chart_name, package_name)


async def fetch_helm_chartmuseum_version(
    registry_url: str, chart_name: str, original_package_name: str
) -> PackageVersionResult:
    """Fetch the latest version of a Helm chart from a ChartMuseum-compatible registry.

    Uses yq (fast Go-based YAML processor) to extract only the needed chart from large index.yaml files.

    Args:
        registry_url: The base URL of the ChartMuseum registry
        chart_name: The name of the chart
        original_package_name: The original package name for the result

    Returns:
        PackageVersionResult with the latest version information

    Raises:
        Exception: If the chart cannot be found or fetched
    """
    # ChartMuseum serves index.yaml at the registry root
    index_url = f"{registry_url}/index.yaml"

    # Stream the YAML file directly to disk to avoid loading potentially large files (20MB+)
    # into memory
    temp_file = None
    try:
        async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
            async with client.stream('GET', index_url) as response:
                response.raise_for_status()

                # Create temp file and stream response to it
                temp_file = tempfile.NamedTemporaryFile(mode='wb', suffix='.yaml', delete=False)
                async for chunk in response.aiter_bytes(chunk_size=8192):
                    temp_file.write(chunk)
                temp_file.close()

        # Use yq to extract only the specific chart (much faster than parsing entire YAML)
        chart_versions = await _extract_helm_chart_with_yq(temp_file.name, chart_name)

        if not chart_versions:
            raise Exception(f"Chart '{chart_name}' not found in repository at {registry_url}")

        # Filter out deprecated charts and find the latest semantic version
        latest_version = None
        latest_digest = None
        latest_created = None

        for version_entry in chart_versions:
            # Skip deprecated charts
            if version_entry.get("deprecated", False):
                continue

            version = version_entry.get("version")
            if not version:
                continue

            # Skip prerelease versions
            _, prerelease = parse_semver(version)
            if prerelease:
                continue

            # Use semantic version comparison to find the latest
            if latest_version is None or compare_semver(version, latest_version) > 0:
                latest_version = version
                latest_digest = version_entry.get("digest")
                latest_created = version_entry.get("created")

        if not latest_version:
            raise Exception(f"No non-deprecated stable versions found for chart '{chart_name}'")

        return PackageVersionResult(
            ecosystem=Ecosystem.Helm,
            package_name=original_package_name,
            latest_version=latest_version,
            digest=latest_digest,
            published_on=latest_created,
        )
    finally:
        # Clean up temp file
        if temp_file:
            try:
                os.unlink(temp_file.name)
            except Exception:
                pass


async def fetch_helm_oci_version(
    registry_url: str, chart_name: str, original_package_name: str, version_hint: Optional[str] = None
) -> PackageVersionResult:
    """Fetch the latest version of a Helm chart from an OCI registry.

    Reuses the Docker registry client to query OCI registries.

    Args:
        registry_url: The registry host and path (without oci:// prefix)
        chart_name: The name of the chart
        original_package_name: The original package name for the result
        version_hint: Optional version hint for compatibility matching

    Returns:
        PackageVersionResult with the latest version information

    Raises:
        Exception: If the chart cannot be found or fetched
    """
    # Construct the full OCI image reference
    # OCI Helm charts are stored as OCI artifacts, queryable like Docker images
    full_image_name = f"{registry_url}/{chart_name}"

    # Parse as a Docker image name
    image_name = ImageName.parse(full_image_name)

    async with DockerRegistryClientAsync() as registry_client:
        # Get all available tags (versions)
        tags = await get_docker_image_tags(image_name, registry_client)

        if not tags:
            raise Exception(f"No versions found for Helm chart '{original_package_name}'")

        # Determine the latest compatible version using the same logic as Docker
        latest_tag = determine_latest_image_tag(tags, version_hint)

        if not latest_tag:
            hint_msg = f" compatible with '{version_hint}'" if version_hint else ""
            raise Exception(f"No valid version tags{hint_msg} found for Helm chart '{original_package_name}'")

        # Get the manifest digest for this tag
        image_with_tag = image_name.clone()
        image_with_tag.set_tag(latest_tag)

        try:
            manifest = await registry_client.head_manifest(image_with_tag)
            digest = str(manifest.digest) if manifest.digest else None
        except Exception:
            digest = None

        return PackageVersionResult(
            ecosystem=Ecosystem.Helm,
            package_name=original_package_name,
            latest_version=latest_tag,
            digest=digest,
            published_on=None,  # OCI registries don't expose this easily
        )


async def _extract_helm_chart_with_yq(yaml_file_path: str, chart_name: str) -> list[dict]:
    """Extract a specific chart's versions from Helm index.yaml using yq (fast Go-based tool).

    This avoids parsing the entire YAML file (which can be 20MB+) by using yq to extract
    only the specific chart we need.

    Args:
        yaml_file_path: Path to the index.yaml file on disk
        chart_name: The name of the chart to extract

    Returns:
        List of version dictionaries for the chart
    """
    try:
        # Use yq to extract just the chart we need and output as JSON
        # yq syntax: .entries["chart-name"] -o json
        process = await asyncio.create_subprocess_exec(
            'yq',
            f'.entries["{chart_name}"]',
            '-o', 'json',
            yaml_file_path,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )

        stdout, _stderr = await process.communicate()

        if process.returncode != 0:
            # yq not found or error - return empty list
            return []

        # Parse the JSON output
        result = json.loads(stdout.decode())

        # yq returns null if the key doesn't exist
        if result is None:
            return []

        return result if isinstance(result, list) else []

    except FileNotFoundError:
        # yq not installed - return empty list to trigger fallback
        return []
    except Exception:
        return []
