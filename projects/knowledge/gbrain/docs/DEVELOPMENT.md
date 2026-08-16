# Development Guide

Thank you for contributing to this project. This guide covers how to set up a local development environment, run tests, and submit changes.

## Development Environment

1. Install [Bun](https://bun.sh/) and Node.js LTS.
2. Clone the workspace recursively:
   ```bash
   git clone --recursive https://github.com/starlink-awaken/omostation.git
   cd omostation/projects/gbrain
   ```
3. Install dependencies:
   ```bash
   bun install
   ```
4. Run the test suite:
   ```bash
   bun test
   ```

## Project Structure

- `src/` — Source code
- `tests/` — Tests
- `docs/` — Documentation
- `README.md` — Project overview

## Coding Conventions

- Follow the existing style in the codebase.
- Add tests for new functionality.
- Keep documentation in sync with code changes.

## Submitting Changes

1. Open an issue to discuss large changes.
2. Create a feature branch from `main`.
3. Make focused commits with clear messages.
4. Ensure tests pass locally.
5. Open a pull request and fill out the template.

## Releasing

See [`RELEASE.md`](RELEASE.md) for the release checklist.
