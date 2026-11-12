# AgentBridge security policy

AgentBridge is experimental software. Do not run it on an account with access to unrelated repositories, private documents, SSH keys, or production credentials.

## Current protections
- Server binds to 127.0.0.1 only.
- Browser requests are checked for a trusted Host and Origin.
- Agent execution is disabled unless explicitly enabled.
- Agent command selection is allowlisted.
- Subprocesses have a 180-second timeout and bounded output.
- Claude is invoked in plan mode and Codex in read-only sandbox mode.

## Limitations
These protections are **not a security boundary**. A local CLI may still access files, network resources, and credentials available to its operating-system user. Environment-variable filtering does not prevent reading credentials from disk. The local web server has no authentication and is intended for a single trusted user only.

## Before enabling execution
Use a separate operating-system account or disposable container with its own home directory, no mounts of unrelated repositories, no host SSH agent, no business secrets, and only scoped AI credentials. Never expose port 8765 to a public network.

## Reporting vulnerabilities
Please open a private security advisory using the GitHub repository's Security tab if available. Avoid publishing working exploits or secrets in public issues.
