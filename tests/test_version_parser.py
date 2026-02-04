import pytest
from package_version_check_mcp.utils.version_parser import Version, parse, InvalidVersion

class TestVersionParser:
    """Tests for the custom Version parser."""

    @pytest.mark.parametrize("version_str, expected", [
        ("1.0", {"major": 1, "minor": 0, "micro": 0, "release": (1, 0)}),
        ("1.2.3", {"major": 1, "minor": 2, "micro": 3, "release": (1, 2, 3)}),
        ("0.1", {"major": 0, "minor": 1, "micro": 0, "release": (0, 1)}),
        ("10.20.30.40", {"major": 10, "minor": 20, "micro": 30, "release": (10, 20, 30, 40)}),
        ("v1.0", {"major": 1, "minor": 0, "micro": 0, "release": (1, 0)}),
    ])
    def test_parsing_basic(self, version_str, expected):
        v = parse(version_str)
        assert v.major == expected["major"]
        assert v.minor == expected["minor"]
        assert v.micro == expected["micro"]
        assert v.release == expected["release"]
        assert v.pre is None
        assert v.post is None
        assert v.dev is None
        assert v.variant is None
        assert str(v) == version_str.lstrip("v")

    @pytest.mark.parametrize("version_str, expected_pre", [
        ("1.0a1", ('a', 1)),
        ("1.0.alpha2", ('a', 2)),
        ("1.0b3", ('b', 3)),
        ("1.0.beta4", ('b', 4)),
        ("1.0rc5", ('rc', 5)),
        ("1.0.rc6", ('rc', 6)),
        ("1.0c7", ('rc', 7)),
        ("1.0pre8", ('rc', 8)),
        ("1.0preview9", ('rc', 9)),
    ])
    def test_parsing_prerelease(self, version_str, expected_pre):
        v = parse(version_str)
        assert v.pre == expected_pre
        assert v.is_prerelease is True

    @pytest.mark.parametrize("version_str, expected_post", [
        ("1.0.post1", 1),
        ("1.0-1", 1),
        ("1.0.rev2", 2),
        ("1.0.r3", 3),
    ])
    def test_parsing_postrelease(self, version_str, expected_post):
        v = parse(version_str)
        assert v.post == expected_post
        assert v.is_postrelease is True

    @pytest.mark.parametrize("version_str, expected_dev", [
        ("1.0.dev1", 1),
        ("1.0.dev4", 4),
    ])
    def test_parsing_devrelease(self, version_str, expected_dev):
        v = parse(version_str)
        assert v.dev == expected_dev
        assert v.is_devrelease is True

    @pytest.mark.parametrize("version_str, expected_variant", [
        ("1.0-android", "android"),
        ("1.0-alpine", "alpine"),
        ("1.0-slim", "slim"),
        ("1.2.3-11.22", "11.22"),
        ("1.0-foo-bar", "foo-bar"),
    ])
    def test_parsing_variant(self, version_str, expected_variant):
        v = parse(version_str)
        assert v.variant == expected_variant
        # Variants are NOT considered prereleases by default in this implementation check
        # unless they also have pre components
        assert v.is_prerelease is False
        assert str(v) == version_str

    def test_parsing_complex_combinations(self):
        # 1.0 alpha 1, post 2, dev 3, variant 'special'
        # Matching regex order: release, pre, post, dev, variant
        v = parse("1.0a1.post2.dev3-special")
        assert v.release == (1, 0)
        assert v.pre == ('a', 1)
        assert v.post == 2
        assert v.dev == 3
        assert v.variant == "special"
        assert str(v) == "1.0a1.post2.dev3-special"

    @pytest.mark.parametrize("invalid_version", [
        "invalid",
        "1.0+local",  # Local removed
        "1!1.0",      # Epoch removed
        "1.0-",       # Variant must have content
        "1.0-.",      # Variant start with dot? regex expects [a-z0-9]
    ])
    def test_invalid_versions(self, invalid_version):
        with pytest.raises(InvalidVersion):
            parse(invalid_version)

    def test_comparison_basic(self):
        assert parse("1.0") < parse("1.1")
        assert parse("1.0.0") == parse("1.0")
        assert parse("1.0.0") == parse("1.0.0.0") # Trailing zeros ignored in release
        assert parse("1.2") > parse("1.1")

    def test_comparison_prerelease(self):
        # dev < alpha < beta < rc < final
        assert parse("1.0.dev1") < parse("1.0a1")
        assert parse("1.0a1") < parse("1.0b1")
        assert parse("1.0b1") < parse("1.0rc1")
        assert parse("1.0rc1") < parse("1.0")

        # versions with different release segments
        assert parse("0.9") < parse("1.0a1")

    def test_comparison_variant(self):
        # Variant < Final
        assert parse("1.0-android") < parse("1.0")

        # Variant comparisons (lexicographical)
        assert parse("1.0-alpine") < parse("1.0-android")

        # Variant vs Pre-release
        # Based on implementation:
        # 1.0a1 (pre matches) vs 1.0-var (pre=None).
        # _pre for 1.0a1 is ('a',1). _pre for 1.0-var is Infinity.
        # So 1.0-var > 1.0a1
        assert parse("1.0-android") > parse("1.0a1")
        assert parse("1.0-android") > parse("1.0rc1")

        # Variant vs Post/Dev
        # 1.0.post1 vs 1.0-android
        # 1.0.post1: post=1. 1.0-android: post=None -> -Infinity.
        # So 1.0.post1 > 1.0-android.
        assert parse("1.0.post1") > parse("1.0-android")

    def test_properties(self):
        v = parse("1.2.3")
        assert v.public == "1.2.3"
        assert v.base_version == "1.2.3"

        v2 = parse("1.2.3-android")
        assert v2.public == "1.2.3-android"
        assert v2.base_version == "1.2.3"
    @pytest.mark.parametrize("version_str, expected_pre, expected_release", [
        ("1.0m1", ('m', 1), (1, 0)),
        ("1.0.milestone2", ('m', 2), (1, 0)),
        ("1.2.0-M2", ('m', 2), (1, 2, 0)),
    ])
    def test_parsing_milestone(self, version_str, expected_pre, expected_release):
        v = parse(version_str)
        assert v.pre == expected_pre
        assert v.release == expected_release
        assert v.is_prerelease is True

    def test_comparison_milestone(self):
        # alpha < beta < milestone < rc
        assert parse("1.0a1") < parse("1.0m1")
        assert parse("1.0b1") < parse("1.0m1")
        assert parse("1.0m1") < parse("1.0rc1")
    def test_trimmed_release(self):
        # Although _TrimmedRelease is an internal helper, verifying release property behavior
        v = parse("1.0.0.0")
        assert v.release == (1, 0, 0, 0)
        # Comparability uses trimmed release implicitly
        assert v == parse("1.0")
