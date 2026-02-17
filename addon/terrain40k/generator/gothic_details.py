"""
Gothic architectural detail primitives for Warhammer 40K terrain.
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
)


def gothic_arch_profile(width, height, segments=12):
    """
    Generate 2D profile points (x, z) for a gothic pointed arch.
    Bottom is at z=0, peak at z=height.
    The profile is a closed shape suitable for extrusion.
    """
    hw = width / 2.0
    # Rectangular portion (lower ~55%)
    rect_h = height * 0.55
    points = []
    # Start bottom-left, go clockwise
    points.append((-hw, 0))
    points.append((-hw, rect_h))
    # Arch: two quadratic curves meeting at center peak
    n = max(segments // 2, 3)
    for i in range(1, n + 1):
        t = i / n
        # Left side: from (-hw, rect_h) to (0, height)
        x = -hw * (1.0 - t)
        z = rect_h + (height - rect_h) * math.sin(t * math.pi / 2.0)
        points.append((x, z))
    for i in range(1, n):
        t = i / n
        # Right side: from (0, height) to (hw, rect_h)
        x = hw * t
        z = rect_h + (height - rect_h) * math.cos(t * math.pi / 2.0)
        points.append((x, z))
    points.append((hw, rect_h))
    points.append((hw, 0))
    return points


def create_gothic_arch_cutter(width, height, depth, segments=12, name="ArchCutter"):
    """Create a solid gothic arch shape for boolean cutting (windows/doors)."""
    profile = gothic_arch_profile(width, height, segments)
    obj = extrude_profile_to_solid(profile, depth, offset_y=0.0, name=name)
    return obj


def create_pillar(radius, height, base_width=None, capital_width=None,
                  segments=12, name="Pillar"):
    """
    Create a gothic pillar with base and capital.
    base_width/capital_width default to radius * 2.8 if not set.
    """
    if base_width is None:
        base_width = radius * 2.8
    if capital_width is None:
        capital_width = radius * 2.6
    base_h = max(height * 0.08, 2.0)
    capital_h = max(height * 0.06, 1.5)
    shaft_h = height - base_h - capital_h
    parts = []
    # Base
    base = create_box_object(
        base_width, base_h, base_width,
        location=(0, 0, 0), name=name + "_Base"
    )
    parts.append(base)
    # Shaft (cylinder)
    shaft = create_cylinder_object(
        radius, shaft_h, segments,
        location=(0, 0, base_h), name=name + "_Shaft"
    )
    parts.append(shaft)
    # Capital
    capital = create_box_object(
        capital_width, capital_h, capital_width,
        location=(0, 0, base_h + shaft_h), name=name + "_Capital"
    )
    parts.append(capital)
    # Join all parts via boolean union for watertight result
    result = parts[0]
    for part in parts[1:]:
        boolean_union(result, part, remove_other=True)
    result.name = name
    return result


def create_buttress(width, height, depth, taper=0.65, name="Buttress"):
    """
    Create a flying buttress / strebepfeiler.
    Tapers from full width at bottom to taper*width at top.
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
    return obj


def create_aquila_relief(width, height, depth=1.0, name="Aquila"):
    """
    Create a simplified Imperial Aquila (double-headed eagle) relief.
    This is a raised panel - union it onto a wall surface.
    Simplified geometric version that prints well on FDM.
    """
    bm = bmesh.new()
    hw = width / 2.0
    hh = height / 2.0
    # Simplified eagle: diamond/chevron shape with wing extensions
    # Center body (diamond)
    body_w = width * 0.15
    body_h = height * 0.4
    # Left wing
    points_front = [
        # Body center diamond
        (0, hh * 0.8),
        (-body_w, 0),
        (0, -hh * 0.5),
        (body_w, 0),
        # We'll build this as a simple raised box for printability
    ]
    # For FDM printability, use a simple raised panel with chevron cutout
    # Main panel
    create_box_bmesh(bm, width * 0.8, height * 0.6, depth, location=(0, 0, 0))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    obj = create_object_from_bmesh(bm, name)
    # Cut a V-shape for the aquila wings using two angled box cutters
    cutter1 = create_box_object(width * 0.5, height * 0.3, depth * 3,
                                location=(-width * 0.25, 0, -height * 0.2),
                                name="_aquila_cut1")
    # Rotate cutter
    cutter1.rotation_euler.y = math.radians(25)
    bpy.context.view_layer.objects.active = cutter1
    cutter1.select_set(True)
    bpy.ops.object.transform_apply(rotation=True)
    from ..utils.mesh import boolean_difference
    boolean_difference(obj, cutter1)

    cutter2 = create_box_object(width * 0.5, height * 0.3, depth * 3,
                                location=(width * 0.25, 0, -height * 0.2),
                                name="_aquila_cut2")
    cutter2.rotation_euler.y = math.radians(-25)
    bpy.context.view_layer.objects.active = cutter2
    cutter2.select_set(True)
    bpy.ops.object.transform_apply(rotation=True)
    boolean_difference(obj, cutter2)
    return obj


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
    from ..utils.mesh import boolean_difference
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


def add_rivets(target_obj, positions, rivet_radius=0.8, rivet_depth=0.6):
    """
    Add rivet bumps at specified positions (list of Vector).
    Rivets are small cylinders boolean-unioned onto the surface.
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
