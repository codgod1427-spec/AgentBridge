# Contributing to AgentBridge

AgentBridge is an early-stage open-source tool for local AI coding-agent coordination. Contributions are welcome from maintainers, testers, and documentation writers.

## Local development

Requirements: Python 3.10 or later. No dependencies are needed for the tests.

```bash
python3 -m unittest discover -s tests -v
python3 -m agentbridge.server
```

The server defaults to execution disabled. Do not enable real CLI execution while testing on a machine with access to unrelated projects.

## Pull requests
1. Open an issue for larger changes.
2. Use a feature branch and keep the change focused.
3. Add automated tests for behavior changes.
4. Explain security implications and how you tested the change.
5. Never commit API keys, account tokens, personal data, or private project files.

## Good first contributions
- Improve setup documentation for Windows and macOS.
- Add tests for malformed requests and failure recovery.
- Improve accessible dashboard status messages.
- Help design a container-based isolation layer.

No paid service or proprietary agent account is required to contribute to the core project.
