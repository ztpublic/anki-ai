# Anki AI Configuration

`enabled` controls whether the add-on's basic functionality should be considered active.

The current scaffold always registers the test menu item. Future features can use this value to gate behavior.

`generation` controls the Claude Code-backed card generator. Anki launched from
Finder or Spotlight usually does not inherit shell environment variables, so set
these values here when the generator needs a custom Anthropic-compatible
endpoint. For local development, you can put the same `generation` object in
ignored `anki_ai/config.local.json`; local values override `config.json`.
The add-on also reads simple `export KEY=value` or `KEY=value` assignments for
the mapped environment keys from common shell startup files such as `~/.zshrc`.
It reads assignments only; it does not execute shell code.

- `anthropicApiKey`: maps to `ANTHROPIC_API_KEY`.
- `anthropicAuthToken`: maps to `ANTHROPIC_AUTH_TOKEN`.
- `anthropicBaseUrl`: maps to `ANTHROPIC_BASE_URL`.
- `anthropicModel`: maps to `ANTHROPIC_MODEL`.
- `claudeCodeOAuthToken`: maps to `CLAUDE_CODE_OAUTH_TOKEN`.
- `claudeConfigDir`: maps to `CLAUDE_CONFIG_DIR`.
- `claudeCliPath`: optional absolute path to the Claude Code executable.
