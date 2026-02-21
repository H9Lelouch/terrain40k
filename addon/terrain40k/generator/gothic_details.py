"""
Gothic architectural detail primitives for Warhammer 40K terrain.
Based on Sector Imperialis / Imperial Gothic architecture:
- Pointed arches, ribbed vaults, flying buttresses
- Skull motifs, Imperial Aquila (double-headed eagle)
- Fluted columns with base/capital
- Pilaster strips (wall-embedded half-columns)
- Stone block mortar lines
All dimensions in mm (1 BU = 1 mm).
"""

import bpy
import bmesh
import math
from mathutils import Vector
from ..utils.mesh import (
    create_box_object,
    create_cylinder_object,
    extrude_profile_to_solid,
    create_box_bmesh,
    create_object_from_bmesh,
    boolean_union,
    boolean_difference,
)


# ── Gothic Arch ────────────────────────────────────────────────────────────

def gothic_arch_profile(width, height, segments=12):
    """
    Generate 2D profile points (x, z) for a gothic pointed arch.
    Authentic lancet arch: two arcs whose centers are at the base,
    producing the characteristic narrow pointed shape.
    """
    hw = width / 2.0
    # Lower rectangular portion (~50% of height)
    rect_h = height * 0.50
    arch_h = height - rect_h
    points = []
    points.append((-hw, 0))
    points.append((-hw, rect_h))
    # Pointed arch: each arc centered at the opposite base corner
    # Radius = full width for equilateral pointed arch
    radius = width
    n = max(segments // 2, 4)
    # Left arc: center at (hw, rect_h), sweeps from (-hw, rect_h) to peak
    start_angle = math.atan2(0, -width)  # = pi
    peak_y = arch_h
    peak_angle = math.atan2(peak_y, -hw)
    for i in range(1, n + 1):
        t = i / n
        angle = start_angle + t * (peak_angle - start_angle)
        x = hw + radius * math.cos(angle)
        z = rect_h + radius * math.sin(angle)
        # Clamp z to not exceed height
        z = min(z, height)
        points.append((x, z))
    # Right arc: center at (-hw, rect_h), sweeps from peak to (hw, rect_h)
    peak_angle_r = math.atan2(peak_y, hw)
    end_angle = 0.0
    for i in range(1, n):
        t = i / n
        angle = peak_angle_r + t * (end_angle - peak_angle_r)
        x = -hw + radius * math.cos(angle)
        z = rect_h + radius * math.sin(angle)
        z = min(z, height)
        points.append((x, z))
    points.append((hw, rect_h))
    points.append((hw, 0))
    return points


def create_gothic_arch_cutter(width, height, depth, segments=12, name="ArchCutter"):
    """Create a solid gothic arch shape for boolean cutting (windows/doors)."""
    profile = gothic_arch_profile(width, height, segments)
    obj = extrude_profile_to_solid(profile, depth, offset_y=0.0, name=name)
    return obj


def create_arch_frame(width, height, depth, frame_thickness=1.5,
                      segments=12, name="ArchFrame"):
    """
    Create a raised arch frame / surround for a window opening.
    This is the decorative border that protrudes from the wall around windows.
    """
    # Outer arch (larger)
    outer_w = width + frame_thickness * 2
    outer_h = height + frame_thickness
    outer = create_gothic_arch_cutter(
        outer_w, outer_h, depth, segments, name=name + "_outer"
    )
    # Inner cutout (window-sized, slightly bigger to ensure clean cut)
    inner = create_gothic_arch_cutter(
        width + 0.2, height + 0.1, depth + 2.0, segments, name=name + "_inner"
    )
    inner.location.z = -0.05
    bpy.context.view_layer.objects.active = inner
    inner.select_set(True)
    bpy.ops.object.transform_apply(location=True)
    boolean_difference(outer, inner)
    outer.name = name
    return outer


# ── Skull Motif ────────────────────────────────────────────────────────────

def create_skull_relief(width=6.0, height=7.0, depth=1.5, name="Skull"):
    """
    Imperial skull motif for wall decoration.  FDM-optimized box-based geometry.

    Coordinate convention (matches wall placement):
        local Y = 0  →  back face (flush with / inside wall surface)
        local Y < 0  →  protrudes toward viewer
        Z from 0 (bottom) to height (top)
        X from −width/2 to +width/2

    Place with:  skull.location = Vector((cx, -(t/2 - overlap), skull_z))
    where overlap ≥ 0.5 mm ensures a solid boolean union with the wall.
    """
    if width < 4.0:
        return create_box_object(width, height * 0.8, depth,
                                 location=(0, -depth / 2, 0), name=name)

    jaw_h     = height * 0.38
    cranium_h = height * 0.62
    jaw_w     = width  * 0.72
    cut_depth = depth + 2.0   # eye/nose cutters span well past front face

    # ── Cranium (upper portion, full width) ─────────────────────────────
    # Y: loc_y ± depth/2  →  -depth/2 ± depth/2  =  [-depth, 0]   ✓
    cranium = create_box_object(
        width, cranium_h, depth,
        location=(0, -depth / 2, jaw_h), name="_cranium"
    )

    # ── Jaw (lower portion, narrower, slightly shallower) ────────────────
    # Y: -depth*0.35 ± depth*0.35  =  [-0.7*depth, 0]               ✓
    jaw = create_box_object(
        jaw_w, jaw_h, depth * 0.7,
        location=(0, -depth * 0.35, 0), name="_jaw"
    )
    boolean_union(cranium, jaw)

    # ── Eye sockets (rectangular — better at FDM scale) ──────────────────
    eye_w = width  * 0.22
    eye_h = height * 0.18
    eye_x = width  * 0.26
    eye_z = jaw_h  + cranium_h * 0.38
    for side in [-1, 1]:
        eye = create_box_object(
            eye_w, eye_h, cut_depth,
            location=(side * eye_x, -depth / 2, eye_z), name="_eye"
        )
        boolean_difference(cranium, eye)

    # ── Nose cavity ───────────────────────────────────────────────────────
    nose_w = width  * 0.15
    nose_h = height * 0.13
    nose_z = jaw_h  + cranium_h * 0.08
    nose = create_box_object(
        nose_w, nose_h, cut_depth,
        location=(0, -depth / 2, nose_z), name="_nose"
    )
    boolean_difference(cranium, nose)

    # ── Tooth gaps (only if skull wide enough for FDM) ───────────────────
    if width >= 7.0:
        tgw = width  * 0.11
        tgh = jaw_h  * 0.38
        for tx in (-width * 0.17, 0.0, width * 0.17):
            tg = create_box_object(
                tgw, tgh, cut_depth,
                location=(tx, -depth * 0.35, 0), name="_tgap"
            )
            boolean_difference(cranium, tg)

    cranium.name = name
    return cranium


# ── Imperial Aquila ────────────────────────────────────────────────────────

def create_aquila_relief(width, height, depth=1.2, name="Aquila"):
    """
    Create a simplified Imperial Aquila (double-headed eagle) relief.
    Geometric V-wing shape with central skull, printable on FDM.
    Width should be >= 15mm for recognizable detail.
    """
    # Main body: diamond/chevron shape
    # Build from profile extrusion for clean geometry
    hw = width / 2.0
    hh = height / 2.0
    wing_droop = height * 0.15  # wings angle down slightly

    # Aquila profile: wide V-shape (wings) with center body
    profile = [
        (-hw, -wing_droop),           # left wingtip
        (-hw * 0.7, hh * 0.3),        # left wing upper
        (-hw * 0.25, hh * 0.7),       # left shoulder
        (0, hh),                       # top center (heads)
        (hw * 0.25, hh * 0.7),        # right shoulder
        (hw * 0.7, hh * 0.3),         # right wing upper
        (hw, -wing_droop),            # right wingtip
        (hw * 0.7, -hh * 0.2),        # right wing lower
        (hw * 0.3, -hh * 0.4),        # right body lower
        (0, -hh * 0.55),              # bottom center
        (-hw * 0.3, -hh * 0.4),       # left body lower
        (-hw * 0.7, -hh * 0.2),       # left wing lower
    ]
    obj = extrude_profile_to_solid(profile, depth, offset_y=0.0, name=name)

    # Add central skull if large enough
    if width >= 18.0:
        skull = create_skull_relief(
            width=width * 0.2, height=height * 0.3, depth=depth * 0.6,
            name="_aquila_skull"
        )
        skull.location = Vector((0, -depth * 0.3, 0))
        bpy.context.view_layer.objects.active = skull
        skull.select_set(True)
        bpy.ops.object.transform_apply(location=True)
        boolean_union(obj, skull)

    return obj


# ── Fluted Column ──────────────────────────────────────────────────────────

def create_fluted_column(radius, height, flute_count=8, flute_depth=0.6,
                         segments=16, name="FlutedColumn"):
    """
    Create a column with vertical flutes (grooves) cut into the shaft.
    Authentic gothic fluted column with base molding and capital.
    """
    base_w = radius * 2.8
    capital_w = radius * 2.6
    base_h = max(height * 0.08, 2.5)
    capital_h = max(height * 0.07, 2.0)
    shaft_h = height - base_h - capital_h

    parts = []

    # Base: two-tier molding (wider bottom, slightly narrower top)
    base_lower = create_box_object(
        base_w, base_h * 0.6, base_w,
        location=(0, 0, 0), name="_base_lower"
    )
    parts.append(base_lower)
    base_upper = create_box_object(
        base_w * 0.85, base_h * 0.4, base_w * 0.85,
        location=(0, 0, base_h * 0.6), name="_base_upper"
    )
    parts.append(base_upper)

    # Shaft (cylinder)
    shaft = create_cylinder_object(
        radius, shaft_h, segments,
        location=(0, 0, base_h), name="_shaft"
    )
    parts.append(shaft)

    # Capital: two-tier (narrower bottom, wider top)
    cap_z = base_h + shaft_h
    cap_lower = create_box_object(
        capital_w * 0.8, capital_h * 0.5, capital_w * 0.8,
        location=(0, 0, cap_z), name="_cap_lower"
    )
    parts.append(cap_lower)
    cap_upper = create_box_object(
        capital_w, capital_h * 0.5, capital_w,
        location=(0, 0, cap_z + capital_h * 0.5), name="_cap_upper"
    )
    parts.append(cap_upper)

    # Union all parts
    result = parts[0]
    for part in parts[1:]:
        boolean_union(result, part, remove_other=True)

    # Cut flutes into shaft (vertical grooves)
    if flute_depth >= 0.4 and flute_count >= 4:
        flute_r = radius * 0.2  # groove width
        for i in range(flute_count):
            angle = 2 * math.pi * i / flute_count
            fx = radius * 0.85 * math.cos(angle)
            fy = radius * 0.85 * math.sin(angle)
            flute = create_cylinder_object(
                flute_r, shaft_h + 1.0, segments=6,
                location=(fx, fy, base_h - 0.5), name=f"_flute_{i}"
            )
            boolean_difference(result, flute)

    result.name = name
    return result


# ── Pilaster (Wall-Embedded Half-Column) ──────────────────────────────────

def create_pilaster(width, height, depth, name="Pilaster"):
    """
    Create a pilaster: a flat, wall-embedded decorative column.
    Has a subtle base, shaft, and capital.
    Typical between windows on Sector Imperialis walls.
    """
    base_h = max(height * 0.07, 2.0)
    cap_h = max(height * 0.06, 1.5)
    shaft_h = height - base_h - cap_h

    parts = []
    # Base (wider) — Z = 0 → base_h
    base = create_box_object(
        width * 1.3, base_h, depth * 1.2,
        location=(0, 0, 0), name="_pil_base"
    )
    parts.append(base)
    # Shaft — Z = base_h → base_h + shaft_h
    shaft = create_box_object(
        width, shaft_h, depth,
        location=(0, 0, base_h), name="_pil_shaft"
    )
    parts.append(shaft)
    # Capital (wider) — Z = base_h + shaft_h → height
    cap = create_box_object(
        width * 1.4, cap_h, depth * 1.3,
        location=(0, 0, base_h + shaft_h), name="_pil_cap"
    )
    parts.append(cap)

    result = parts[0]
    for part in parts[1:]:
        boolean_union(result, part, remove_other=True)
    result.name = name
    return result


# ── Buttress ───────────────────────────────────────────────────────────────

def create_buttress(width, height, depth, taper=0.65, name="Buttress"):
    """
    Create a flying buttress / Strebepfeiler.
    Tapers from full width at bottom to taper*width at top.
    Includes a stepped base for authentic gothic look.
    """
    bm = bmesh.new()
    hw = width / 2.0
    hd = depth / 2.0
    tw = width * taper / 2.0
    td = depth * taper / 2.0
    # Bottom vertices
    v0 = bm.verts.new((-hw, -hd, 0))
    v1 = bm.verts.new((hw, -hd, 0))
    v2 = bm.verts.new((hw, hd, 0))
    v3 = bm.verts.new((-hw, hd, 0))
    # Top vertices (tapered)
    v4 = bm.verts.new((-tw, -td, height))
    v5 = bm.verts.new((tw, -td, height))
    v6 = bm.verts.new((tw, td, height))
    v7 = bm.verts.new((-tw, td, height))
    # Faces
    bm.faces.new([v0, v3, v2, v1])  # bottom
    bm.faces.new([v4, v5, v6, v7])  # top
    bm.faces.new([v0, v1, v5, v4])  # front
    bm.faces.new([v2, v3, v7, v6])  # back
    bm.faces.new([v3, v0, v4, v7])  # left
    bm.faces.new([v1, v2, v6, v5])  # right
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    obj = create_object_from_bmesh(bm, name)

    # Add stepped base plinth — Z = 0 → plinth_h
    plinth_h = max(height * 0.06, 1.5)
    plinth = create_box_object(
        width * 1.3, plinth_h, depth * 1.3,
        location=(0, 0, 0), name="_butt_plinth"
    )
    boolean_union(obj, plinth)

    return obj


# ── Stone Block Pattern ────────────────────────────────────────────────────

def add_stone_block_lines(target_obj, block_height=8.0, block_width=12.0,
                          line_width=0.8, line_depth=0.5, front_face_y=None,
                          boss_depth=0.0, texture_depth=0.0):
    """
    Cut a grid of mortar lines into a wall surface to simulate stone blocks.
    Alternating horizontal courses with staggered vertical joints.

    front_face_y: world Y of the wall front face (e.g. –t/2).
        When provided the cutters are placed exactly at the wall surface
        regardless of protruding plinths/buttresses that skew the bounding box.
        When None: falls back to the bounding-box front (legacy behaviour).

    boss_depth: if > 0, each stone block gets a slight raised face (bossage).
        Disabled (0.0) by default — boolean-union of many small boxes causes
        interior voids in complex meshes.

    texture_depth: if >= 0.25, two shallow horizontal scratches are cut into
        each individual stone face.  All boolean differences — no void risk.
        Gives a rough, hand-dressed stone appearance.  Recommended: 0.3 mm.
    """
    if target_obj is None:
        return
    bb = target_obj.bound_box
    min_co = Vector(bb[0])
    max_co = Vector(bb[6])
    size = max_co - min_co

    # Y centre and total depth of each mortar-line cutter.
    # The cutter must start 0.2 mm past the wall face (to guarantee intersection)
    # and reach line_depth mm into the wall.
    if front_face_y is not None:
        cut_y     = front_face_y + line_depth / 2   # centre: half-way into groove
        cut_depth = line_depth + 0.4                # 0.2 mm margin each side
    else:
        cut_y     = min_co.y - 0.01                 # legacy: bounding-box front
        cut_depth = line_depth

    # Horizontal mortar lines — course heights vary per row (authentic ashlar)
    # Real hand-laid stone uses blocks of different heights; this cycle produces
    # a naturalistic pattern without randomness (deterministic = reproducible).
    _COURSE_CYCLE = [0.75, 1.0, 1.2, 0.88, 1.05, 0.82]
    row = 0
    z   = min_co.z + block_height * _COURSE_CYCLE[0]
    while z < max_co.z - 2.0:
        ch = block_height * _COURSE_CYCLE[row % len(_COURSE_CYCLE)]
        cutter = create_box_object(
            size.x + 2, line_width, cut_depth,
            location=(min_co.x + size.x / 2, cut_y, z),
            name=f"_mortar_h_{row}"
        )
        boolean_difference(target_obj, cutter)
        # Vertical joints sized to this course's actual block height
        offset    = (block_width / 2.0) if (row % 2 == 1) else 0.0
        x         = min_co.x + offset + block_width
        bh_vert   = ch - line_width
        if bh_vert >= 0.8:                           # FDM minimum
            while x < max_co.x - 2.0:
                vcutter = create_box_object(
                    line_width, bh_vert, cut_depth,
                    location=(x, cut_y, z - bh_vert / 2),
                    name=f"_mortar_v_{row}"
                )
                boolean_difference(target_obj, vcutter)
                x += block_width

        # Stone face texture — two shallow horizontal scratches per stone block.
        # Simulates hand-dressed / rough-cut stone: each block reads as individual
        # geometry, not a flat grid cell.  All boolean differences → no void risk.
        # Z positions of the two cuts vary by column (deterministic cycle) so no
        # two adjacent stones look identical.
        if texture_depth >= 0.25 and front_face_y is not None:
            stone_bot = z - ch
            face_z0   = stone_bot + line_width        # stone face bottom Z
            face_zh   = ch - 2 * line_width           # stone face total height
            if face_zh >= 1.5:
                # Scratch width ~10 % of stone face, min 0.5 mm
                t_w  = max(0.5, min(1.2, face_zh * 0.10))
                t_cd = texture_depth + 0.4            # cut depth with margin
                t_cy = front_face_y + texture_depth / 2  # centred in groove
                x_mg = max(line_width * 0.5, 0.5)    # inset from stone X edges
                # Fraction table — 5-entry cycle so neighbour columns differ
                _FRACS = [(0.32, 0.66), (0.28, 0.70),
                          (0.35, 0.63), (0.30, 0.68), (0.38, 0.72)]
                col = 0
                bx  = min_co.x + offset
                while bx < max_co.x - 0.5:
                    bx_right  = min(bx + block_width, max_co.x)
                    stone_cx  = (bx + bx_right) / 2
                    stone_sx  = (bx_right - bx) - 2 * x_mg
                    if stone_sx >= 0.8:
                        f1, f2 = _FRACS[col % len(_FRACS)]
                        for frac in (f1, f2):
                            t_z = face_z0 + face_zh * frac
                            # Clamp so scratch stays inside stone face
                            t_z = max(face_z0 + 0.3,
                                      min(face_z0 + face_zh - t_w - 0.3, t_z))
                            tcut = create_box_object(
                                stone_sx, t_w, t_cd,
                                location=(stone_cx, t_cy, t_z),
                                name=f"_tex_{row}_{col}",
                            )
                            boolean_difference(target_obj, tcut)
                    col += 1
                    bx  += block_width

        # Block face bossage — slight protrusion per stone face.
        # Each block gets a raised rectangle (boss) on its front surface,
        # making individual stones readable as real 3-D geometry.
        # Y-formula: boss_cy = front_face_y - boss_depth/2 + overlap/2
        #            boss is unioned, so back face is slightly inside the wall.
        if boss_depth >= 0.3 and front_face_y is not None:
            stone_bot = z - ch                       # bottom of this course
            bz_start  = stone_bot + line_width       # above bottom mortar line
            bz_h      = ch - 2 * line_width          # stone face height
            bm        = max(line_width * 0.5, 0.3)   # inset from mortar joint
            b_overlap = 0.15                         # mm inside wall surface
            boss_cy   = front_face_y - boss_depth / 2 + b_overlap / 2
            boss_yd   = boss_depth + b_overlap

            if bz_h - 2 * bm >= 0.6:
                bx = min_co.x + offset
                while bx < max_co.x - 0.5:
                    bx_right = min(bx + block_width, max_co.x)
                    boss_w   = (bx_right - bx) - 2 * bm
                    boss_h   = bz_h - 2 * bm
                    if boss_w >= 0.6:
                        boss_cx = (bx + bx_right) / 2
                        boss = create_box_object(
                            boss_w, boss_h, boss_yd,
                            location=(boss_cx, boss_cy, bz_start + bm),
                            name=f"_stone_boss_{row}"
                        )
                        boolean_union(target_obj, boss)
                    bx += block_width

        row += 1
        z += block_height * _COURSE_CYCLE[row % len(_COURSE_CYCLE)]


def add_panel_lines(target_obj, direction='HORIZONTAL', count=3,
                    line_width=0.8, line_depth=0.5):
    """
    Cut shallow panel lines into a surface using boolean difference.
    direction: 'HORIZONTAL' or 'VERTICAL'
    """
    if target_obj is None:
        return
    bb = target_obj.bound_box
    min_co = Vector(bb[0])
    max_co = Vector(bb[6])
    size = max_co - min_co
    for i in range(count):
        t = (i + 1) / (count + 1)
        if direction == 'HORIZONTAL':
            z = min_co.z + size.z * t
            cutter = create_box_object(
                size.x + 2, line_width, line_depth,
                location=(min_co.x + size.x / 2, min_co.y - 0.01, z),
                name=f"_panelline_{i}"
            )
        else:
            x = min_co.x + size.x * t
            cutter = create_box_object(
                line_width, size.z + 2, line_depth,
                location=(x, min_co.y - 0.01, min_co.z + size.z / 2),
                name=f"_panelline_{i}"
            )
        boolean_difference(target_obj, cutter)


# ── Pillar (Legacy, simple version) ───────────────────────────────────────

def create_pillar(radius, height, base_width=None, capital_width=None,
                  segments=12, name="Pillar"):
    """
    Create a gothic pillar with base and capital.
    For a more detailed version with flutes, use create_fluted_column().
    """
    if base_width is None:
        base_width = radius * 2.8
    if capital_width is None:
        capital_width = radius * 2.6
    base_h = max(height * 0.08, 2.0)
    capital_h = max(height * 0.06, 1.5)
    shaft_h = height - base_h - capital_h
    parts = []
    base = create_box_object(
        base_width, base_h, base_width,
        location=(0, 0, 0), name=name + "_Base"
    )
    parts.append(base)
    shaft = create_cylinder_object(
        radius, shaft_h, segments,
        location=(0, 0, base_h), name=name + "_Shaft"
    )
    parts.append(shaft)
    capital = create_box_object(
        capital_width, capital_h, capital_width,
        location=(0, 0, base_h + shaft_h), name=name + "_Capital"
    )
    parts.append(capital)
    result = parts[0]
    for part in parts[1:]:
        boolean_union(result, part, remove_other=True)
    result.name = name
    return result


# ── Rivets ─────────────────────────────────────────────────────────────────

def add_rivets(target_obj, positions, rivet_radius=0.8, rivet_depth=0.6):
    """
    Add rivet bumps at specified positions (list of Vector).
    Only added if rivet_radius >= 0.6mm (FDM minimum).
    """
    if rivet_radius < 0.6:
        return
    for pos in positions:
        rivet = create_cylinder_object(
            rivet_radius, rivet_depth, segments=8,
            location=(pos.x, pos.y - rivet_depth * 0.5, pos.z),
            name="_rivet"
        )
        boolean_union(target_obj, rivet, remove_other=True)
