# AgentBridge

Open-source, local-first coordination for Claude Code and Codex.

## What works
- A real localhost web dashboard and SQLite workflow history
- Sequential Claude → Codex or Codex → Claude workflows
- Each agent receives the previous agent's captured output
- Read-only/plan-mode agent commands, timeouts, and an execution-disabled default
- No cloud hosting or dependencies beyond Python 3.10+

**Alpha software:** No live authenticated Claude/Codex execution has been verified yet. This is not a security sandbox: agent processes may access files and credentials available to the operating-system user. Run only in a dedicated restricted account/container with no access to other projects.

## Run
```bash
python3 -m agentbridge.server
```
Open http://127.0.0.1:8765. By default, you can inspect the dashboard but cannot run agents.

To enable execution **only in an isolated environment** with both CLIs installed:
```bash
python3 -m agentbridge.server --allow-execution
```

Data is stored in `~/.agentbridge/agentbridge.sqlite3`. Agent commands run in `~/.agentbridge/workspace`.

## Security limitations
- Never expose the server beyond localhost.
- CLI execution inherits the dedicated OS account's file permissions; environment filtering alone does not isolate it.
- No authentication is provided; this is a single-user localhost tool.
- No automatic repository modifications or deployment integration.
- Explicitly review costs and permissions before running real agents.

## Roadmap
- Container-based isolation and least-privilege credentials
- End-to-end tests with installed agent CLIs
- Approval gates, cancellation, and cost limits
- Contribution documentation and release packaging

MIT licensed. Completely independent of Atpresli business projects.
