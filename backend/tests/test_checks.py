"""Tests for individual validation checks (checks.py).

Covers: manifest, skills, agents, hooks, mcp, paths, symlinks.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from backend.app.models.schemas import Severity
from backend.app.services.checks import (
    check_agents,
    check_hooks,
    check_manifest,
    check_mcp,
    check_paths,
    check_skills,
    check_symlinks,
    parse_frontmatter,
)


# ── Helpers ──────────────────────────────────────────────────────────

def _mkdir(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    return path


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _make_valid_manifest(plugin_dir: Path, name: str = "test-plugin") -> None:
    _mkdir(plugin_dir / ".cursor-plugin")
    _write(
        plugin_dir / ".cursor-plugin" / "plugin.json",
        json.dumps({
            "name": name,
            "version": "1.0.0",
            "description": "A test plugin",
        }),
    )


def _make_valid_skill(plugin_dir: Path, skill_name: str = "my-skill") -> None:
    skill_dir = _mkdir(plugin_dir / "skills" / skill_name)
    _write(
        skill_dir / "SKILL.md",
        f"""---
name: {skill_name}
description: A test skill
paths:
  - README.md
---

# {skill_name}

This is a test skill.
""",
    )
    _write(skill_dir / "README.md", "# Test Skill")


# ── parse_frontmatter ─────────────────────────────────────────────────

class TestParseFrontmatter:
    def test_valid_frontmatter(self):
        content = "---\nname: test\ndescription: hello\n---\nBody text\n"
        data, body = parse_frontmatter(content)
        assert data is not None
        assert data["name"] == "test"
        assert data["description"] == "hello"
        assert "Body text" in body

    def test_invalid_yaml(self):
        content = "---\nname: Test Skill\ndescription: unquoted: value\n---\n"
        data, error = parse_frontmatter(content)
        assert data is None
        assert error is not None
        assert "YAML" in error or "Invalid" in error

    def test_no_frontmatter(self):
        content = "Just some text without frontmatter\n"
        data, error = parse_frontmatter(content)
        assert data is None
        assert "delimiter" in error.lower()

    def test_empty_frontmatter(self):
        content = "---\n---\nBody\n"
        data, body = parse_frontmatter(content)
        assert data == {}
        assert body == "Body\n"


# ── Manifest ──────────────────────────────────────────────────────────

class TestManifestCheck:
    def test_missing_manifest(self, plugin_dir: Path):
        results = check_manifest(plugin_dir)
        errors = [r for r in results if r.severity == Severity.error]
        assert len(errors) == 1
        assert errors[0].check_id == "manifest_missing"

    def test_invalid_json(self, plugin_dir: Path):
        _mkdir(plugin_dir / ".cursor-plugin")
        _write(plugin_dir / ".cursor-plugin" / "plugin.json", "{invalid json")
        results = check_manifest(plugin_dir)
        errors = [r for r in results if r.severity == Severity.error]
        assert any(r.check_id == "manifest_json_invalid" for r in errors)

    def test_missing_required_fields(self, plugin_dir: Path):
        _mkdir(plugin_dir / ".cursor-plugin")
        _write(plugin_dir / ".cursor-plugin" / "plugin.json", json.dumps({"name": "x"}))
        results = check_manifest(plugin_dir)
        missing = [r for r in results if r.check_id == "manifest_missing_field"]
        assert len(missing) == 2  # version + description

    def test_valid_manifest(self, plugin_dir: Path):
        _make_valid_manifest(plugin_dir)
        results = check_manifest(plugin_dir)
        errors = [r for r in results if r.severity == Severity.error]
        assert len(errors) == 0
        # marketplace.json warning is expected
        warnings = [r for r in results if r.severity == Severity.warning]
        assert any(r.check_id == "marketplace_missing" for r in warnings)

    def test_invalid_name_pattern(self, plugin_dir: Path):
        _mkdir(plugin_dir / ".cursor-plugin")
        _write(
            plugin_dir / ".cursor-plugin" / "plugin.json",
            json.dumps({"name": "My Plugin", "version": "1.0.0", "description": "d"}),
        )
        results = check_manifest(plugin_dir)
        assert any(r.check_id == "manifest_name_invalid" for r in results)


# ── Skills ────────────────────────────────────────────────────────────

class TestSkillsCheck:
    def test_missing_skills_dir(self, plugin_dir: Path):
        results = check_skills(plugin_dir)
        assert any(r.check_id == "skills_dir_missing" for r in results)

    def test_name_mismatch_issue_237(self, plugin_dir: Path):
        """Skill name doesn't match folder name (issue #237)."""
        _make_valid_skill(plugin_dir, skill_name="poteto-mode")
        # Tamper: set name to "Poteto Mode" (capitals + space)
        skill_md = plugin_dir / "skills" / "poteto-mode" / "SKILL.md"
        content = skill_md.read_text()
        content = content.replace("name: poteto-mode", "name: Poteto Mode")
        skill_md.write_text(content)

        results = check_skills(plugin_dir)
        assert any(r.check_id == "skill_name_mismatch" for r in results)
        assert any(r.check_id == "skill_name_invalid_chars" for r in results)

    def test_invalid_yaml_frontmatter(self, plugin_dir: Path):
        """Invalid YAML in frontmatter (issue #381)."""
        skill_dir = _mkdir(plugin_dir / "skills" / "my-skill")
        _write(
            skill_dir / "SKILL.md",
            "---\nname: my-skill\ndescription: unquoted: value\n---\n\nBody\n",
        )
        results = check_skills(plugin_dir)
        assert any(r.check_id == "skill_frontmatter_invalid" for r in results)

    def test_valid_skill(self, plugin_dir: Path):
        _make_valid_skill(plugin_dir, skill_name="my-skill")
        results = check_skills(plugin_dir)
        errors = [r for r in results if r.severity == Severity.error]
        assert len(errors) == 0

    def test_missing_description(self, plugin_dir: Path):
        skill_dir = _mkdir(plugin_dir / "skills" / "my-skill")
        _write(
            skill_dir / "SKILL.md",
            "---\nname: my-skill\n---\n\nBody\n",
        )
        results = check_skills(plugin_dir)
        assert any(r.check_id == "skill_description_missing" for r in results)

    def test_missing_skill_md(self, plugin_dir: Path):
        _mkdir(plugin_dir / "skills" / "broken")
        results = check_skills(plugin_dir)
        assert any(r.check_id == "skill_md_missing" for r in results)


# ── Agents ────────────────────────────────────────────────────────────

class TestAgentsCheck:
    def test_no_agents_dir(self, plugin_dir: Path):
        results = check_agents(plugin_dir)
        assert results == []

    def test_valid_agent(self, plugin_dir: Path):
        _mkdir(plugin_dir / "agents")
        _write(
            plugin_dir / "agents" / "helper.md",
            "---\nname: helper\ndescription: A helper agent\n---\n\nBody\n",
        )
        results = check_agents(plugin_dir)
        errors = [r for r in results if r.severity == Severity.error]
        assert len(errors) == 0

    def test_agent_missing_name(self, plugin_dir: Path):
        _mkdir(plugin_dir / "agents")
        _write(
            plugin_dir / "agents" / "helper.md",
            "---\ndescription: A helper agent\n---\n\nBody\n",
        )
        results = check_agents(plugin_dir)
        assert any(r.check_id == "agent_name_missing" for r in results)


# ── Hooks ─────────────────────────────────────────────────────────────

class TestHooksCheck:
    def test_no_hooks(self, plugin_dir: Path):
        results = check_hooks(plugin_dir)
        assert results == []

    def test_invalid_json(self, plugin_dir: Path):
        _write(plugin_dir / "hooks.json", "{invalid")
        results = check_hooks(plugin_dir)
        assert any(r.check_id == "hooks_json_invalid" for r in results)

    def test_missing_script(self, plugin_dir: Path):
        """Issue #531: hook references a script that doesn't exist."""
        _write(
            plugin_dir / "hooks.json",
            json.dumps({"hooks": {"pre-commit": {"script": "./hooks/pre-commit.sh"}}}),
        )
        results = check_hooks(plugin_dir)
        assert any(r.check_id == "hook_script_missing" for r in results)

    def test_valid_hooks(self, plugin_dir: Path):
        _mkdir(plugin_dir / "hooks")
        _write(plugin_dir / "hooks" / "pre-commit.sh", "#!/bin/sh\necho hi")
        _write(
            plugin_dir / "hooks.json",
            json.dumps({"hooks": {"pre-commit": {"script": "hooks/pre-commit.sh"}}}),
        )
        results = check_hooks(plugin_dir)
        errors = [r for r in results if r.severity == Severity.error]
        assert len(errors) == 0


# ── MCP ───────────────────────────────────────────────────────────────

class TestMCPCheck:
    def test_no_mcp(self, plugin_dir: Path):
        results = check_mcp(plugin_dir)
        assert results == []

    def test_invalid_json(self, plugin_dir: Path):
        _write(plugin_dir / "mcp.json", "{bad")
        results = check_mcp(plugin_dir)
        assert any(r.check_id == "mcp_json_invalid" for r in results)

    def test_undeclared_variable(self, plugin_dir: Path):
        """Issue #531: ${VAR} used but not declared in variables."""
        _write(
            plugin_dir / "mcp.json",
            json.dumps({
                "mcpServers": {
                    "gmail": {
                        "command": "python",
                        "args": ["-m", "server"],
                        "env": {"GMAIL_TOKEN": "${GMAIL_TOKEN}"},
                    }
                }
            }),
        )
        results = check_mcp(plugin_dir)
        assert any(r.check_id == "mcp_undeclared_variable" for r in results)

    def test_gmail_scope_missing_issue_385(self, plugin_dir: Path):
        """Issue #385: Gmail filter tools without settings.basic scope."""
        _write(
            plugin_dir / "mcp.json",
            json.dumps({
                "mcpServers": {
                    "gmail": {"command": "gmail-mcp", "args": []}
                },
                "variables": {},
                # No gmail.settings.basic scope
            }),
        )
        # The raw JSON contains "gmail.settings" via the server config
        results = check_mcp(plugin_dir)
        # Only triggers if "gmail.settings" appears in the JSON
        # Let's use a config that references gmail.settings
        _write(
            plugin_dir / "mcp.json",
            json.dumps({
                "mcpServers": {
                    "gmail": {
                        "command": "gmail-mcp",
                        "args": ["--scopes", "gmail.settings"],
                    }
                },
                "variables": {},
            }),
        )
        results = check_mcp(plugin_dir)
        assert any(r.check_id == "mcp_gmail_scope_missing" for r in results)

    def test_valid_mcp(self, plugin_dir: Path):
        _write(
            plugin_dir / "mcp.json",
            json.dumps({
                "mcpServers": {
                    "myserver": {
                        "command": "python",
                        "args": ["-m", "myserver"],
                        "env": {"API_KEY": "${API_KEY}"},
                    }
                },
                "variables": {"API_KEY": {"description": "API key"}},
            }),
        )
        results = check_mcp(plugin_dir)
        errors = [r for r in results if r.severity == Severity.error]
        assert len(errors) == 0


# ── Paths ─────────────────────────────────────────────────────────────

class TestPathsCheck:
    def test_no_manifest(self, plugin_dir: Path):
        results = check_paths(plugin_dir)
        assert results == []

    def test_missing_referenced_path(self, plugin_dir: Path):
        _make_valid_manifest(plugin_dir)
        manifest = json.loads(
            (plugin_dir / ".cursor-plugin" / "plugin.json").read_text()
        )
        manifest["skills"] = ["nonexistent-skill"]
        _write(
            plugin_dir / ".cursor-plugin" / "plugin.json",
            json.dumps(manifest),
        )
        results = check_paths(plugin_dir)
        assert any(r.check_id == "manifest_path_missing" for r in results)

    def test_valid_paths(self, plugin_dir: Path):
        _make_valid_manifest(plugin_dir)
        _mkdir(plugin_dir / "skills" / "my-skill")
        results = check_paths(plugin_dir)
        errors = [r for r in results if r.severity == Severity.error]
        assert len(errors) == 0


# ── Symlinks ──────────────────────────────────────────────────────────

class TestSymlinkCheck:
    def test_no_symlinks(self, plugin_dir: Path):
        _make_valid_manifest(plugin_dir)
        results = check_symlinks(plugin_dir)
        assert any(r.check_id == "symlink_none" for r in results)

    @pytest.mark.skipif(os.name == "nt", reason="symlinks not reliable on Windows")
    def test_symlink_detected_issue_35(self, plugin_dir: Path):
        """Issue #35: symlinked plugin components cause loading failures."""
        _make_valid_manifest(plugin_dir)
        real_dir = plugin_dir / "real-skills"
        real_dir.mkdir()
        link = plugin_dir / "skills"
        os.symlink(real_dir, link)
        results = check_symlinks(plugin_dir)
        assert any(r.check_id == "symlink_detected" for r in results)