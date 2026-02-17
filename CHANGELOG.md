# Changelog

All notable changes to this project will be documented in this file.
Format: [Keep a Changelog](https://keepachangelog.com/). Commits: [Conventional Commits](https://www.conventionalcommits.org/).

## [0.1.0] - 2026-02-17

### Added
- Initial addon structure for Blender 4.x
- Sidebar panel UI (N-Key → "40K Terrain" category)
- **Wall Segment** generator: parametric wall with gothic arch windows, buttresses, panel lines
- **Corner Ruin** generator: L-shaped two-wing ruin piece
- **Pillar Cluster** generator: grouped gothic pillars on shared base platform
- Gothic detail primitives: pointed arches, tapered buttresses, pillars with base/capital
- Battle damage system: top edge crumbling, bullet holes, chunk removal (intensity 0–1)
- Connector system: pin male/female, magnet seat pockets (parametric tolerances)
- Auto-split for BambuLab A1 print bed (256×256×256mm)
- Mesh cleanup utility: merge by distance, recalc normals, dissolve degenerate, apply transforms
- Boolean operations with EXACT solver (FAST fallback)
- Random seed for reproducible procedural variation
- GitHub Actions: release workflow (tag → zip → GitHub Release), PR checks (lint, validate)
- Issue templates: bug report, feature request, task
- Project memory system: PROJECT_STATE.md, session brief template, new session prompt
- update_project_state.py tool for CI freshness checks
