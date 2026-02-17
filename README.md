# terrain40k — Warhammer 40K Terrain Generator for Blender

Blender 4.x addon that procedurally generates modular imperial/gothic ruin terrain for Warhammer 40K tabletop gaming, optimized for FDM 3D printing on BambuLab A1.

## Features

- **3 module types**: Wall Segment, Corner Ruin, Pillar Cluster
- **Gothic details**: pointed arch windows, tapered buttresses, pillars with base/capital
- **Battle damage**: crumbling edges, bullet holes, chunk removal (adjustable intensity)
- **Modular connectors**: pin/hole and magnet seat pockets with parametric tolerances
- **Print-optimized**: manifold/watertight meshes, min 1.6mm wall thickness, auto-split for 256mm bed
- **Fully parametric**: width, height, thickness, window count, detail level, gothic style, damage, seed

## Installation

1. Download the latest `terrain40k-vX.Y.Z.zip` from [Releases](../../releases)
2. In Blender: **Edit → Preferences → Add-ons → Install**
3. Select the zip file, then enable **"40K Terrain Generator"**
4. Open the sidebar (**N** key) → **"40K Terrain"** tab

## Usage

1. Select a **Module Type** (Wall, Corner, Pillar)
2. Adjust **dimensions**, **style**, and **damage** parameters
3. Click **"Generate Module"**
4. Export as STL/3MF for slicing

### Unit Convention

This addon uses **1 Blender Unit = 1 mm**. Set your scene units accordingly or scale on export.

## Print Guidelines (BambuLab A1)

| Parameter | Value |
|-----------|-------|
| Build volume | 256 × 256 × 256 mm |
| Min wall thickness | 1.6 mm (default 3.0) |
| Min detail size | 0.6 mm |
| Nozzle | 0.4 mm |
| Layer height | 0.16–0.20 mm recommended |
| Supports | Mostly not needed (designed supportless) |
| Pin tolerance | 0.25 mm per side (adjustable) |
| Magnet seats | 5×2 mm or 6×2 mm (adjustable) |

## Game Scale

Designed for Warhammer 40K **Primaris / Kill Team** scale:
- Wall segments: 50–150 mm (2–6")
- Heights: 60–100 mm (2.5–4")
- Doors/windows sized for "heroic scale" models

## Building from Source

```bash
cd addon
zip -r ../terrain40k.zip terrain40k/
```

## Development

- Conventional commits: `feat(wall):`, `fix(damage):`, `chore(ci):`
- See `docs/CHANGELOG_RULES.md` for versioning rules
- See `docs/PROJECT_STATE.md` for current project status

## License

MIT — see [LICENSE](LICENSE)
