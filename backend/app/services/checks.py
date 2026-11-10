"""Individual validation checks for Cursor plugins.

Each check function receives the plugin root directory and returns a list
of CheckResult objects.  Checks are deterministic — no network access, no
LLM dependency.

Check categories and their originating issues:
  manifest  — issue #531 (manifest schema + name pattern)
  skills    — issue #237 (name identifier constraint), #381 (invalid YAML)
  agents    — issue #531 (agent frontmatter)
  hooks     — issue #531 (hook script path existence)
  mcp       — issue #531 (placeholder variables), #251/#385 (OAuth scopes)
  paths     — issue #531 (component path existence)
  symlinks  — issue #35 (symlinked plugin components)
  oauth     — issue #278/#385 (OAuth connector scope validation)
"""

from __future__ import annotations

import json
import os
import re
from pathlib import Path

from backend.app.models.schemas import CheckResult, Severity

# --- Constants derived from the Agent Skills specification ---

# Skill/agent name must be lowercase letters, numbers, and hyphens only,
# must match the parent folder name.  See issue #237.
NAME_PATTERN = re.compile(r"^[a-z0-9]([a-z0-9.-]*[a-z0-9])?$")

# Plugin manifest name pattern (same constraint as skill names).
PLUGIN_NAME_PATTERN = NAME_PATTERN

# Required fields in a plugin.json manifest.
MANIFEST_REQUIRED_FIELDS: list[str] = ["name", "version", "description"]

# Required fields in skill/agent frontmatter.
FRONTMATTER_REQUIRED_FIELDS: list[str] = ["name", "description"]

# Required OAuth scopes for auth-dependent MCP tools (issue #385).
GMAIL_SETTINGS_SCOPE = "https://www.googleapis.com/auth/gmail.settings.basic"


def _result(
    check_id: str,
    category: str,
    severity: Severity,
    title: str,
    message: str,
    file_path: str | None = None,
    line: int | None = None,
) -> CheckResult:
    """Helper to build a CheckResult."""
    return CheckResult(
        check_id=check_id,
        category=category,
        severity=severity,
        title=title,
        message=message,
        file_path=file_path,
        line=line,
    )


def parse_frontmatter(content: str) -> tuple[dict | None, str | None]:
    """Parse YAML frontmatter from a Markdown file.

    Returns (frontmatter_dict_or_None, body_or_None).  If the frontmatter
    block is present but contains a syntax error, the dict is None and the
    second element is the error message.
    """
    if not content.startswith("---"):
        return None, "File does not start with a frontmatter delimiter"

    # Split on the closing delimiter.
    parts = content.split("---", 2)
    if len(parts) < 3:
        return None, "Frontmatter block is not closed"

    raw_block = parts[1]
    body = parts[2].lstrip("\n")

    try:
        import yaml

        data = yaml.safe_load(raw_block)
    except yaml.YAMLError as exc:
        return None, f"Invalid YAML frontmatter: {exc}"

    if data is None:
        return {}, body
    if not isinstance(data, dict):
        return None, "Frontmatter is not a YAML mapping"
    return data, body


def check_manifest(plugin_dir: Path) -> list[CheckResult]:
    """Validate the plugin.json manifest."""
    results: list[CheckResult] = []
    manifest_path = plugin_dir / ".cursor-plugin" / "plugin.json"

    if not manifest_path.exists():
        results.append(
            _result(
                "manifest_missing",
                "manifest",
                Severity.error,
                "Missing plugin manifest",
                "No .cursor-plugin/plugin.json found at the plugin root. "
                "Every plugin must declare a manifest.",
                file_path=".cursor-plugin/plugin.json",
            )
        )
        return results

    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        results.append(
            _result(
                "manifest_json_invalid",
                "manifest",
                Severity.error,
                "Invalid JSON in plugin manifest",
                f"plugin.json could not be parsed as JSON: {exc}",
                file_path=str(manifest_path),
                line=exc.lineno if hasattr(exc, "lineno") else None,
            )
        )
        return results

    if not isinstance(manifest, dict):
        results.append(
            _result(
                "manifest_not_object",
                "manifest",
                Severity.error,
                "Manifest is not a JSON object",
                "plugin.json must contain a JSON object at the top level.",
                file_path=str(manifest_path),
            )
        )
        return results

    # Required fields
    for field_name in MANIFEST_REQUIRED_FIELDS:
        if field_name not in manifest:
            results.append(
                _result(
                    "manifest_missing_field",
                    "manifest",
                    Severity.error,
                    f"Manifest missing required field: {field_name}",
                    f"The field '{field_name}' is required in plugin.json.",
                    file_path=str(manifest_path),
                )
            )

    # Name pattern
    name = manifest.get("name", "")
    if isinstance(name, str) and name and not PLUGIN_NAME_PATTERN.match(name):
        results.append(
            _result(
                "manifest_name_invalid",
                "manifest",
                Severity.error,
                "Plugin name does not conform to identifier rules",
                f"Name '{name}' must match the pattern "
                r"^[a-z0-9]([a-z0-9.-]*[a-z0-9])?$ — lowercase letters, "
                "numbers, hyphens, and dots only.",
                file_path=str(manifest_path),
            )
        )

    # Marketplace cross-reference (issue #531)
    marketplace_path = plugin_dir / ".cursor-plugin" / "marketplace.json"
    if not marketplace_path.exists():
        results.append(
            _result(
                "marketplace_missing",
                "manifest",
                Severity.warning,
                "Marketplace manifest not found",
                ".cursor-plugin/marketplace.json is recommended for plugins "
                "published to Cursor's marketplace.",
                file_path=str(marketplace_path),
            )
        )

    return results


def check_skills(plugin_dir: Path) -> list[CheckResult]:
    """Validate all skill SKILL.md files."""
    results: list[CheckResult] = []
    skills_dir = plugin_dir / "skills"

    if not skills_dir.exists():
        results.append(
            _result(
                "skills_dir_missing",
                "skills",
                Severity.warning,
                "No skills directory",
                f"The directory '{skills_dir}' does not exist. Plugins without "
                "skills have nothing for agents to discover.",
            )
        )
        return results

    for skill_dir in sorted(skills_dir.iterdir()):
        if not skill_dir.is_dir():
            continue

        skill_name = skill_dir.name
        skill_md = skill_dir / "SKILL.md"

        if not skill_md.exists():
            results.append(
                _result(
                    "skill_md_missing",
                    "skills",
                    Severity.error,
                    f"Missing SKILL.md for skill '{skill_name}'",
                    f"No SKILL.md found in {skill_dir}.",
                    file_path=f"skills/{skill_name}/SKILL.md",
                )
            )
            continue

        content = skill_md.read_text(encoding="utf-8")
        frontmatter, error = parse_frontmatter(content)

        if frontmatter is None:
            results.append(
                _result(
                    "skill_frontmatter_invalid",
                    "skills",
                    Severity.error,
                    f"Invalid frontmatter in skill '{skill_name}'",
                    error or "Could not parse frontmatter.",
                    file_path=str(skill_md),
                )
            )
            continue

        # Name must match parent folder (issue #237)
        name = frontmatter.get("name")
        if name is None:
            results.append(
                _result(
                    "skill_name_missing",
                    "skills",
                    Severity.error,
                    f"Skill '{skill_name}' has no name field",
                    "The 'name' field is required in SKILL.md frontmatter.",
                    file_path=str(skill_md),
                )
            )
        elif name != skill_name:
            results.append(
                _result(
                    "skill_name_mismatch",
                    "skills",
                    Severity.error,
                    f"Skill name mismatch in '{skill_name}'",
                    f"Frontmatter name '{name}' does not match folder name "
                    f"'{skill_name}'. The name must match the parent directory.",
                    file_path=str(skill_md),
                )
            )

        # Name must conform to identifier pattern (issue #237)
        if isinstance(name, str) and name and not NAME_PATTERN.match(name):
            results.append(
                _result(
                    "skill_name_invalid_chars",
                    "skills",
                    Severity.error,
                    f"Skill name '{name}' has invalid characters",
                    f"Name must match {NAME_PATTERN.pattern} — "
                    "lowercase letters, numbers, hyphens only.",
                    file_path=str(skill_md),
                )
            )

        # Description required (issue #530)
        if not frontmatter.get("description"):
            results.append(
                _result(
                    "skill_description_missing",
                    "skills",
                    Severity.warning,
                    f"Skill '{skill_name}' has no description",
                    "The 'description' field is recommended in SKILL.md "
                    "frontmatter.",
                    file_path=str(skill_md),
                )
            )

        # Check paths field references exist (issue #531)
        paths = frontmatter.get("paths", [])
        if isinstance(paths, list):
            for p in paths:
                if isinstance(p, str):
                    resolved = skill_dir / p
                    if not resolved.exists():
                        results.append(
                            _result(
                                "skill_path_missing",
                                "skills",
                                Severity.warning,
                                f"Skill path does not exist: {p}",
                                f"Path '{p}' referenced in "
                                f"skills/{skill_name}/SKILL.md does not exist.",
                                file_path=str(skill_md),
                            )
                        )

    return results


def check_agents(plugin_dir: Path) -> list[CheckResult]:
    """Validate agent definition files."""
    results: list[CheckResult] = []
    agents_dir = plugin_dir / "agents"

    if not agents_dir.exists():
        return results  # Agents are optional

    for agent_file in sorted(agents_dir.iterdir()):
        if not agent_file.is_file() or agent_file.suffix != ".md":
            continue

        content = agent_file.read_text(encoding="utf-8")
        frontmatter, error = parse_frontmatter(content)

        if frontmatter is None:
            results.append(
                _result(
                    "agent_frontmatter_invalid",
                    "agents",
                    Severity.error,
                    f"Invalid frontmatter in agent '{agent_file.name}'",
                    error or "Could not parse frontmatter.",
                    file_path=str(agent_file),
                )
            )
            continue

        name = frontmatter.get("name")
        if name is None:
            results.append(
                _result(
                    "agent_name_missing",
                    "agents",
                    Severity.error,
                    f"Agent '{agent_file.name}' has no name field",
                    "The 'name' field is required in agent frontmatter.",
                    file_path=str(agent_file),
                )
            )

        if not frontmatter.get("description"):
            results.append(
                _result(
                    "agent_description_missing",
                    "agents",
                    Severity.warning,
                    f"Agent '{agent_file.name}' has no description",
                    "The 'description' field is recommended in agent "
                    "frontmatter.",
                    file_path=str(agent_file),
                )
            )

    return results


def check_hooks(plugin_dir: Path) -> list[CheckResult]:
    """Validate hooks.json and referenced script paths."""
    results: list[CheckResult] = []
    hooks_path = plugin_dir / "hooks.json"

    if not hooks_path.exists():
        return results  # Hooks are optional

    try:
        data = json.loads(hooks_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        results.append(
            _result(
                "hooks_json_invalid",
                "hooks",
                Severity.error,
                "Invalid JSON in hooks.json",
                str(exc),
                file_path=str(hooks_path),
                line=exc.lineno if hasattr(exc, "lineno") else None,
            )
        )
        return results

    if not isinstance(data, dict):
        results.append(
            _result(
                "hooks_not_object",
                "hooks",
                Severity.error,
                "hooks.json is not a JSON object",
                "hooks.json must contain a JSON object at the top level.",
                file_path=str(hooks_path),
            )
        )
        return results

    # Check referenced script paths exist (issue #531)
    hook_scripts_dir = plugin_dir / "hooks"
    hooks = data.get("hooks", {})
    if isinstance(hooks, dict):
        for hook_name, config in hooks.items():
            if isinstance(config, dict):
                script = config.get("script")
                if isinstance(script, str):
                    # Resolve relative to hooks/ directory
                    # (issue #531: ralph-loop used ./hooks/*.sh incorrectly)
                    resolved = plugin_dir / script
                    if not resolved.exists():
                        resolved_alt = hook_scripts_dir / Path(script).name
                        if not resolved_alt.exists():
                            results.append(
                                _result(
                                    "hook_script_missing",
                                    "hooks",
                                    Severity.error,
                                    f"Hook script not found: {script}",
                                    f"Script '{script}' referenced by hook "
                                    f"'{hook_name}' does not exist.",
                                    file_path=str(hooks_path),
                                )
                            )

    return results


def check_mcp(plugin_dir: Path) -> list[CheckResult]:
    """Validate mcp.json — structure, variables, and OAuth scopes."""
    results: list[CheckResult] = []
    mcp_path = plugin_dir / "mcp.json"

    if not mcp_path.exists():
        return results  # MCP config is optional

    try:
        data = json.loads(mcp_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        results.append(
            _result(
                "mcp_json_invalid",
                "mcp",
                Severity.error,
                "Invalid JSON in mcp.json",
                str(exc),
                file_path=str(mcp_path),
                line=exc.lineno if hasattr(exc, "lineno") else None,
            )
        )
        return results

    if not isinstance(data, dict):
        results.append(
            _result(
                "mcp_not_object",
                "mcp",
                Severity.error,
                "mcp.json is not a JSON object",
                file_path=str(mcp_path),
            )
        )
        return results

    # Check ${VAR} placeholders are declared in variables (issue #531)
    variables = data.get("variables", {})
    declared = set(variables.keys()) if isinstance(variables, dict) else set()
    declared.update(k for k, v in (variables.items() if isinstance(variables, dict) else []))

    mcp_servers = data.get("mcpServers", data.get("servers", {}))
    if isinstance(mcp_servers, dict):
        for server_name, config in mcp_servers.items():
            if isinstance(config, dict):
                # Check command and args for ${VAR} placeholders
                for field in ["command", "args", "url", "env"]:
                    value = config.get(field)
                    if isinstance(value, str):
                        for match in re.finditer(r"\$\{(\w+)\}", value):
                            var_name = match.group(1)
                            if var_name not in declared:
                                results.append(
                                    _result(
                                        "mcp_undeclared_variable",
                                        "mcp",
                                        Severity.error,
                                        f"Undeclared variable ${{{var_name}}}",
                                        f"Variable '${{{var_name}}}' used in "
                                        f"mcp.json server '{server_name}' but "
                                        "not declared in 'variables'.",
                                        file_path=str(mcp_path),
                                    )
                                )
                    elif isinstance(value, list):
                        for item in value:
                            if isinstance(item, str):
                                for match in re.finditer(r"\$\{(\w+)\}", item):
                                    var_name = match.group(1)
                                    if var_name not in declared:
                                        results.append(
                                            _result(
                                                "mcp_undeclared_variable",
                                                "mcp",
                                                Severity.error,
                                                f"Undeclared variable ${{{var_name}}}",
                                                f"Variable '${{{var_name}}}' used in "
                                                f"server '{server_name}' but "
                                                "not declared in 'variables'.",
                                                file_path=str(mcp_path),
                                            )
                                        )
                    elif isinstance(value, dict):
                        for v in value.values():
                            if isinstance(v, str):
                                for match in re.finditer(r"\$\{(\w+)\}", v):
                                    var_name = match.group(1)
                                    if var_name not in declared:
                                        results.append(
                                            _result(
                                                "mcp_undeclared_variable",
                                                "mcp",
                                                Severity.error,
                                                f"Undeclared variable ${{{var_name}}}",
                                                f"Variable '${{{var_name}}}' used "
                                                f"in server '{server_name}' env but "
                                                "not declared in 'variables'.",
                                                file_path=str(mcp_path),
                                            )
                                        )

    # Transport-specific validation
    mcp_servers = data.get("mcpServers", data.get("servers", {}))
    if isinstance(mcp_servers, dict):
        for server_name, config in mcp_servers.items():
            if isinstance(config, dict):
                transport = config.get("transport", "stdio")
                
                # Validate transport type
                if transport not in ("stdio", "sse", "http"):
                    results.append(
                        _result(
                            "mcp_invalid_transport",
                            "mcp",
                            Severity.error,
                            f"Invalid transport '{transport}'",
                            f"MCP server '{server_name}' has invalid transport '{transport}'. "
                            "Valid transports: stdio, sse, http.",
                            file_path=str(mcp_path),
                        )
                    )
                    continue
                
                # Transport-specific required fields
                if transport == "stdio":
                    command = config.get("command")
                    if not command or not isinstance(command, str) or not command.strip():
                        results.append(
                            _result(
                                "mcp_missing_command",
                                "mcp",
                                Severity.error,
                                "Missing required 'command' for stdio transport",
                                f"MCP server '{server_name}' with stdio transport must have a 'command' field.",
                                file_path=str(mcp_path),
                            )
                        )
                    else:
                        # Check command exists (basic validation - warn if not absolute path and not in PATH)
                        cmd_name = command.split()[0] if isinstance(command, str) else ""
                        if cmd_name and not os.path.isabs(cmd_name):
                            # Check if it's a common builtin or likely in PATH
                            common_builtins = {"python", "python3", "node", "npm", "npx", "uvx", "docker"}
                            if cmd_name not in common_builtins:
                                results.append(
                                    _result(
                                        "mcp_command_not_found",
                                        "mcp",
                                        Severity.warning,
                                        f"Command '{cmd_name}' may not be in PATH",
                                        f"MCP server '{server_name}' uses command '{cmd_name}' which is not an absolute path "
                                        "and not a common builtin. Ensure it is available in the execution environment.",
                                        file_path=str(mcp_path),
                                    )
                                )
                elif transport in ("sse", "http"):
                    url = config.get("url")
                    if not url or not isinstance(url, str) or not url.strip():
                        results.append(
                            _result(
                                f"mcp_missing_url_{transport}",
                                "mcp",
                                Severity.error,
                                f"Missing required 'url' for {transport} transport",
                                f"MCP server '{server_name}' with {transport} transport must have a 'url' field.",
                                file_path=str(mcp_path),
                            )
                        )
                    else:
                        # Validate URL format
                        if not re.match(r"^https?://", url):
                            results.append(
                                _result(
                                    f"mcp_invalid_url_{transport}",
                                    "mcp",
                                    Severity.error,
                                    f"Invalid URL format for {transport} transport",
                                    f"MCP server '{server_name}' URL '{url}' must start with http:// or https://",
                                    file_path=str(mcp_path),
                                )
                            )
                
                # Check env variables for ${VAR} placeholders (all transports)
                env = config.get("env")
                if isinstance(env, dict):
                    for env_key, env_value in env.items():
                        if isinstance(env_value, str):
                            for match in re.finditer(r"\$\{(\w+)\}", env_value):
                                var_name = match.group(1)
                                if var_name not in declared:
                                    results.append(
                                        _result(
                                            "mcp_undeclared_variable",
                                            "mcp",
                                            Severity.error,
                                            f"Undeclared variable ${{{var_name}}}",
                                            f"Variable '${{{var_name}}}' used in "
                                            f"server '{server_name}' env but "
                                            "not declared in 'variables'.",
                                            file_path=str(mcp_path),
                                        )
                                    )
                
                # OAuth configuration validation
                auth_config = config.get("auth", config.get("oauth"))
                if auth_config is not None:
                    if not isinstance(auth_config, dict):
                        results.append(
                            _result(
                                "mcp_invalid_auth_config",
                                "mcp",
                                Severity.error,
                                "Invalid auth/oauth configuration",
                                f"MCP server '{server_name}' auth/oauth must be an object.",
                                file_path=str(mcp_path),
                            )
                        )
                    else:
                        # Validate auth type
                        auth_type = auth_config.get("type")
                        if auth_type and auth_type not in ("bearer", "oauth2", "api_key", "basic"):
                            results.append(
                                _result(
                                    "mcp_invalid_auth_type",
                                    "mcp",
                                    Severity.warning,
                                    f"Unknown auth type '{auth_type}'",
                                    f"MCP server '{server_name}' has unknown auth type '{auth_type}'. "
                                    "Common types: bearer, oauth2, api_key, basic.",
                                    file_path=str(mcp_path),
                                )
                            )
                        
                        # Validate scopes if present
                        scopes = auth_config.get("scopes", auth_config.get("scope"))
                        if scopes is not None:
                            if isinstance(scopes, str):
                                scopes = [scopes]
                            if not isinstance(scopes, list):
                                results.append(
                                    _result(
                                        "mcp_invalid_scopes",
                                        "mcp",
                                        Severity.error,
                                        "Invalid scopes format",
                                        f"MCP server '{server_name}' scopes must be a string or array.",
                                        file_path=str(mcp_path),
                                    )
                                )
                
                # Server capability validation - check for required fields based on server type hints
                # If server name suggests specific capabilities, validate accordingly
                server_name_lower = server_name.lower()
                if "gmail" in server_name_lower:
                    # Check for Gmail-specific scope
                    _check_gmail_scope(results, config, server_name, mcp_path)
                if "github" in server_name_lower or "git" in server_name_lower:
                    _check_github_auth(results, config, server_name, mcp_path)

    # OAuth scope checks (issues #385, #278) - global check
    mcp_servers = data.get("mcpServers", data.get("servers", {}))
    if isinstance(mcp_servers, dict):
        for server_name, config in mcp_servers.items():
            if isinstance(config, dict):
                _check_gmail_scope(results, config, server_name, mcp_path)

    return results


def _check_gmail_scope(
    results: list[CheckResult],
    config: dict,
    server_name: str,
    mcp_path: Path,
) -> None:
    """Check if Gmail settings scope is declared when Gmail tools are referenced."""
    # Check if this server references Gmail settings (in command, args, or env)
    gmail_referenced = False
    for field in ["command", "args", "url", "env"]:
        value = config.get(field)
        if isinstance(value, str) and "gmail.settings" in value.lower():
            gmail_referenced = True
            break
        elif isinstance(value, list):
            for item in value:
                if isinstance(item, str) and "gmail.settings" in item.lower():
                    gmail_referenced = True
                    break
        elif isinstance(value, dict):
            for v in value.values():
                if isinstance(v, str) and "gmail.settings" in v.lower():
                    gmail_referenced = True
                    break
        if gmail_referenced:
            break
    
    if gmail_referenced:
        # Check if the required scope is declared in the server's auth/oauth config
        auth_config = config.get("auth", config.get("oauth", {}))
        if isinstance(auth_config, dict):
            scopes = auth_config.get("scopes", auth_config.get("scope", []))
            if isinstance(scopes, str):
                scopes = [scopes]
            has_gmail_scope = any(
                GMAIL_SETTINGS_SCOPE in s for s in scopes if isinstance(s, str)
            )
        else:
            has_gmail_scope = False
        
        # Also check global variables for the scope (fallback)
        if not has_gmail_scope:
            # Note: we'd need access to the full data here; for now just check config
            pass
        
        if not has_gmail_scope:
            results.append(
                _result(
                    "mcp_gmail_scope_missing",
                    "oauth",
                    Severity.warning,
                    "Gmail filter tools may require gmail.settings.basic scope",
                    f"MCP server '{server_name}' references Gmail settings tools "
                    f"but does not include the required scope "
                    f"'{GMAIL_SETTINGS_SCOPE}' in its auth/oauth configuration. "
                    "Calls to create_filter / list_filters will return 403.",
                    file_path=str(mcp_path),
                )
            )


def _check_github_auth(
    results: list[CheckResult],
    config: dict,
    server_name: str,
    mcp_path: Path,
) -> None:
    """Check if GitHub servers have proper authentication configured."""
    auth_config = config.get("auth", config.get("oauth"))
    if auth_config is None:
        results.append(
            _result(
                "mcp_github_auth_missing",
                "mcp",
                Severity.warning,
                "GitHub server may require authentication",
                f"MCP server '{server_name}' appears to be a GitHub server but has no auth/oauth configuration. "
                "Consider adding a bearer token or OAuth2 config for private repository access.",
                file_path=str(mcp_path),
            )
        )


def check_paths(plugin_dir: Path) -> list[CheckResult]:
    """Check that all component paths referenced in the manifest exist."""
    results: list[CheckResult] = []
    manifest_path = plugin_dir / ".cursor-plugin" / "plugin.json"
    if not manifest_path.exists():
        return results

    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return results

    # Component path fields from the manifest schema
    component_fields = [
        "skills", "agents", "commands", "rules", "logo",
        "icon", "hooks", "mcpServers",
    ]

    for field in component_fields:
        value = manifest.get(field)
        if isinstance(value, str):
            resolved = plugin_dir / value
            if not resolved.exists():
                results.append(
                    _result(
                        "manifest_path_missing",
                        "paths",
                        Severity.warning,
                        f"Manifest path does not exist: {value}",
                        f"Path '{value}' in field '{field}' of plugin.json "
                        "does not exist.",
                        file_path=str(manifest_path),
                    )
                )
        elif isinstance(value, list):
            for item in value:
                if isinstance(item, str):
                    resolved = plugin_dir / item
                    if not resolved.exists():
                        results.append(
                            _result(
                                "manifest_path_missing",
                                "paths",
                                Severity.warning,
                                f"Manifest path does not exist: {item}",
                                f"Path '{item}' in field '{field}' of "
                                "plugin.json does not exist.",
                                file_path=str(manifest_path),
                            )
                        )

    return results


def check_symlinks(plugin_dir: Path) -> list[CheckResult]:
    """Detect symlinked plugin components.

    Issue #35: plugins installed via symlinks in ~/.cursor/plugins/local/
    do not load in Cursor.  This check inspects the plugin tree for any
    symlinked files or directories.
    """
    results: list[CheckResult] = []
    symlink_found = False

    for root, dirs, files in os_walk(plugin_dir):
        for name in dirs + files:
            entry = Path(root) / name
            if entry.is_symlink():
                symlink_found = True
                target = entry.resolve()
                results.append(
                    _result(
                        "symlink_detected",
                        "symlinks",
                        Severity.warning,
                        "Symlinked plugin component detected",
                        f"'{entry.relative_to(plugin_dir)}' is a symlink to "
                        f"'{target}'. Plugins installed via symlinks may fail "
                        "to load in Cursor (issue #35). Copy the directory "
                        "instead of symlinking.",
                        file_path=str(entry.relative_to(plugin_dir)),
                    )
                )

    if not symlink_found:
        results.append(
            _result(
                "symlink_none",
                "symlinks",
                Severity.info,
                "No symlinks detected",
                "No symlinked files or directories found in the plugin tree.",
            )
        )

    return results


def os_walk(root: Path):
    """Wrapper around os.walk to avoid top-level import clutter."""
    import os

    return os.walk(root)


# --- Registry of all checks ---

ALL_CHECKS: list = [
    check_manifest,
    check_skills,
    check_agents,
    check_hooks,
    check_mcp,
    check_paths,
    check_symlinks,
]