# PROJECT STATE — terrain40k

> **Single Source of Truth** for the terrain40k Blender addon project.
> Last updated: 2026-02-17 | Version: 0.1.0

---

## Current Version
`0.1.0` — Initial release

## Implemented Features

- [x] Blender 4.x addon structure (register/unregister, bl_info)
- [x] Sidebar Panel UI (N-Key → "40K Terrain")
- [x] Wall Segment generator (windows, buttresses, panel lines)
- [x] Corner Ruin generator (L-shaped, two-wing)
- [x] Pillar Cluster generator (grouped pillars on base)
- [x] Gothic arch window cutters (parametric pointed arches)
- [x] Buttress primitives (tapered)
- [x] Pillar primitives (shaft + base + capital)
- [x] Battle damage system (edge damage, bullet holes, chunk removal)
- [x] Connector system (pins male/female, magnet pockets)
- [x] Auto-split for BambuLab A1 print bed (256×256×256mm)
- [x] Mesh cleanup utility (merge by distance, recalc normals, apply transforms)
- [x] Random seed for reproducible variation
- [ ] Floor Count / multi-story support
- [ ] Arch Ruin module
- [ ] Platform / floor module
- [ ] Scatter Debris standalone module
- [ ] Aquila relief details (basic version exists, not wired to UI)
- [ ] Rivet details (function exists, not wired to UI)
- [ ] Voronoi fracture (optional, off by default)
- [ ] STL/3MF batch export operator

## Module Types

| Module | Status | File |
|--------|--------|------|
| Wall Segment | Done | `generator/wall_segment.py` |
| Corner Ruin | Done | `generator/corner_ruin.py` |
| Pillar Cluster | Done | `generator/pillar_cluster.py` |
| Arch Ruin | Planned | — |
| Platform | Planned | — |
| Scatter Debris | Planned | — |

## Parameters / Defaults

| Parameter | Default | Range | Notes |
|-----------|---------|-------|-------|
| Wall Thickness | 3.0 mm | 1.6–10.0 | Min 1.6 for FDM |
| Width | 100 mm | 20–500 | ~4" game scale |
| Height | 80 mm | 15–300 | ~3" game scale |
| Window Count | 2 | 0–6 | Per wall segment |
| Detail Level | 1 | 0–3 | |
| Gothic Style | 1 | 0–3 | |
| Damage Intensity | 0.3 | 0.0–1.0 | |
| Pin Tolerance | 0.25 mm | 0.1–0.5 | Per side |
| Magnet Diameter | 5.0 mm | 3–10 | Common: 5×2 or 6×2 |
| Bevel Width | 0.0 mm | 0–3 | 0 = off |
| Print Bed | 256×256×256 mm | — | BambuLab A1 |

## Known Issues / Bugs

No open bug issues.

## Next Tasks (Roadmap)

### v0.2.0
- [ ] Implement multi-floor walls (floor_count parameter)
- [ ] Add Arch Ruin module type
- [ ] Add Platform/Floor module type
- [ ] Wire Aquila/Rivet details to detail_level 3
- [ ] Add STL batch export operator

### v0.3.0
- [ ] Scatter Debris standalone module
- [ ] Voronoi fracture option (off by default)
- [ ] Preset system (save/load parameter sets)
- [ ] Edge highlighting for painting guides

### Future
- [ ] Kill Team layout presets
- [ ] Base/plinth integration
- [ ] Texture/UV mapping for painting reference

## Decisions Log

| Date | Decision | Rationale |
|------|----------|-----------|
| 2026-02-17 | 1 BU = 1 mm | Standard for 3D print workflows in Blender |
| 2026-02-17 | EXACT boolean solver, FAST fallback | EXACT is most reliable for manifold output |
| 2026-02-17 | Min wall thickness 1.6mm, default 3mm | FDM reliability on 0.4mm nozzle |
| 2026-02-17 | Gothic arch = sine-curve approximation | True circular arcs cause more boolean issues; visual difference is minimal at print scale |
| 2026-02-17 | No Voronoi in v0.1 | Watertight Voronoi requires complex post-processing; defer to v0.3 |
| 2026-02-17 | Connectors as boolean ops, not separate meshes | Ensures single watertight mesh per module |

## Test Checklist

Before each release, verify:

- [ ] Addon installs in Blender 4.x without errors
- [ ] Each module type generates without exceptions
- [ ] Generated meshes pass Blender's "3D Print Toolbox" manifold check
- [ ] No non-manifold edges (Select → Select All by Trait → Non Manifold = 0)
- [ ] Exported STL opens in BambuStudio without errors
- [ ] Wall thickness ≥ 1.6mm in thinnest section
- [ ] Pieces fit within 256×256×256mm (or are auto-split)
- [ ] Connectors align between matching pieces
- [ ] Damage at intensity=0 produces no damage
- [ ] Damage at intensity=1 still produces printable geometry
