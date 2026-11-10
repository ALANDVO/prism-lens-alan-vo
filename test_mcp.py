#!/usr/bin/env python
"""Test script for MCP validation."""
import sys
sys.path.insert(0, '/var/lib/alan-portfolio/workspaces/alan/prism-lens-alan-vo/backend')

from pathlib import Path
import tempfile
import json

from app.services.checks import check_mcp, Severity

def test_basic():
    with tempfile.TemporaryDirectory() as tmpdir:
        plugin_dir = Path(tmpdir)
        
        # Test 1: No MCP config
        results = check_mcp(plugin_dir)
        assert results == [], f"Expected empty, got {results}"
        print("✓ Test 1 passed: No MCP config")
        
        # Test 2: Valid MCP with stdio transport
        mcp_json = {
            "mcpServers": {
                "myserver": {
                    "command": "python",
                    "args": ["-m", "myserver"],
                    "transport": "stdio",
                }
            },
            "variables": {}
        }
        (plugin_dir / "mcp.json").write_text(json.dumps(mcp_json))
        results = check_mcp(plugin_dir)
        errors = [r for r in results if r.severity == Severity.error]
        assert len(errors) == 0, f"Expected no errors, got {errors}"
        print("✓ Test 2 passed: Valid stdio MCP")
        
        # Test 3: Missing command for stdio
        mcp_json = {
            "mcpServers": {
                "myserver": {
                    "transport": "stdio",
                }
            }
        }
        (plugin_dir / "mcp.json").write_text(json.dumps(mcp_json))
        results = check_mcp(plugin_dir)
        errors = [r for r in results if r.severity == Severity.error]
        assert any(r.check_id == "mcp_missing_command" for r in errors), f"Expected mcp_missing_command, got {errors}"
        print("✓ Test 3 passed: Missing command for stdio")
        
        # Test 4: Invalid transport
        mcp_json = {
            "mcpServers": {
                "myserver": {
                    "command": "python",
                    "transport": "invalid",
                }
            }
        }
        (plugin_dir / "mcp.json").write_text(json.dumps(mcp_json))
        results = check_mcp(plugin_dir)
        errors = [r for r in results if r.severity == Severity.error]
        assert any(r.check_id == "mcp_invalid_transport" for r in errors), f"Expected mcp_invalid_transport, got {errors}"
        print("✓ Test 4 passed: Invalid transport")
        
        # Test 5: SSE transport missing URL
        mcp_json = {
            "mcpServers": {
                "myserver": {
                    "transport": "sse",
                }
            }
        }
        (plugin_dir / "mcp.json").write_text(json.dumps(mcp_json))
        results = check_mcp(plugin_dir)
        errors = [r for r in results if r.severity == Severity.error]
        assert any(r.check_id == "mcp_missing_url_sse" for r in errors), f"Expected mcp_missing_url_sse, got {errors}"
        print("✓ Test 5 passed: SSE missing URL")
        
        # Test 6: SSE transport with invalid URL
        mcp_json = {
            "mcpServers": {
                "myserver": {
                    "transport": "sse",
                    "url": "not-a-url",
                }
            }
        }
        (plugin_dir / "mcp.json").write_text(json.dumps(mcp_json))
        results = check_mcp(plugin_dir)
        errors = [r for r in results if r.severity == Severity.error]
        assert any(r.check_id == "mcp_invalid_url_sse" for r in errors), f"Expected mcp_invalid_url_sse, got {errors}"
        print("✓ Test 6 passed: SSE invalid URL")
        
        # Test 7: HTTP transport with valid URL
        mcp_json = {
            "mcpServers": {
                "myserver": {
                    "transport": "http",
                    "url": "https://example.com/mcp",
                }
            }
        }
        (plugin_dir / "mcp.json").write_text(json.dumps(mcp_json))
        results = check_mcp(plugin_dir)
        errors = [r for r in results if r.severity == Severity.error]
        assert len(errors) == 0, f"Expected no errors for valid HTTP, got {errors}"
        print("✓ Test 7 passed: Valid HTTP transport")
        
        # Test 8: Undeclared variable in env
        mcp_json = {
            "mcpServers": {
                "myserver": {
                    "command": "python",
                    "transport": "stdio",
                    "env": {"API_KEY": "${UNDECLARED_KEY}"},
                }
            },
            "variables": {"OTHER_KEY": {"description": "other"}}
        }
        (plugin_dir / "mcp.json").write_text(json.dumps(mcp_json))
        results = check_mcp(plugin_dir)
        errors = [r for r in results if r.severity == Severity.error]
        assert any(r.check_id == "mcp_undeclared_variable" for r in errors), f"Expected mcp_undeclared_variable, got {errors}"
        print("✓ Test 8 passed: Undeclared variable in env")
        
        # Test 9: GitHub server without auth (warning)
        mcp_json = {
            "mcpServers": {
                "github": {
                    "command": "python",
                    "transport": "stdio",
                }
            }
        }
        (plugin_dir / "mcp.json").write_text(json.dumps(mcp_json))
        results = check_mcp(plugin_dir)
        warnings = [r for r in results if r.severity == Severity.warning]
        assert any(r.check_id == "mcp_github_auth_missing" for r in warnings), f"Expected mcp_github_auth_missing, got {warnings}"
        print("✓ Test 9 passed: GitHub server missing auth warning")
        
        print("\n✅ All tests passed!")

if __name__ == "__main__":
    test_basic()

