# Assemble plugins for Claude

Assemble's plugins for Claude Code and the Claude desktop app. **Private to Assemble** —
keep this repository private.

| Plugin | What it does |
|---|---|
| [`forma-user`](plugins/forma-user) | Autodesk Forma (ACC Cost Management): answers questions about project money, and does the Forma work for consultant contracts (contract-bot) and variations (var-bot), each write confirmed in chat. Also builds a person's Cost & Spend Desk. |

## Install

**Claude desktop app (most people).** Download the `.plugin` file from the latest
[release](../../releases), then install it through the app's plugin manager. Follow
`plugins/forma-user/INSTALL.md` for the one-time setup (Python, sign-in, the
provisioning check).

**Claude Code in a terminal.** With git signed in to GitHub (`gh auth login`, then
`gh auth setup-git`):

```bash
claude plugin marketplace add <org>/<this-repo>
claude plugin install forma-user@assemble-plugins
```

Updates arrive when the plugin's `version` in `plugins/forma-user/.claude-plugin/plugin.json`
goes up.

## Rules for this repository

- **No personal or sensitive data.** The Entity Bible in `forma-user` is an *extract* —
  entity name, purpose, addresses, ACN and ABN only. The master holds tax file numbers and
  ASIC corporate keys and must never be committed; regenerate the extract with
  `plugins/forma-user/skills/contract-bot/scripts/make_entity_extract.py`.
- **No credentials.** Sign-in uses PKCE with no client secret; tokens stay in each
  person's `~/.forma-mcp`, outside the plugin.
- **Before a release:** run `python -m forma_mcp.server --selftest` in `plugins/forma-user`,
  bump the version, add a CHANGELOG entry, and attach the built `.plugin` to the release.
