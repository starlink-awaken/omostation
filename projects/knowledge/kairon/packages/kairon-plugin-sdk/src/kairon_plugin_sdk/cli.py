# ---
# domain: sdk
# layer: tool
# status: active
# ---
"""
Plugin SDK CLI

Command-line interface for plugin development.
"""

from __future__ import annotations

import json
from pathlib import Path

import click
import yaml


@click.group()
@click.version_option(version="1.0.0", prog_name="kairon-plugin")
def main() -> None:
    """Plugin SDK - Develop and manage kairon plugins."""
    pass


@main.command()
@click.argument("plugin_id")
@click.option("--name", help="Plugin display name")
@click.option("--description", help="Plugin description")
@click.option("--author", help="Plugin author")
@click.option("--email", help="Author email")
@click.option("--template", default="basic", type=click.Choice(["basic", "advanced", "api"]))
def init(
    plugin_id: str, name: str | None, description: str | None, author: str | None, email: str | None, template: str
) -> None:
    """
    Initialize a new plugin project.

    Creates a new plugin directory with all necessary files.
    """
    plugin_dir = Path.cwd() / plugin_id
    if plugin_dir.exists():
        click.echo(f"Error: Directory {plugin_id} already exists", err=True)
        raise click.Abort()

    # Validate plugin_id
    if not _validate_plugin_id(plugin_id):
        click.echo("Error: Plugin ID must be lowercase with hyphens (e.g., my-plugin)", err=True)
        raise click.Abort()

    # Create directory structure
    src_dir = plugin_dir / plugin_id.replace("-", "_")
    src_dir.mkdir(parents=True)
    (plugin_dir / "tests").mkdir()

    plugin_name = name or plugin_id.replace("-", " ").title()
    plugin_author = author or ""
    plugin_email = email or ""
    plugin_description = description or f"A plugin for {plugin_id}"
    class_name = _to_class_name(plugin_id)

    # Generate files based on template
    _write_manifest(plugin_dir, plugin_id, plugin_name, plugin_description, plugin_author)
    _write_pyproject(plugin_dir, plugin_id, plugin_name, plugin_description, plugin_author, plugin_email)
    _write_plugin_code(src_dir, plugin_id, class_name, plugin_name, plugin_description, plugin_author, template)
    _write_tests(plugin_dir, plugin_id, class_name)
    _write_readme(plugin_dir, plugin_id, plugin_name, plugin_description, plugin_author, template)

    click.echo(click.style(f"✓ Plugin '{plugin_id}' created successfully!", fg="green", bold=True))
    click.echo(f"\n📁 Location: {plugin_dir}")
    click.echo(f"📝 Template: {template}")
    click.echo("\nNext steps:")
    click.echo(f"  cd {plugin_id}")
    click.echo('  pip install -e ".[dev]"')
    click.echo("  kairon-plugin test")
    click.echo("  kairon-plugin validate")


def _validate_plugin_id(plugin_id: str) -> bool:
    """Validate plugin ID format (kebab-case)."""
    if not plugin_id:
        return False
    if plugin_id[0] == "-" or plugin_id[-1] == "-":
        return False
    allowed = set("abcdefghijklmnopqrstuvwxyz0123456789-")
    return all(c in allowed for c in plugin_id)


def _to_class_name(plugin_id: str) -> str:
    """Convert kebab-case to CamelCase."""
    return "".join(word.capitalize() for word in plugin_id.replace("-", "_").split("_")) + "Plugin"


def _to_module_name(plugin_id: str) -> str:
    """Convert kebab-case to module_name."""
    return plugin_id.replace("-", "_")


def _write_manifest(plugin_dir: Path, plugin_id: str, name: str, description: str, author: str) -> None:
    """Write plugin.yaml manifest."""
    manifest = {
        "plugin": {
            "id": plugin_id,
            "version": "1.0.0",
            "name": name,
            "description": description,
            "author": author,
            "tags": ["plugin"],
            "capabilities": [],
        }
    }

    with open(plugin_dir / "plugin.yaml", "w") as f:
        yaml.dump(manifest, f, default_flow_style=False, sort_keys=False)


def _write_pyproject(plugin_dir: Path, plugin_id: str, name: str, description: str, author: str, email: str) -> None:
    """Write pyproject.toml."""
    module_name = _to_module_name(plugin_id)
    author_str = f'"{author}"' if not email else f'{{name = "{author}", email = "{email}"}}'

    content = f'''[build-system]
requires = ["setuptools>=61.0", "wheel"]
build-backend = "setuptools.build_meta"

[project]
name = "{plugin_id}"
version = "1.0.0"
description = "{description}"
readme = "README.md"
license = {{text = "MIT"}}
authors = [{author_str}]
requires-python = ">=3.10"
dependencies = [
    "kairon-plugin-sdk>=1.0.0",
]
classifiers = [
    "Development Status :: 3 - Alpha",
    "Intended Audience :: Developers",
    "License :: OSI Approved :: MIT License",
    "Programming Language :: Python :: 3",
    "Programming Language :: Python :: 3.10",
    "Programming Language :: Python :: 3.11",
    "Programming Language :: Python :: 3.12",
]

[project.optional-dependencies]
dev = [
    "pytest>=7.0",
    "pytest-asyncio>=0.20",
    "mypy>=1.0",
]

[project.entry-points."kairon.plugins"]
{module_name} = "{module_name}.plugin:{_to_class_name(plugin_id)}"

[tool.setuptools.packages.find]
where = ["."]
include = ["{module_name}*"]

[tool.mypy]
python_version = "3.10"
warn_return_any = true
warn_unused_configs = true
'''

    with open(plugin_dir / "pyproject.toml", "w") as f:
        f.write(content)


def _write_plugin_code(
    src_dir: Path, plugin_id: str, class_name: str, name: str, description: str, author: str, template: str
) -> None:
    """Write plugin implementation."""
    if template == "basic":
        code = f'''"""
{name} - {description}
"""

from __future__ import annotations

from typing import Any

from kairon_plugin_sdk import BosPlugin


class {class_name}(BosPlugin):
    """
    {name}.

    {description}
    """

    plugin_id = "{plugin_id}"
    plugin_version = "1.0.0"
    plugin_name = "{name}"
    plugin_description = "{description}"
    plugin_author = "{author}"
    plugin_tags = ["plugin"]
    plugin_capabilities = []

    def __init__(self):
        super().__init__()
        self._config: dict[str, Any] = {{}}

    def configure(self, config: dict[str, Any]) -> None:
        """Configure the plugin."""
        self._config = config

    def execute(self, action: str, **kwargs) -> dict[str, Any]:
        """
        Execute plugin actions.

        Args:
            action: Action to perform
            **kwargs: Action parameters

        Returns:
            Action result
        """
        actions = {{
            "hello": self._hello,
        }}

        handler = actions.get(action)
        if handler is None:
            return {{
                "status": "error",
                "error": f"Unknown action: {{action}}"
            }}

        return handler(**kwargs)

    def _hello(self, name: str = "World") -> dict[str, Any]:
        """Say hello."""
        return {{
            "status": "success",
            "message": f"Hello, {{name}}!"
        }}
'''
    elif template == "api":
        code = f'''"""
{name} - {description}
"""

from __future__ import annotations

from typing import Any

import requests

from kairon_plugin_sdk import BosPlugin


class {class_name}(BosPlugin):
    """
    {name}.

    {description}
    """

    plugin_id = "{plugin_id}"
    plugin_version = "1.0.0"
    plugin_name = "{name}"
    plugin_description = "{description}"
    plugin_author = "{author}"
    plugin_tags = ["integration", "api"]
    plugin_capabilities = ["api-access"]

    def __init__(self):
        super().__init__()
        self._config: dict[str, Any] = {{}}
        self._session: requests.Session | None = None

    def configure(self, config: dict[str, Any]) -> None:
        """Configure the plugin with API credentials."""
        self._config = config
        self._session = requests.Session()
        self._session.headers["Authorization"] = f"Bearer {{config.get('api_key', '')}}"

    def execute(self, action: str, **kwargs) -> dict[str, Any]:
        """Execute plugin actions."""
        if self._session is None:
            return {{"status": "error", "error": "Not configured"}}

        actions = {{
            "get": self._api_get,
            "post": self._api_post,
        }}

        handler = actions.get(action)
        if handler is None:
            return {{"status": "error", "error": f"Unknown action: {{action}}"}}

        return handler(**kwargs)

    def _api_get(self, endpoint: str) -> dict[str, Any]:
        """Make GET request."""
        base_url = self._config.get("base_url", "")
        response = self._session.get(f"{{base_url}}/{{endpoint}}")
        response.raise_for_status()
        return {{"status": "success", "data": response.json()}}

    def _api_post(self, endpoint: str, data: dict) -> dict[str, Any]:
        """Make POST request."""
        base_url = self._config.get("base_url", "")
        response = self._session.post(f"{{base_url}}/{{endpoint}}", json=data)
        response.raise_for_status()
        return {{"status": "success", "data": response.json()}}

    def health_check(self) -> dict[str, Any]:
        """Check API connectivity."""
        health = super().health_check()

        if self._session is None:
            health["status"] = "unhealthy"
            health["error"] = "Not configured"
        else:
            try:
                self._api_get("health")
                health["api"] = "healthy"
            except Exception as e:  # noqa: BLE001
                health["status"] = "degraded"
                health["api"] = f"error: {{e}}"

        return health
'''
    else:  # advanced
        code = f'''"""
{name} - {description}
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from kairon_plugin_sdk import BosPlugin


@dataclass
class {class_name}Config:
    """Plugin configuration."""
    api_key: str
    base_url: str = "https://api.example.com"
    timeout: int = 30

    @classmethod
    def from_dict(cls, config: dict[str, Any]) -> {class_name}Config:
        """Create config from dict."""
        return cls(
            api_key=config.get("api_key", ""),
            base_url=config.get("base_url", "https://api.example.com"),
            timeout=config.get("timeout", 30)
        )


class {class_name}(BosPlugin):
    """
    {name}.

    {description}
    """

    plugin_id = "{plugin_id}"
    plugin_version = "1.0.0"
    plugin_name = "{name}"
    plugin_description = "{description}"
    plugin_author = "{author}"
    plugin_tags = ["plugin", "advanced"]
    plugin_capabilities = ["config-management"]

    def __init__(self):
        super().__init__()
        self._config: {class_name}Config | None = None

    def configure(self, config: dict[str, Any]) -> None:
        """Configure the plugin."""
        self._config = {class_name}Config.from_dict(config)

    def execute(self, action: str, **kwargs) -> dict[str, Any]:
        """Execute plugin actions."""
        if self._config is None:
            return {{"status": "error", "error": "Not configured"}}

        actions = {{
            "status": self._status,
            "configure": self._update_config,
        }}

        handler = actions.get(action)
        if handler is None:
            return {{"status": "error", "error": f"Unknown action: {{action}}"}}

        return handler(**kwargs)

    def _status(self) -> dict[str, Any]:
        """Get plugin status."""
        return {{
            "status": "success",
            "config": {{
                "base_url": self._config.base_url,
                "timeout": self._config.timeout,
                "has_api_key": bool(self._config.api_key)
            }}
        }}

    def _update_config(self, **kwargs) -> dict[str, Any]:
        """Update configuration."""
        for key, value in kwargs.items():
            if hasattr(self._config, key):
                setattr(self._config, key, value)
        return {{"status": "success", "message": "Config updated"}}
'''

    # Write __init__.py
    init_content = f'''"""{name}"""

from .plugin import {class_name}

__all__ = ["{class_name}"]
__version__ = "1.0.0"
'''

    with open(src_dir / "__init__.py", "w") as f:
        f.write(init_content)

    with open(src_dir / "plugin.py", "w") as f:
        f.write(code)


def _write_tests(plugin_dir: Path, plugin_id: str, class_name: str) -> None:
    """Write test files."""
    module_name = _to_module_name(plugin_id)

    test_content = f'''"""Tests for {plugin_id} plugin."""

import pytest

from {module_name} import {class_name}


class Test{class_name}:
    """Test {class_name} functionality."""

    def test_plugin_metadata(self):
        """Test plugin metadata."""
        plugin = {class_name}()
        meta = plugin.get_metadata()

        assert meta["id"] == "{plugin_id}"
        assert meta["version"] == "1.0.0"

    def test_configure(self):
        """Test plugin configuration."""
        plugin = {class_name}()
        plugin.configure({{"key": "value"}})
        # Add assertions based on your config structure

    def test_execute_without_config(self):
        """Test execute without configuration."""
        plugin = {class_name}()
        # Test that appropriate error is returned
        # Modify based on your plugin's requirements

    def test_health_check(self):
        """Test health check."""
        plugin = {class_name}()
        health = plugin.health_check()

        assert health["status"] == "healthy"
        assert health["plugin_id"] == "{plugin_id}"
'''

    conftest_content = '''"""Pytest configuration."""

import pytest
'''

    with open(plugin_dir / "tests" / "test_plugin.py", "w") as f:
        f.write(test_content)

    with open(plugin_dir / "tests" / "conftest.py", "w") as f:
        f.write(conftest_content)


def _write_readme(plugin_dir: Path, plugin_id: str, name: str, description: str, author: str, template: str) -> None:
    """Write README.md."""
    template_specific = ""
    capabilities: list[str] = []
    if template == "api":
        capabilities = ["api-access"]
        template_specific = """
## Configuration

```yaml
plugins:
  {plugin_id}:
    api_key: "your-api-key"
    base_url: "https://api.example.com"
```

## Actions

### get
```python
result = plugin.execute("get", endpoint="users")
```

### post
```python
result = plugin.execute("post", endpoint="users", data={{"name": "John"}})
```
"""
    elif template == "advanced":
        capabilities = ["config-management"]
        template_specific = """
## Configuration

```yaml
plugins:
  {plugin_id}:
    api_key: "your-api-key"
    base_url: "https://api.example.com"
    timeout: 30
```

## Actions

### status
```python
result = plugin.execute("status")
```

### configure
```python
result = plugin.execute("configure", timeout=60)
```
"""

    capabilities_section = "\n".join(f"- {capability}" for capability in capabilities) or "- (none)"

    content = f"""# {name}

{description}

## Installation

```bash
pip install -e .
```

## Usage

```python
from {plugin_id.replace("-", "_")} import {name.replace(" ", "")}Plugin

plugin = {name.replace(" ", "")}Plugin()
plugin.configure({{"key": "value"}})
result = plugin.execute("hello", name="World")
```
{template_specific}
## Capabilities

{capabilities_section}

## Development

```bash
# Install dev dependencies
pip install -e ".[dev]"

# Run tests
pytest

# Type checking
mypy {plugin_id.replace("-", "_")}/
```

## Author

{author}

## License

MIT License
"""

    with open(plugin_dir / "README.md", "w") as f:
        f.write(content)


@main.command()
@click.option("--verbose", "-v", is_flag=True)
def test(verbose: bool) -> None:
    """Run plugin tests."""
    if not (Path.cwd() / "tests").exists():
        click.echo("No tests directory found", err=True)
        raise click.Abort()

    import subprocess

    args = ["pytest", "tests/", "-v" if verbose else ""]
    args = [a for a in args if a]

    result = subprocess.run(args, capture_output=False)
    raise SystemExit(result.returncode)


@main.command()
def validate() -> None:
    """Validate plugin manifest and code."""
    plugin_dir = Path.cwd()

    # Check pyproject.toml
    pyproject_path = plugin_dir / "pyproject.toml"
    if not pyproject_path.exists():
        click.echo("✗ pyproject.toml not found", err=True)
        raise click.Abort()

    # Check plugin.yaml (optional)
    manifest_path = plugin_dir / "plugin.yaml"
    if manifest_path.exists():
        with open(manifest_path) as f:
            manifest = yaml.safe_load(f)

        plugin_data = manifest.get("plugin", {})
        click.echo(f"Plugin: {plugin_data.get('name', 'Unknown')}")
        click.echo(f"ID: {plugin_data.get('id', 'Unknown')}")
        click.echo(f"Version: {plugin_data.get('version', 'Unknown')}")

    # Validate Python syntax
    src_dirs = list(plugin_dir.glob("*/__init__.py"))
    if not src_dirs:
        click.echo("✗ No Python package found", err=True)
        raise click.Abort()

    import py_compile

    for src_dir in [d.parent for d in src_dirs]:
        for py_file in src_dir.glob("*.py"):
            try:
                py_compile.compile(py_file, doraise=True)  # type: ignore[type-var]
            except py_compile.PyCompileError as e:
                click.echo(f"✗ Syntax error in {py_file}: {e}", err=True)
                raise click.Abort() from e

    click.echo(click.style("✓ Plugin validation passed!", fg="green"))


@main.command()
def build() -> None:
    """Build plugin package."""
    import subprocess

    # Check for pyproject.toml
    if not (Path.cwd() / "pyproject.toml").exists():
        click.echo("✗ pyproject.toml not found", err=True)
        raise click.Abort()

    click.echo("Building package...")
    result = subprocess.run(["python", "-m", "build"], capture_output=False)

    if result.returncode == 0:
        dist_dir = Path.cwd() / "dist"
        if dist_dir.exists():
            files = list(dist_dir.glob("*"))
            click.echo(click.style(f"✓ Build successful! ({len(files)} files in dist/)", fg="green"))
    else:
        click.echo("✗ Build failed", err=True)
        raise click.Abort()


@main.command()
def info() -> None:
    """Show plugin information."""
    plugin_dir = Path.cwd()

    # Try pyproject.toml first
    pyproject_path = plugin_dir / "pyproject.toml"
    if pyproject_path.exists():
        import tomllib

        with open(pyproject_path, "rb") as f:
            data = tomllib.load(f)

        project = data.get("project", {})
        click.echo(click.style("Plugin Info", bold=True))
        click.echo(f"Name: {project.get('name', 'Unknown')}")
        click.echo(f"Version: {project.get('version', 'Unknown')}")
        click.echo(f"Description: {project.get('description', 'N/A')}")

        # Show entry points
        entry_points = data.get("project", {}).get("entry-points", {})
        if "kairon.plugins" in entry_points:
            click.echo(f"\nEntry Point: {entry_points['kairon.plugins']}")

        return

    # Fallback to plugin.yaml
    manifest_path = plugin_dir / "plugin.yaml"
    if manifest_path.exists():
        with open(manifest_path) as f:
            manifest = yaml.safe_load(f)
        click.echo(json.dumps(manifest, indent=2))
        return

    click.echo("No plugin configuration found", err=True)
    raise click.Abort()


if __name__ == "__main__":
    main()
