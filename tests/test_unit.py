import pytest
from package_version_check_mcp.get_latest_versions_pkg.fetchers.docker import determine_latest_image_tag
from package_version_check_mcp.get_latest_versions_pkg.fetchers.maven import parse_maven_package_name
from package_version_check_mcp.get_latest_versions_pkg.fetchers.terraform import (
    parse_terraform_provider_name,
    parse_terraform_module_name,
)


@pytest.mark.parametrize(
    "available_tags,tag_hint,expected_result,test_description",
    [
        # Test 1: Basic version upgrade
        (
            ['1.2.3', '1.2.4', '1.3.0', '2.0.0'],
            '1.2',
            '2.0.0',
            "Basic version upgrade - most specific, compatible version"
        ),
        # Test 2: Suffix compatibility (alpine)
        (
            ['1.2.3-alpine', '1.3.0-alpine', '1.3.0', '1.4.0-alpine'],
            '1.2-alpine',
            '1.4.0-alpine',
            "Suffix compatibility - should match -alpine suffix"
        ),
        # Test 3: No compatible versions
        (
            ['3.7.0', '3.8.0'],
            '3.7.0-alpine',
            None,
            "No compatible versions - no -alpine tags available"
        ),
        # Test 4: Prerelease handling
        (
            ['3.7.0', '3.7.0b1', '3.8.0b1', '3.8.0'],
            '3.7.0',
            '3.8.0',
            "Prerelease handling - prefer stable versions over prereleases"
        ),
        # Test 5: No hint provided
        (
            ['1.2.3', '2.0.0', '1.5.0', '1.5.0-alpine', '2.0.0-alpine'],
            None,
            '2.0.0',
            "No hint provided - return latest stable version, prefer no suffix"
        ),
        # Test 6: Commit hashes ignored
        (
            ['1.2.3', 'abc123def', '1.3.0', '0a1b2c3d4e5f6a7b8c9d0a1b2c3d4e5f6a7b8c9d'],
            '1.2',
            '1.3.0',
            "Commit hashes ignored - filter out hash-like tags"
        ),
        # Test 7: Special tags ignored (latest, stable, etc.)
        (
            ['latest', '1.2.3', 'stable', '1.3.0', 'nightly', '2.0.0', 'edge'],
            '1.2',
            '2.0.0',
            "Special tags ignored - filter out 'latest', 'stable', 'nightly', 'edge'"
        ),
        # Additional test cases for edge cases
        # Test 8: Empty tag list
        (
            [],
            '1.2',
            None,
            "Empty tag list - should return None"
        ),
        # Test 9: Tags with 'v' prefix
        (
            ['v1.2.3', 'v1.3.0', 'v2.0.0'],
            'v1.2',
            'v2.0.0',
            "Tags with 'v' prefix - should handle properly"
        ),
        # Test 10: Complex suffix matching
        (
            ['1.2.3-alpine3.18', '1.3.0-alpine3.18', '1.3.0-alpine3.19', '1.4.0-alpine3.18'],
            '1.2-alpine3.18',
            '1.4.0-alpine3.18',
            "Complex suffix matching - exact suffix match required"
        ),
        # Test 11: Prerelease with hint
        (
            ['3.7.0b1', '3.8.0b1', '3.8.0b2'],
            '3.7.0b1',
            '3.8.0b2',
            "Prerelease with prerelease hint - allow prerelease versions"
        ),
        # Test 12: No hint, only prereleases available
        (
            ['1.0.0rc1', '1.0.0rc2', '2.0.0b1'],
            None,
            '2.0.0b1',
            "No hint with only prereleases - return latest prerelease"
        ),
        # Test 13: Large number tags ignored (date-based tags like 20260202)
        (
            ['1.2.3', '20260202', '1.3.0', '20250115', '2.0.0'],
            '1.2',
            '2.0.0',
            "Large number tags ignored - filter out date-based tags like 20260202"
        ),
        # Test 14: Large number tags only
        (
            ['20260202', '20250115', '1000', '20240101'],
            None,
            None,
            "Large number tags only - should return None when all tags are large numbers"
        ),
        # Test 15: Small numbers without dots are allowed
        (
            ['1', '2', '10', '100', '999'],
            None,
            '999',
            "Small numbers without dots allowed - numbers <1000 are valid"
        ),
        # Test 16: Large numbers with dots are allowed
        (
            ['2024.1.15', '2025.1.15', '2026.2.2'],
            None,
            '2026.2.2',
            "Large numbers with dots allowed - semantic versions with large numbers are valid"
        ),
        # Test 17: Mixed large numbers with and without dots
        (
            ['1.2.3', '20260202', '2026.2.2', '1001', '2.0.0'],
            None,
            '2026.2.2',
            "Mixed large numbers - prefer valid semver over large numbers without dots"
        ),
    ],
)
def test_determine_latest_image_tag(available_tags, tag_hint, expected_result, test_description):
    """Test determine_latest_image_tag function with various inputs."""
    result = determine_latest_image_tag(available_tags, tag_hint)
    assert result == expected_result, f"Failed: {test_description}"


@pytest.mark.parametrize(
    "package_name,expected_registry,expected_group_id,expected_artifact_id,test_description",
    [
        # Test 1: Simple Maven Central package (no registry prefix)
        (
            "org.springframework:spring-core",
            "https://repo1.maven.org/maven2",
            "org.springframework",
            "spring-core",
            "Maven Central package - groupId:artifactId format"
        ),
        # Test 2: Package with custom registry
        (
            "https://maven.google.com:com.google.android:android",
            "https://maven.google.com",
            "com.google.android",
            "android",
            "Custom registry - full URL with https"
        ),
        # Test 3: Package with registry without https prefix
        (
            "repo.spring.io/release:org.springframework:spring-core",
            "https://repo.spring.io/release",
            "org.springframework",
            "spring-core",
            "Registry without https prefix - should add https"
        ),
        # Test 4: Package with http registry
        (
            "http://internal.repo:com.company:artifact",
            "http://internal.repo",
            "com.company",
            "artifact",
            "HTTP registry - should preserve http protocol"
        ),
        # Test 5: Registry with trailing slash
        (
            "https://maven.example.com/:org.example:mylib",
            "https://maven.example.com",
            "org.example",
            "mylib",
            "Registry with trailing slash - should remove trailing slash"
        ),
    ],
)
def test_parse_maven_package_name_success(package_name, expected_registry, expected_group_id, expected_artifact_id, test_description):
    """Test parse_maven_package_name with valid inputs."""
    registry, group_id, artifact_id = parse_maven_package_name(package_name)
    assert registry == expected_registry, f"Failed registry: {test_description}"
    assert group_id == expected_group_id, f"Failed group_id: {test_description}"
    assert artifact_id == expected_artifact_id, f"Failed artifact_id: {test_description}"


@pytest.mark.parametrize(
    "package_name,test_description",
    [
        # Test 1: Missing artifact ID
        (
            "org.springframework",
            "Missing artifact ID - only one part"
        ),
        # Test 2: Too many colons
        (
            "a:b:c:d",
            "Too many colons - four parts"
        ),
        # Test 3: Empty group ID
        (
            ":spring-core",
            "Empty group ID"
        ),
        # Test 4: Empty artifact ID
        (
            "org.springframework:",
            "Empty artifact ID"
        ),
        # Test 5: Empty package name
        (
            "",
            "Empty package name"
        ),
    ],
)
def test_parse_maven_package_name_invalid(package_name, test_description):
    """Test parse_maven_package_name with invalid inputs."""
    with pytest.raises(ValueError):
        parse_maven_package_name(package_name)


@pytest.mark.parametrize(
    "package_name,expected_registry,expected_namespace,expected_type,test_description",
    [
        # Test 1: Simple provider (namespace/type only, defaults to registry.terraform.io)
        (
            "hashicorp/aws",
            "registry.terraform.io",
            "hashicorp",
            "aws",
            "Simple provider - defaults to registry.terraform.io"
        ),
        # Test 2: Fully qualified with Terraform registry
        (
            "registry.terraform.io/hashicorp/google",
            "registry.terraform.io",
            "hashicorp",
            "google",
            "Fully qualified Terraform registry"
        ),
        # Test 3: OpenTofu registry
        (
            "registry.opentofu.org/hashicorp/random",
            "registry.opentofu.org",
            "hashicorp",
            "random",
            "OpenTofu registry - alternative registry"
        ),
        # Test 4: Third-party namespace
        (
            "integrations/github",
            "registry.terraform.io",
            "integrations",
            "github",
            "Third-party namespace provider"
        ),
        # Test 5: Custom private registry
        (
            "terraform.example.com/myorg/mycloud",
            "terraform.example.com",
            "myorg",
            "mycloud",
            "Custom private registry"
        ),
    ],
)
def test_parse_terraform_provider_name_success(package_name, expected_registry, expected_namespace, expected_type, test_description):
    """Test parse_terraform_provider_name with valid inputs."""
    registry, namespace, provider_type = parse_terraform_provider_name(package_name)
    assert registry == expected_registry, f"Failed registry: {test_description}"
    assert namespace == expected_namespace, f"Failed namespace: {test_description}"
    assert provider_type == expected_type, f"Failed provider_type: {test_description}"


@pytest.mark.parametrize(
    "package_name,test_description",
    [
        # Test 1: Missing type
        (
            "hashicorp",
            "Missing type - only one part"
        ),
        # Test 2: Too many slashes
        (
            "a/b/c/d",
            "Too many slashes - four parts"
        ),
        # Test 3: Empty namespace
        (
            "/aws",
            "Empty namespace"
        ),
        # Test 4: Empty type
        (
            "hashicorp/",
            "Empty type"
        ),
        # Test 5: Empty package name
        (
            "",
            "Empty package name"
        ),
        # Test 6: Fully qualified with empty parts
        (
            "registry.terraform.io//aws",
            "Fully qualified with empty namespace"
        ),
    ],
)
def test_parse_terraform_provider_name_invalid(package_name, test_description):
    """Test parse_terraform_provider_name with invalid inputs."""
    with pytest.raises(ValueError):
        parse_terraform_provider_name(package_name)


@pytest.mark.parametrize(
    "package_name,expected_registry,expected_namespace,expected_name,expected_provider,test_description",
    [
        # Test 1: Simple module name (no registry)
        (
            "terraform-aws-modules/vpc/aws",
            "registry.terraform.io",
            "terraform-aws-modules",
            "vpc",
            "aws",
            "Simple module name - defaults to registry.terraform.io"
        ),
        # Test 2: Fully qualified with registry
        (
            "registry.terraform.io/terraform-aws-modules/vpc/aws",
            "registry.terraform.io",
            "terraform-aws-modules",
            "vpc",
            "aws",
            "Fully qualified - explicit Terraform Registry"
        ),
        # Test 3: OpenTofu registry
        (
            "registry.opentofu.org/terraform-aws-modules/vpc/aws",
            "registry.opentofu.org",
            "terraform-aws-modules",
            "vpc",
            "aws",
            "OpenTofu registry - alternative registry"
        ),
        # Test 4: Azure module
        (
            "Azure/network/azurerm",
            "registry.terraform.io",
            "Azure",
            "network",
            "azurerm",
            "Azure module - different namespace and provider"
        ),
        # Test 5: Custom private registry
        (
            "terraform.example.com/myorg/mymodule/mycloud",
            "terraform.example.com",
            "myorg",
            "mymodule",
            "mycloud",
            "Custom private registry"
        ),
        # Test 6: Google Cloud module
        (
            "GoogleCloudPlatform/lb-http/google",
            "registry.terraform.io",
            "GoogleCloudPlatform",
            "lb-http",
            "google",
            "Google Cloud Platform module"
        ),
    ],
)
def test_parse_terraform_module_name_success(package_name, expected_registry, expected_namespace, expected_name, expected_provider, test_description):
    """Test parse_terraform_module_name with valid inputs."""
    registry, namespace, module_name, provider = parse_terraform_module_name(package_name)
    assert registry == expected_registry, f"Failed registry: {test_description}"
    assert namespace == expected_namespace, f"Failed namespace: {test_description}"
    assert module_name == expected_name, f"Failed module_name: {test_description}"
    assert provider == expected_provider, f"Failed provider: {test_description}"


@pytest.mark.parametrize(
    "package_name,test_description",
    [
        # Test 1: Missing provider (only two parts)
        (
            "terraform-aws-modules/vpc",
            "Missing provider - only two parts"
        ),
        # Test 2: Too many slashes
        (
            "a/b/c/d/e",
            "Too many slashes - five parts"
        ),
        # Test 3: Empty namespace
        (
            "/vpc/aws",
            "Empty namespace"
        ),
        # Test 4: Empty name
        (
            "terraform-aws-modules//aws",
            "Empty module name"
        ),
        # Test 5: Empty provider
        (
            "terraform-aws-modules/vpc/",
            "Empty provider"
        ),
        # Test 6: Empty package name
        (
            "",
            "Empty package name"
        ),
        # Test 7: Only one part
        (
            "terraform-aws-modules",
            "Only one part - missing name and provider"
        ),
        # Test 8: Fully qualified with empty parts
        (
            "registry.terraform.io/terraform-aws-modules//aws",
            "Fully qualified with empty module name"
        ),
    ],
)
def test_parse_terraform_module_name_invalid(package_name, test_description):
    """Test parse_terraform_module_name with invalid inputs."""
    with pytest.raises(ValueError):
        parse_terraform_module_name(package_name)


# ============================================================================
# PHP check_php_constraint tests
# ============================================================================

from package_version_check_mcp.get_latest_versions_pkg.fetchers.php import check_php_constraint


@pytest.mark.parametrize(
    "php_constraint,target_php_version,expected_result,test_description",
    [
        # Basic >= operator
        (">=8.1", "8.1", True, ">= operator - exact match"),
        (">=8.1", "8.2", True, ">= operator - higher version"),
        (">=8.1", "8.0", False, ">= operator - lower version"),
        (">=8.1", "9.0", True, ">= operator - next major version"),
        (">=7.4", "8.1", True, ">= operator - target much higher"),

        # Basic > operator
        (">8.1", "8.2", True, "> operator - higher version"),
        (">8.1", "8.1", False, "> operator - exact match should fail"),
        (">8.1", "8.0", False, "> operator - lower version"),

        # Basic <= operator
        ("<=8.1", "8.1", True, "<= operator - exact match"),
        ("<=8.1", "8.0", True, "<= operator - lower version"),
        ("<=8.1", "8.2", False, "<= operator - higher version"),

        # Basic < operator
        ("<8.2", "8.1", True, "< operator - lower version"),
        ("<8.2", "8.2", False, "< operator - exact match should fail"),
        ("<8.2", "8.3", False, "< operator - higher version"),

        # Caret operator (treated as >=)
        ("^8.1", "8.1", True, "^ operator - exact match"),
        ("^8.1", "8.2", True, "^ operator - higher minor"),
        ("^8.1", "8.0", False, "^ operator - lower version"),
        ("^7.4", "8.0", True, "^ operator - next major allowed"),

        # Tilde operator (treated as >=)
        ("~8.1", "8.1", True, "~ operator - exact match"),
        ("~8.1", "8.2", True, "~ operator - higher minor"),
        ("~8.1", "7.4", False, "~ operator - lower version"),

        # No operator (treated as >=)
        ("8.1", "8.1", True, "No operator - exact match"),
        ("8.1", "8.2", True, "No operator - higher version"),
        ("8.1", "8.0", False, "No operator - lower version"),

        # OR constraints (||)
        (">=7.2 || >=8.0", "7.4", True, "OR constraint - matches first part"),
        (">=7.2 || >=8.0", "8.1", True, "OR constraint - matches second part"),
        (">=7.4 || >=8.0", "7.2", False, "OR constraint - matches neither"),
        ("^7.4 || ^8.0", "8.2", True, "OR constraint with caret - matches second"),
        (">=7.2||>=8.0", "7.4", True, "OR constraint without spaces"),

        # AND constraints (comma-separated)
        (">=8.0, <9.0", "8.1", True, "AND constraint - in range"),
        (">=8.0, <9.0", "9.0", False, "AND constraint - at upper bound"),
        (">=8.0, <9.0", "7.4", False, "AND constraint - below range"),
        (">=8.0,<9.0", "8.5", True, "AND constraint without spaces"),

        # Complex constraints
        (">=7.2.5 || ^8.0", "7.2.6", True, "Complex - patch version higher"),
        (">=7.2.5 || ^8.0", "7.2.4", False, "Complex - patch version lower"),
        (">=8.1.0", "8.1", True, "Three-part constraint vs two-part target"),
        (">=8.1", "8.1.5", True, "Two-part constraint vs three-part target"),

        # Version with prerelease suffix (should strip it)
        (">=8.1.0-beta", "8.1", True, "Constraint with prerelease suffix"),
        (">=8.1.0@dev", "8.1", True, "Constraint with @dev suffix"),

        # Equality operators
        ("==8.1", "8.1", True, "== operator - exact match"),
        ("==8.1", "8.2", False, "== operator - different version"),
        ("=8.1", "8.1", True, "= operator - exact match"),
        ("!=8.1", "8.2", True, "!= operator - different version"),
        ("!=8.1", "8.1", False, "!= operator - same version"),

        # Edge cases
        (">=8", "8.1", True, "Single digit constraint"),
        (">=8.1.2.3", "8.1.2.4", True, "Four-part version"),
    ],
)
def test_check_php_constraint(php_constraint, target_php_version, expected_result, test_description):
    """Test check_php_constraint with various constraint formats."""
    result = check_php_constraint(php_constraint, target_php_version)
    assert result == expected_result, f"Failed: {test_description}"


# ============================================================================
# Version parser tests (parse_semver and compare_semver)
# ============================================================================

from package_version_check_mcp.get_latest_versions_pkg.utils.version_parser import parse_semver, compare_semver


@pytest.mark.parametrize(
    "version,expected_numeric,expected_prerelease,test_description",
    [
        # Standard versions
        ("1.2.3", [1, 2, 3], "", "Standard three-part version"),
        ("2.0.0", [2, 0, 0], "", "Major version 2"),
        ("10.20.30", [10, 20, 30], "", "Large version numbers"),
        ("1.0", [1, 0], "", "Two-part version"),
        ("5", [5], "", "Single-part version"),

        # Versions with 'v' prefix
        ("v1.2.3", [1, 2, 3], "", "Version with v prefix"),
        ("v2.0.0", [2, 0, 0], "", "Major version with v prefix"),

        # Prerelease versions
        ("1.0.0-beta", [1, 0, 0], "prerelease", "Version with beta prerelease"),
        ("2.0.0rc1", [2, 0, 0], "prerelease", "Version with rc prerelease"),
        ("3.1.0a1", [3, 1, 0], "prerelease", "Version with alpha prerelease"),
        ("1.2.3b2", [1, 2, 3], "prerelease", "Version with beta number"),
        ("8.5.2RC1", [8, 5, 2], "prerelease", "PHP-style RC version"),

        # Invalid versions (should return empty list and 'invalid')
        ("4.0b3_RC2", [], "invalid", "Invalid version with underscore"),
        ("invalid", [], "invalid", "Completely invalid version string"),
        ("zulu-1.2.3", [], "invalid", "Completely invalid version string"),
        ("", [], "invalid", "Empty version string"),
    ],
)
def test_parse_semver(version, expected_numeric, expected_prerelease, test_description):
    """Test parse_semver with various version formats."""
    numeric_parts, prerelease = parse_semver(version)
    assert numeric_parts == expected_numeric, f"Failed numeric parts: {test_description}"
    assert prerelease == expected_prerelease, f"Failed prerelease: {test_description}"


@pytest.mark.parametrize(
    "version1,version2,expected_result,test_description",
    [
        # Equal versions
        ("1.2.3", "1.2.3", 0, "Equal versions"),
        ("v1.2.3", "1.2.3", 0, "Equal versions with v prefix on first"),
        ("2.0.0", "v2.0.0", 0, "Equal versions with v prefix on second"),
        ("2.0.0", "v2.0", 0, "Equal versions with v prefix on second"),

        # Less than
        ("1.2.3", "1.2.4", -1, "Patch version less"),
        ("1.2.3", "1.3.0", -1, "Minor version less"),
        ("1.2.3", "2.0.0", -1, "Major version less"),
        ("1.0", "1.0.1", -1, "Two-part vs three-part (less)"),
        ("0.9.9", "1.0.0", -1, "Pre-1.0 version less"),

        # Greater than
        ("1.2.4", "1.2.3", 1, "Patch version greater"),
        ("1.3.0", "1.2.3", 1, "Minor version greater"),
        ("2.0.0", "1.2.3", 1, "Major version greater"),
        ("1.0.1", "1.0", 1, "Three-part vs two-part (greater)"),
        ("10.0.0", "9.9.9", 1, "Double-digit major version"),

        # Prerelease handling
        ("1.0.0rc1", "1.0.0", -1, "Prerelease less than stable"),
        ("1.0.0", "1.0.0rc1", 1, "Stable greater than prerelease"),
        ("2.0.0-beta", "2.0.0", -1, "Beta less than stable"),
        ("1.0.0a1", "1.0.0b1", -1, "Alpha less than beta"),

        # Different number of parts
        ("1.2", "1.2.0", 0, "Two-part equals three-part with zero"),
        ("1", "1.0.0", 0, "One-part equals three-part with zeros"),

        # Invalid versions (should return 0 - equal)
        ("invalid", "1.2.3", 0, "Invalid first version"),
        ("1.2.3", "invalid", 0, "Invalid second version"),
        ("invalid", "invalid", 0, "Both invalid versions"),
        ("4.0b3_RC2", "1.2.3", 0, "Non-standard version format"),
    ],
)
def test_compare_semver(version1, version2, expected_result, test_description):
    """Test compare_semver with various version comparisons."""
    result = compare_semver(version1, version2)
    assert result == expected_result, f"Failed: {test_description} (got {result}, expected {expected_result})"
