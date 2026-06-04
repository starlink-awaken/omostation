# Contributing to omo-debt

Thank you for your interest in contributing to omo-debt! This document provides guidelines and instructions for contributing.

## Table of Contents

1. [Code of Conduct](#code-of-conduct)
2. [Getting Started](#getting-started)
3. [Development Setup](#development-setup)
4. [Making Changes](#making-changes)
5. [Testing](#testing)
6. [Submitting Changes](#submitting-changes)
7. [Code Style](#code-style)
8. [Documentation](#documentation)

---

## Code of Conduct

This project follows the [Contributor Covenant](https://www.contributor-covenant.org/) Code of Conduct. By participating, you are expected to uphold this code.

---

## Getting Started

### Prerequisites

- Python 3.13+
- [uv](https://github.com/astral-sh/uv) package manager
- Git

### Find an Issue

1. Browse [open issues](https://github.com/your-org/omo-debt/issues)
2. Look for issues labeled `good first issue` or `help wanted`
3. Comment on the issue to let others know you're working on it

---

## Development Setup

### 1. Fork and Clone

```bash
# Fork the repository on GitHub, then:
git clone https://github.com/YOUR-USERNAME/omo-debt.git
cd omo-debt
```

### 2. Install Dependencies

```bash
# Install all dependencies (including dev)
uv sync

# Verify installation
uv run python -m omo_debt.cli --version
```

### 3. Create a Branch

```bash
git checkout -b feature/your-feature-name
# or
git checkout -b fix/issue-number-description
```

---

## Making Changes

### Project Structure

```
omo-debt/
├── src/omo_debt/
│   ├── core/           # Core algorithms (stage, scoring)
│   ├── honesty/        # Honesty dimension (v2.1)
│   ├── cli.py          # CLI commands
│   ├── cli_honesty.py  # Honesty CLI commands
│   ├── models.py       # Data classes
│   └── __version__.py  # Version metadata
├── tests/
│   └── unit/           # Unit tests
├── examples/           # Real-world examples
└── docs/               # Documentation
```

### Coding Guidelines

1. **Follow existing patterns**: Study similar code before implementing
2. **Keep functions focused**: Each function should do one thing well
3. **Add type hints**: All function parameters and returns should have types
4. **Document thoroughly**: Use docstrings for all public functions

### Example: Adding a New Feature

```python
# src/omo_debt/core/new_feature.py

"""
New feature module docstring.

Explain what this module does and why it exists.
"""

from dataclasses import dataclass
from typing import Optional


@dataclass
class NewFeatureResult:
    """Result of new feature calculation.
    
    Attributes:
        score: Calculated score (0-10)
        metadata: Additional context
    """
    score: float
    metadata: dict


def calculate_new_feature(
    input_param: float,
    optional_param: Optional[str] = None
) -> NewFeatureResult:
    """Calculate new feature score.
    
    Args:
        input_param: Main input parameter (1-10)
        optional_param: Optional configuration
    
    Returns:
        NewFeatureResult object with score and metadata
    
    Examples:
        >>> result = calculate_new_feature(8.5)
        >>> result.score
        8.5
    """
    # Implementation
    return NewFeatureResult(score=input_param, metadata={})
```

---

## Testing

### Run Tests

```bash
# Run all tests
uv run pytest tests/unit/ -v

# Run specific test file
uv run pytest tests/unit/test_honesty.py -v

# Run with coverage
uv run pytest tests/unit/ --cov=src/omo_debt --cov-report=term-missing
```

### Writing Tests

1. **Location**: Place tests in `tests/unit/`
2. **Naming**: `test_<module>_<feature>.py`
3. **Structure**: Use `pytest` conventions

```python
# tests/unit/test_new_feature.py

import pytest
from omo_debt.core.new_feature import calculate_new_feature


class TestNewFeature:
    """Test cases for new feature."""
    
    def test_basic_calculation(self):
        """Test basic calculation works."""
        result = calculate_new_feature(8.5)
        assert result.score == 8.5
    
    def test_edge_case_low_value(self):
        """Test edge case with minimum value."""
        result = calculate_new_feature(0.0)
        assert result.score >= 0.0
    
    def test_edge_case_high_value(self):
        """Test edge case with maximum value."""
        result = calculate_new_feature(10.0)
        assert result.score <= 10.0
```

### Test Coverage

- **Minimum**: 80% coverage for new code
- **Target**: 90% coverage
- **Focus**: Edge cases, error handling, boundary values

---

## Submitting Changes

### 1. Commit Messages

Follow [Conventional Commits](https://www.conventionalcommits.org/):

```
<type>(<scope>): <subject>

<body>

<footer>
```

**Types**:
- `feat`: New feature
- `fix`: Bug fix
- `docs`: Documentation only
- `test`: Adding or updating tests
- `refactor`: Code change that neither fixes a bug nor adds a feature
- `perf`: Performance improvement
- `chore`: Maintenance tasks

**Examples**:
```
feat(honesty): add legacy dimension support

Implements the Legacy (L) dimension for 4P3V1L1H framework.
Includes completeness, consistency, and verifiability sub-dimensions.

Closes #42
```

```
fix(cli): correct date format in stage identification

GitPython expects date as "timestamp +offset" string,
not raw integer timestamp.

Fixes #89
```

### 2. Push and Create PR

```bash
# Push your branch
git push origin feature/your-feature-name

# Create Pull Request on GitHub
# Include:
# - Clear description of changes
# - Link to related issue(s)
# - Test results
# - Screenshots (if UI changes)
```

### 3. PR Checklist

Before submitting:

- [ ] Tests pass locally (`uv run pytest`)
- [ ] Code follows style guidelines (`ruff check .`)
- [ ] Documentation updated (if needed)
- [ ] CHANGELOG.md updated (if user-facing change)
- [ ] Commit messages follow conventions
- [ ] Branch is up-to-date with `main`

### 4. Review Process

1. Maintainers will review your PR
2. Address feedback by pushing new commits
3. Once approved, a maintainer will merge

---

## Code Style

### Python Style

- **Formatter**: `ruff format`
- **Linter**: `ruff check`
- **Line length**: 120 characters
- **Imports**: Sorted with `isort` (via ruff)

### Run Linters

```bash
# Check code
ruff check .

# Auto-fix issues
ruff check --fix .

# Format code
ruff format .
```

### Type Hints

All functions must have type hints:

```python
# Good ✅
def calculate(value: float, factor: int = 1) -> float:
    return value * factor

# Bad ❌
def calculate(value, factor=1):
    return value * factor
```

### Docstrings

Use Google-style docstrings:

```python
def function_name(param1: str, param2: int) -> bool:
    """Short one-line summary.
    
    More detailed explanation if needed. Can be multiple paragraphs.
    
    Args:
        param1: Description of param1
        param2: Description of param2
    
    Returns:
        Description of return value
    
    Raises:
        ValueError: When param2 is negative
    
    Examples:
        >>> function_name("test", 42)
        True
    """
```

---

## Documentation

### Update Documentation

When adding features, update:

1. **README.md**: If changing installation or basic usage
2. **TUTORIAL.md**: If adding new commands or workflows
3. **API.md**: If adding/changing public APIs
4. **CHANGELOG.md**: Always for user-facing changes

### Documentation Style

- **Be concise**: Get to the point quickly
- **Use examples**: Show real code snippets
- **Explain why**: Not just how, but why it matters
- **Link related docs**: Help users discover more

---

## Questions?

- **Issues**: [GitHub Issues](https://github.com/your-org/omo-debt/issues)
- **Discussions**: [GitHub Discussions](https://github.com/your-org/omo-debt/discussions)
- **Email**: maintainers@example.com

---

Thank you for contributing to omo-debt! 🎉

