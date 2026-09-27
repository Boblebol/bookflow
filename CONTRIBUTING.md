# Contributing to BookFlow Studio

Thank you for considering contributing to BookFlow Studio!

## Development Workflow

1. Fork or branch from `main`.
2. Install dependencies with `uv`:
   ```bash
   uv sync
   ```
3. Run test suite:
   ```bash
   uv run pytest
   ```

## Commit Guidelines

We strictly follow [Conventional Commits](https://www.conventionalcommits.org/):
- `feat:` A new feature or capability
- `fix:` A bug fix
- `docs:` Documentation improvements
- `refactor:` Code improvements without behavioral changes
- `test:` Adding or improving tests
- `chore:` Maintenance tasks

## Pull Requests

1. Ensure all tests pass.
2. Provide a clear description and testing evidence.
3. Open a PR against `main`.
