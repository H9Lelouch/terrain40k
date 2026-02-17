# Session Brief — terrain40k

> Copy this into a new Claude session as context. Fill in the "This Session" section.

## Project
Blender 4.x addon: procedural Warhammer 40K terrain (imperial gothic ruins), FDM-optimized for BambuLab A1 (256³mm bed). All meshes must be manifold/watertight/boolean-safe. 1 BU = 1 mm.

## Current Version
v0.1.0

## Repo Structure
```
addon/terrain40k/        → Blender addon package
  __init__.py            → bl_info, register/unregister
  properties.py          → All UI properties
  operators.py           → Generate operator
  ui.py                  → Sidebar panel
  generator/             → Module generators
    wall_segment.py      → Wall with windows + buttresses
    corner_ruin.py       → L-shaped corner
    pillar_cluster.py    → Pillar group on base
    gothic_details.py    → Arch, pillar, buttress primitives
    damage.py            → Battle damage (booleans)
    connectors.py        → Pins / magnet seats
    splitter.py          → Auto-split for print bed
  utils/mesh.py          → cleanup_mesh, boolean ops, primitives
docs/                    → PROJECT_STATE.md, templates
tools/                   → update_project_state.py
.github/                 → CI workflows, issue templates
```

## Last Changes
- (fill in from CHANGELOG.md)

## Open Issues
- (fill in from GitHub Issues or PROJECT_STATE.md "Known Issues")

## This Session Goals
- [ ] (fill in your goals for this session)

## Rules
- Blender 4.x bpy only, no external dependencies
- All geometry: manifold, boolean-safe, no open edges
- Min wall thickness ≥ 1.6mm, default 3mm
- Min detail size ≥ 0.6mm (FDM)
- No placeholders / TODOs — all code must be runnable
- Small diffs, output changed files with full path headers
- Test: install addon in Blender, generate each module type

## Build/Zip
```bash
cd addon && zip -r ../terrain40k.zip terrain40k/
```
