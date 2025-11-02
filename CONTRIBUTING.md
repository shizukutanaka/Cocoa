# Contributing to Cocoa

Thank you for your interest in contributing to Cocoa! This document provides guidelines and instructions for contributing.

## Code of Conduct

Please see [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md) for our community standards.

## How to Contribute

### Reporting Bugs

Before creating bug reports, check the [issue list](https://github.com/cocoa-project/cocoa/issues) as you might find out that you don't need to create one. When creating a bug report:

1. **Use a clear, descriptive title**
2. **Describe the exact steps to reproduce** the problem
3. **Provide specific examples** to demonstrate the steps
4. **Describe the behavior you observed** after following the steps
5. **Explain which behavior you expected** instead and why
6. **Include screenshots** if possible
7. **Include your environment details**: OS, Python version, installed packages

### Suggesting Enhancements

Enhancement suggestions are tracked as GitHub issues. When creating an enhancement suggestion:

1. **Use a clear, descriptive title**
2. **Provide a step-by-step description** of the suggested enhancement
3. **Provide specific examples** to demonstrate the steps
4. **Describe the current behavior** and **the expected behavior**
5. **Explain why this enhancement** would be useful

### Pull Requests

- Fill in the required template
- Follow the Python styleguide
- Include appropriate test cases
- Update documentation as needed
- End all files with a newline

## Development Setup

### Prerequisites

- Python 3.8+
- Git
- Virtual environment tool (venv)

### Local Development

1. **Fork the repository** on GitHub

2. **Clone your fork locally**:
   ```bash
   git clone https://github.com/yourusername/cocoa.git
   cd cocoa
   ```

3. **Create a virtual environment**:
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

4. **Install development dependencies**:
   ```bash
   pip install -r requirements.txt
   pip install -r requirements-dev.txt
   ```

5. **Create a feature branch**:
   ```bash
   git checkout -b feature/your-feature-name
   ```

6. **Make your changes**:
   - Write clear, descriptive commit messages
   - Add tests for new functionality
   - Follow the code style guidelines

7. **Run tests locally**:
   ```bash
   python -m pytest tests -v
   python -m pytest tests --cov=main --cov-report=html
   ```

8. **Lint your code**:
   ```bash
   pylint main/*.py
   black main/
   ```

9. **Commit and push**:
   ```bash
   git add .
   git commit -m "Descriptive message about changes"
   git push origin feature/your-feature-name
   ```

10. **Create a Pull Request** on GitHub

## Style Guide

### Python Code Style

- Follow [PEP 8](https://www.python.org/dev/peps/pep-0008/)
- Use 4 spaces for indentation
- Use descriptive variable and function names
- Add docstrings to all functions and classes
- Use type hints where applicable

### Docstring Format

```python
def function_name(param1: str, param2: int) -> bool:
    """
    Brief description of what the function does.

    Args:
        param1: Description of param1
        param2: Description of param2

    Returns:
        Description of return value

    Raises:
        ValueError: When something is invalid

    Examples:
        >>> function_name("test", 42)
        True
    """
    pass
```

### Commit Message Format

```
Type: Brief description (50 chars max)

Detailed explanation of the changes (72 chars per line).

Fixes: #issue-number
Related-To: #related-issue
```

Types: `feat`, `fix`, `docs`, `style`, `refactor`, `test`, `chore`

## Testing

### Running Tests

```bash
# Run all tests
python -m pytest tests -v

# Run specific test file
python -m pytest tests/test_cocoa.py -v

# Run with coverage
python -m pytest tests --cov=main --cov-report=html

# Run specific test
python -m pytest tests/test_cocoa.py::test_function_name -v
```

### Writing Tests

- Use `pytest` for test framework
- Place tests in `tests/` directory
- Use descriptive test names: `test_<function>_<scenario>`
- Aim for >80% code coverage
- Test both happy path and error cases

Example test:

```python
import pytest
from main.module import function_name

def test_function_succeeds_with_valid_input():
    result = function_name("valid_input")
    assert result is True

def test_function_raises_on_invalid_input():
    with pytest.raises(ValueError):
        function_name("invalid")
```

## Documentation

- Use clear, concise language
- Update README.md for significant changes
- Add docstrings to all public functions
- Update CHANGELOG.md in your PR

## Review Process

1. At least one approval required to merge
2. All checks must pass (tests, linting)
3. No merge conflicts
4. Updated documentation if needed

## Questions?

- **Documentation**: Check [docs/](docs/) directory
- **Issues**: Search [GitHub issues](https://github.com/cocoa-project/cocoa/issues)
- **Discussions**: Use [GitHub discussions](https://github.com/cocoa-project/cocoa/discussions)

Thank you for contributing to Cocoa!
