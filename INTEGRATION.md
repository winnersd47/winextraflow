# WinExtraFlow — nextlevelbuilder Integrations

## ui-ux-pro-max-skill
Installed via `uipro init --ai claude`. Provides 192-rule design system for frontend.
**How to use:** Claude Code now has design intelligence built in. Ask it to improve any UI component.

## GoClaw AI Agent Gateway
**What it does:** Routes Telegram signal broadcasting through GoClaw's multi-agent pipeline.
**Files:**
- `backend/app/services/goclaw_telegram.py` — GoClaw Telegram adapter
- `backend/app/config.py` — GOCLAW_URL, GOCLAW_TOKEN vars

**Setup:**
1. Deploy GoClaw (see GOCLAW_DEPLOY.md)
2. Set GOCLAW_URL and GOCLAW_TOKEN in Railway env vars
3. GoClaw routes signals with enhanced context and 5-layer security

## goclaw-mcp
Added to Claude Code MCP config. Enables 66 management tools for GoClaw directly in Claude.
