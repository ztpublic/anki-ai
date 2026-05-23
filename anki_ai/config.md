# Anki AI Configuration

`enabled` controls whether the add-on's basic functionality should be considered active.

The current scaffold always registers the test menu item. Future features can use this value to gate behavior.

`generation` controls the agent-backed card generator. `agentProvider` defaults
to `claude` for backward compatibility; set it to `codex` to use the Codex SDK
runner instead. Anki launched from Finder or Spotlight usually does not inherit
shell environment variables, so set auth values here when the generator needs
provider credentials. For local development, you can put the same `generation`
object in ignored `anki_ai/config.local.json`; local values override
`config.json`.
The add-on also reads simple `export KEY=value` or `KEY=value` assignments for
the mapped environment keys from common shell startup files such as `~/.zshrc`.
It reads assignments only; it does not execute shell code.

- `agentProvider`: `claude` or `codex`.
- `anthropicApiKey`: maps to `ANTHROPIC_API_KEY`.
- `anthropicAuthToken`: maps to `ANTHROPIC_AUTH_TOKEN`.
- `anthropicBaseUrl`: maps to `ANTHROPIC_BASE_URL`.
- `anthropicModel`: maps to `ANTHROPIC_MODEL`.
- `claudeCodeOAuthToken`: maps to `CLAUDE_CODE_OAUTH_TOKEN`.
- `claudeConfigDir`: maps to `CLAUDE_CONFIG_DIR`.
- `claudeCliPath`: optional absolute path to the Claude Code executable.
- `codexApiKey`: maps to `OPENAI_API_KEY`; omit it to reuse existing Codex auth.
- `codexModel`: optional Codex model override.
- `codexReasoningEffort`: optional reasoning effort override; defaults to `high`.
- `codexCliPath`: optional absolute path to a specific Codex executable.
