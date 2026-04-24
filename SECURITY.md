# Security Policy

## Supported Versions

Security fixes are applied to the latest published release and `main`.

## Reporting a Vulnerability

Please report vulnerabilities privately by opening a confidential security advisory on GitHub or contacting the maintainer directly.

Include:

- Affected version/commit
- Impact summary
- Reproduction steps
- Suggested mitigation (if known)

## Secrets Handling

RAYS-CORE is designed to read API keys from environment variables at runtime.

- Do not commit secrets to repository files.
- Do not persist real API keys in `config.yaml`.
- Rotate keys immediately if accidentally exposed.

## Hardening Recommendations

- Use least-privilege API keys.
- Restrict provider billing/project scope where possible.
- Run in isolated virtual environments.
- Review generated code before deployment.

