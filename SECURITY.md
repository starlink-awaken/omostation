# Security Policy

## Supported Versions

| Version | Supported          |
| ------- | ------------------ |
| `main`  | :white_check_mark: |

Only the latest commit on the `main` branch receives security updates. Users running older commits should rebase or upgrade.

## Reporting a Vulnerability

If you discover a security vulnerability in OMO, please report it responsibly:

1. **Do not open a public issue** for undisclosed security problems.
2. Open a private security advisory on the repository, or contact the maintainers listed in [`README.md`](README.md).
3. Include a clear description, steps to reproduce, and the impact you believe the issue has.

We aim to acknowledge reports within 5 business days and will work with you to validate, prioritize, and disclose the fix.

## Security Best Practices

- `.omo/` state files are governed; use broker/CLI, not ad-hoc writes.
- Audit logs are evidence; protect them from tampering.

## Disclosure Policy

- We follow a coordinated disclosure process.
- Once a fix is released, we will publish a security advisory and update the workspace [`CHANGELOG.md`](../../CHANGELOG.md) with the relevant details.
