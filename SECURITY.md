# Security Policy

## Supported Versions

| Version | Supported          |
| ------- | ------------------ |
| `main`  | :white_check_mark: |

Only the latest commit on the `main` branch receives security updates. Users running older commits should rebase or upgrade.

## Reporting a Vulnerability

If you discover a security vulnerability in ecos, please report it responsibly:

1. **Do not open a public issue** for undisclosed security problems.
2. Open a private security advisory on the repository, or contact the maintainers listed in [`README.md`](README.md).
3. Include a clear description, steps to reproduce, and the impact you believe the issue has.

We aim to acknowledge reports within 5 business days and will work with you to validate, prioritize, and disclose the fix.

## Security Best Practices

- L0 constraints are authoritative; mutations require governance workflow.
- Guard MOF tool execution against untrusted inputs.

## Disclosure Policy

- We follow a coordinated disclosure process.
- Once a fix is released, we will publish a security advisory and update the workspace [`CHANGELOG.md`](../../CHANGELOG.md) with the relevant details.
