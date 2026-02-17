# Changelog Rules

## Format
We follow [Keep a Changelog](https://keepachangelog.com/) with [Conventional Commits](https://www.conventionalcommits.org/).

## Commit Message Format
```
<type>(<scope>): <short description>

<optional body>
```

### Types
- `feat` — New feature or module
- `fix` — Bug fix
- `refactor` — Code restructuring, no behavior change
- `docs` — Documentation only
- `chore` — Build, CI, tooling
- `test` — Test additions/changes

### Scopes
- `wall`, `corner`, `pillar` — Specific generators
- `damage`, `connectors`, `splitter` — Subsystems
- `ui`, `props`, `ops` — Addon interface
- `mesh` — Mesh utilities
- `ci` — GitHub Actions

### Examples
```
feat(wall): add gothic window sill detail at style level 2
fix(damage): prevent thin-wall violation at high intensity
chore(ci): add Blender headless lint step
```

## CHANGELOG.md Entries
Each version section uses these categories:
- **Added** — New features
- **Changed** — Changes to existing features
- **Fixed** — Bug fixes
- **Removed** — Removed features

## Version Bumping
- `PATCH` (0.1.x): bug fixes, small tweaks
- `MINOR` (0.x.0): new module types, new features
- `MAJOR` (x.0.0): breaking changes to API/parameters

## Release Process
1. Update `bl_info["version"]` in `__init__.py`
2. Update `CHANGELOG.md` with new version section
3. Commit: `chore: release vX.Y.Z`
4. Tag: `git tag vX.Y.Z`
5. Push: `git push origin main --tags`
6. GitHub Action builds zip and creates release
