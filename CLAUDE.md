# phantominvestigator
<!-- token-kit. Loaded on every Claude turn: keep it under ~80 lines, facts only. -->

## Stack
- Node (npm) in `ui`
- Python in `agent` (requirements.txt)

## Commands
- Build: `cd ui && npm run build`
- Test one: `pytest -q -k <name>`

## Layout
- `agent/` — TODO
- `demo-app/` — TODO
- `docs/` — TODO
- `monitoring/` — TODO
- `runbooks/` — TODO
- `scripts/` — TODO
- `ui/` — TODO

## Conventions
- TODO (naming, error handling, where new endpoints/components go)

## Working rules
- One task per session; /clear between tasks. Keep plans in docs/plan.md.
- Global token rules: ~/.claude/CLAUDE.md
