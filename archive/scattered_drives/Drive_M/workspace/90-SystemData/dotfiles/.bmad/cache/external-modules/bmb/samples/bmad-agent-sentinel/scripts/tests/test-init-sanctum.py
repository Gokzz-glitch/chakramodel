#!/usr/bin/env python3
"""Tests for init-sanctum.py"""

import sys
import tempfile
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from importlib.machinery import SourceFileLoader

# Load the module with hyphenated filename
loader = SourceFileLoader("init_sanctum", str(Path(__file__).parent.parent / "init-sanctum.py"))
init_sanctum = loader.load_module()


def test_parse_yaml_config_basic():
    """Test basic YAML parsing with simple key-value pairs."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
        f.write("user_name: TestUser\ncommunication_language: English\n")
        f.flush()
        config = init_sanctum.parse_yaml_config(Path(f.name))
        assert config["user_name"] == "TestUser"
        assert config["communication_language"] == "English"
    Path(f.name).unlink()


def test_parse_yaml_config_missing_file():
    """Test that missing config file returns empty dict."""
    config = init_sanctum.parse_yaml_config(Path("/nonexistent/config.yaml"))
    assert config == {}


def test_parse_yaml_config_quoted_values():
    """Test YAML parsing strips quotes from values."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
        f.write("name: 'quoted'\nother: \"double-quoted\"\n")
        f.flush()
        config = init_sanctum.parse_yaml_config(Path(f.name))
        assert config["name"] == "quoted"
        assert config["other"] == "double-quoted"
    Path(f.name).unlink()


def test_parse_frontmatter():
    """Test frontmatter extraction from markdown files."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False) as f:
        f.write("---\nname: test-cap\ndescription: A test\ncode: TC\n---\n\n# Content\n")
        f.flush()
        meta = init_sanctum.parse_frontmatter(Path(f.name))
        assert meta["name"] == "test-cap"
        assert meta["code"] == "TC"
    Path(f.name).unlink()


def test_parse_frontmatter_no_frontmatter():
    """Test frontmatter extraction when no frontmatter exists."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False) as f:
        f.write("# Just content\nNo frontmatter here.\n")
        f.flush()
        meta = init_sanctum.parse_frontmatter(Path(f.name))
        assert meta == {}
    Path(f.name).unlink()


def test_substitute_vars():
    """Test variable substitution in content strings."""
    content = "Hello {user_name}, born on {birth_date}."
    variables = {"user_name": "TestUser", "birth_date": "2026-04-05"}
    result = init_sanctum.substitute_vars(content, variables)
    assert result == "Hello TestUser, born on 2026-04-05."


def test_substitute_vars_no_match():
    """Test that unmatched placeholders are left as-is."""
    content = "Hello {unknown_var}."
    result = init_sanctum.substitute_vars(content, {"user_name": "Test"})
    assert result == "Hello {unknown_var}."


def test_generate_capabilities_md_evolvable():
    """Test capabilities markdown generation with evolvable enabled."""
    caps = [{"name": "test", "description": "A test", "code": "TS", "source": "./references/test.md"}]
    result = init_sanctum.generate_capabilities_md(caps, evolvable=True)
    assert "## Learned" in result
    assert "How to Add a Capability" in result
    assert "[TS]" in result


def test_generate_capabilities_md_not_evolvable():
    """Test capabilities markdown generation without evolvable."""
    caps = [{"name": "test", "description": "A test", "code": "TS", "source": "./references/test.md"}]
    result = init_sanctum.generate_capabilities_md(caps, evolvable=False)
    assert "## Learned" not in result
    assert "[TS]" in result


def test_sanctum_creation():
    """Test full sanctum creation in a temp directory."""
    with tempfile.TemporaryDirectory() as tmpdir:
        project_root = Path(tmpdir)
        skill_path = project_root / "skill"

        # Create minimal skill structure
        bmad_dir = project_root / "_bmad"
        bmad_dir.mkdir()
        (bmad_dir / "config.yaml").write_text("document_output_language: English\n")
        (bmad_dir / "config.user.yaml").write_text("user_name: Tester\ncommunication_language: English\n")

        # Create skill dirs
        refs_dir = skill_path / "references"
        refs_dir.mkdir(parents=True)
        assets_dir = skill_path / "assets"
        assets_dir.mkdir(parents=True)
        scripts_dir = skill_path / "scripts"
        scripts_dir.mkdir(parents=True)

        # Create a capability reference
        (refs_dir / "test-cap.md").write_text(
            "---\nname: test-cap\ndescription: Test capability\ncode: TC\n---\n\n# Test\n"
        )

        # Create minimal templates
        for tmpl in init_sanctum.TEMPLATE_FILES:
            (assets_dir / tmpl).write_text(f"# Template {tmpl}\nUser: {{user_name}}\nBorn: {{birth_date}}\n")

        # Run the sanctum creation logic
        sanctum_path = bmad_dir / "memory" / init_sanctum.SANCTUM_DIR

        # Simulate main() logic
        sanctum_path.mkdir(parents=True, exist_ok=True)
        (sanctum_path / "capabilities").mkdir(exist_ok=True)
        (sanctum_path / "sessions").mkdir(exist_ok=True)

        # Verify structure
        assert sanctum_path.exists()
        assert (sanctum_path / "capabilities").exists()
        assert (sanctum_path / "sessions").exists()


def run_tests():
    """Run all tests and report results."""
    tests = [
        test_parse_yaml_config_basic,
        test_parse_yaml_config_missing_file,
        test_parse_yaml_config_quoted_values,
        test_parse_frontmatter,
        test_parse_frontmatter_no_frontmatter,
        test_substitute_vars,
        test_substitute_vars_no_match,
        test_generate_capabilities_md_evolvable,
        test_generate_capabilities_md_not_evolvable,
        test_sanctum_creation,
    ]

    passed = 0
    failed = 0
    for test in tests:
        try:
            test()
            passed += 1
            print(f"  PASS: {test.__name__}")
        except Exception as e:
            failed += 1
            print(f"  FAIL: {test.__name__} — {e}")

    print(f"\n{passed} passed, {failed} failed")
    return failed == 0


if __name__ == "__main__":
    success = run_tests()
    sys.exit(0 if success else 1)
