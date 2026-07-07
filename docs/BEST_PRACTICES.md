# Best Practices

## Code

- Write small, focused functions with clear names.
- Add docstrings to public APIs.
- Keep tests close to the code they test.
- Avoid hard-coding runtime facts; use workspace SSOT registries.

## Documentation

- Update `README.md` when public interfaces change.
- Keep `CHANGELOG.md` current.
- Use Mermaid diagrams for architecture flows.
- Follow the workspace documentation SSOT contract.

## Security

- Never commit secrets or credentials.
- Report security issues privately per [`SECURITY.md`](SECURITY.md).
- Review dependency updates for supply-chain risks.

## Operations

- Run the full test suite before opening a PR.
- Keep commits atomic and messages descriptive.
- Prefer small, reviewable PRs over large sweeping changes.
