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

def create_skull_relief(width=6.0, height=7.0, depth=1.2, name="Skull"):
    """
    Create a simplified Imperial skull motif for wall decoration.
    FDM-optimized: min ~6mm wide for recognizable detail.
    Shape: rounded cranium top, angular jaw, hollow eye sockets.
    """
    if width < 4.0:
        # Too small for FDM detail, return simple bump
        return create_box_object(width, height * 0.8, depth,
                                 location=(0, 0, 0), name=name)

    skull_w = width
    skull_h = height
    # Cranium (upper 60%): use a half-cylinder approximation
    cranium_r = skull_w / 2.0
    cranium_h = skull_h * 0.6
    cranium = create_cylinder_object(
        cranium_r, depth, segments=12,
        location=(0, 0, skull_h * 0.35), name="_cranium"
    )
    # Rotate to face outward (cylinder along Y becomes relief on wall)
    cranium.rotation_euler.x = math.radians(90)
    bpy.context.view_layer.objects.active = cranium
    cranium.select_set(True)
    bpy.ops.object.transform_apply(rotation=True)

    # Jaw (lower 40%): tapered box
    jaw_w = skull_w * 0.7
    jaw_h = skull_h * 0.4
    jaw = create_box_object(
        jaw_w, jaw_h, depth * 0.8,
        location=(0, 0, -skull_h * 0.05), name="_jaw"
    )
    boolean_union(cranium, jaw)

    # Eye sockets: two small cylinder cuts
    eye_spacing = skull_w * 0.28
    eye_r = skull_w * 0.12
    eye_depth_val = depth + 1.0
    for side in [-1, 1]:
        eye = create_cylinder_object(
            eye_r, eye_depth_val, segments=8,
            location=(side * eye_spacing, 0, skull_h * 0.35), name="_eye"
        )
        eye.rotation_euler.x = math.radians(90)
        bpy.context.view_layer.objects.active = eye
        eye.select_set(True)
        bpy.ops.object.transform_apply(rotation=True)
        boolean_difference(cranium, eye)

    # Nose cavity: small triangle-ish cut
    nose = create_box_object(
        skull_w * 0.15, skull_w * 0.18, eye_depth_val,
        location=(0, 0, skull_h * 0.2), name="_nose"
    )
    nose.rotation_euler.z = math.radians(45)
    bpy.context.view_layer.objects.active = nose
    nose.select_set(True)
    bpy.ops.object.transform_apply(rotation=True)
    boolean_difference(cranium, nose)

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
    # Base (wider)
    base = create_box_object(
        width * 1.3, base_h, depth * 1.2,
        location=(0, 0, base_h / 2), name="_pil_base"
    )
    parts.append(base)
    # Shaft
    shaft = create_box_object(
        width, shaft_h, depth,
        location=(0, 0, base_h + shaft_h / 2), name="_pil_shaft"
    )
    parts.append(shaft)
    # Capital (wider, with slight overhang)
    cap = create_box_object(
        width * 1.4, cap_h, depth * 1.3,
        location=(0, 0, base_h + shaft_h + cap_h / 2), name="_pil_cap"
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

    # Add stepped base plinth
    plinth_h = max(height * 0.06, 1.5)
    plinth = create_box_object(
        width * 1.3, plinth_h, depth * 1.3,
        location=(0, 0, plinth_h / 2), name="_butt_plinth"
    )
    boolean_union(obj, plinth)

    return obj


# ── Stone Block Pattern ────────────────────────────────────────────────────

def add_stone_block_lines(target_obj, block_height=8.0, block_width=12.0,
                          line_width=0.6, line_depth=0.4):
    """
    Cut a grid of mortar lines into a wall surface to simulate stone blocks.
    Alternating horizontal courses with staggered vertical joints.
    Typical of Sector Imperialis wall surfaces.
    """
    if target_obj is None:
        return
    bb = target_obj.bound_box
    min_co = Vector(bb[0])
    max_co = Vector(bb[6])
    size = max_co - min_co

    # Horizontal mortar lines
    z = min_co.z + block_height
    row = 0
    while z < max_co.z - 2.0:
        cutter = create_box_object(
            size.x + 2, line_width, line_depth,
            location=(min_co.x + size.x / 2, min_co.y - 0.01, z),
            name=f"_mortar_h_{row}"
        )
        boolean_difference(target_obj, cutter)
        # Vertical joints (staggered every other row)
        offset = (block_width / 2.0) if (row % 2 == 1) else 0.0
        x = min_co.x + offset + block_width
        while x < max_co.x - 2.0:
            vcutter = create_box_object(
                line_width, block_height - line_width, line_depth,
                location=(x, min_co.y - 0.01, z - (block_height - line_width) / 2),
                name=f"_mortar_v_{row}"
            )
            boolean_difference(target_obj, vcutter)
            x += block_width
        z += block_height
        row += 1


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
