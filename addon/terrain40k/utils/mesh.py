"""
Mesh utility functions for terrain40k addon.
Boolean-safe operations, cleanup, manifold checks.
All geometry helpers assume 1 Blender Unit = 1 mm.
"""

import bpy
import bmesh
import math
from mathutils import Vector


def create_object_from_bmesh(bm, name="TerrainPart"):
    """Convert a bmesh to a new Blender object, link to active collection."""
    mesh = bpy.data.meshes.new(name)
    bm.to_mesh(mesh)
    bm.free()
    obj = bpy.data.objects.new(name, mesh)
    bpy.context.collection.objects.link(obj)
    return obj


def create_box_bmesh(bm, width, height, depth, location=(0, 0, 0)):
    """Create a solid box in an existing bmesh. Returns list of created verts."""
    ox, oy, oz = location
    hw, hd = width / 2, depth / 2
    coords = [
        (ox - hw, oy - hd, oz),
        (ox + hw, oy - hd, oz),
        (ox + hw, oy + hd, oz),
        (ox - hw, oy + hd, oz),
        (ox - hw, oy - hd, oz + height),
        (ox + hw, oy - hd, oz + height),
        (ox + hw, oy + hd, oz + height),
        (ox - hw, oy + hd, oz + height),
    ]
    verts = [bm.verts.new(co) for co in coords]
    # 6 faces with consistent winding (outward normals)
    bm.faces.new([verts[0], verts[3], verts[2], verts[1]])  # bottom
    bm.faces.new([verts[4], verts[5], verts[6], verts[7]])  # top
    bm.faces.new([verts[0], verts[1], verts[5], verts[4]])  # front
    bm.faces.new([verts[2], verts[3], verts[7], verts[6]])  # back
    bm.faces.new([verts[3], verts[0], verts[4], verts[7]])  # left
    bm.faces.new([verts[1], verts[2], verts[6], verts[5]])  # right
    return verts


def create_box_object(width, height, depth, location=(0, 0, 0), name="Box"):
    """Create a standalone box object."""
    bm = bmesh.new()
    create_box_bmesh(bm, width, height, depth, location)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    obj = create_object_from_bmesh(bm, name)
    return obj


def create_cylinder_object(radius, height, segments=16, location=(0, 0, 0), name="Cylinder"):
    """Create a solid cylinder (capped top and bottom)."""
    bm = bmesh.new()
    ox, oy, oz = location
    # Bottom ring
    bottom_verts = []
    for i in range(segments):
        angle = 2 * math.pi * i / segments
        x = ox + radius * math.cos(angle)
        y = oy + radius * math.sin(angle)
        bottom_verts.append(bm.verts.new((x, y, oz)))
    # Top ring
    top_verts = []
    for i in range(segments):
        angle = 2 * math.pi * i / segments
        x = ox + radius * math.cos(angle)
        y = oy + radius * math.sin(angle)
        top_verts.append(bm.verts.new((x, y, oz + height)))
    # Bottom cap
    bm.faces.new(list(reversed(bottom_verts)))
    # Top cap
    bm.faces.new(top_verts)
    # Side faces
    for i in range(segments):
        j = (i + 1) % segments
        bm.faces.new([bottom_verts[i], bottom_verts[j], top_verts[j], top_verts[i]])
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    obj = create_object_from_bmesh(bm, name)
    return obj


def extrude_profile_to_solid(profile_points_xz, depth, offset_y=0.0, name="Profile"):
    """
    Take a list of (x, z) 2D points forming a closed profile,
    extrude along Y axis to create a watertight solid.
    Points must be in order (CW or CCW, normals will be recalculated).
    """
    bm = bmesh.new()
    n = len(profile_points_xz)
    half_d = depth / 2.0
    front_verts = []
    back_verts = []
    for x, z in profile_points_xz:
        front_verts.append(bm.verts.new((x, offset_y - half_d, z)))
        back_verts.append(bm.verts.new((x, offset_y + half_d, z)))
    # Front face
    try:
        bm.faces.new(front_verts)
    except ValueError:
        pass
    # Back face (reversed)
    try:
        bm.faces.new(list(reversed(back_verts)))
    except ValueError:
        pass
    # Side quads
    for i in range(n):
        j = (i + 1) % n
        try:
            bm.faces.new([front_verts[i], front_verts[j], back_verts[j], back_verts[i]])
        except ValueError:
            pass
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    obj = create_object_from_bmesh(bm, name)
    return obj


def boolean_operation(target, cutter, operation='DIFFERENCE', remove_cutter=True):
    """
    Apply a boolean modifier (EXACT solver) and clean up.
    operation: 'DIFFERENCE', 'UNION', 'INTERSECT'
    """
    if bpy.context.mode != 'OBJECT':
        bpy.ops.object.mode_set(mode='OBJECT')
    bpy.ops.object.select_all(action='DESELECT')
    bpy.context.view_layer.objects.active = target
    target.select_set(True)

    mod = target.modifiers.new(name="Bool_" + operation[:4], type='BOOLEAN')
    mod.operation = operation
    mod.solver = 'EXACT'
    mod.object = cutter
    # Hide cutter from viewport to avoid visual clutter
    cutter.hide_set(True)

    try:
        try:
            bpy.ops.object.modifier_apply(modifier=mod.name)
        except RuntimeError:
            # Fallback: try FAST solver if EXACT fails
            if mod.name in [m.name for m in target.modifiers]:
                target.modifiers.remove(mod)
            mod2 = target.modifiers.new(name="Bool_FAST", type='BOOLEAN')
            mod2.operation = operation
            mod2.solver = 'FAST'
            mod2.object = cutter
            try:
                bpy.ops.object.modifier_apply(modifier=mod2.name)
            except RuntimeError:
                if mod2.name in [m.name for m in target.modifiers]:
                    target.modifiers.remove(mod2)
    finally:
        # Always remove cutter — even if a non-RuntimeError exception occurs
        if remove_cutter:
            try:
                bpy.data.objects.remove(cutter, do_unlink=True)
            except Exception:
                pass


def boolean_difference(target, cutter, remove_cutter=True):
    boolean_operation(target, cutter, 'DIFFERENCE', remove_cutter)


def boolean_union(target, other, remove_other=True):
    boolean_operation(target, other, 'UNION', remove_other)


def cleanup_mesh(obj):
    """
    Full mesh cleanup: remove doubles, recalc normals, apply transforms.
    Call this on every final output mesh.
    """
    if obj is None or obj.type != 'MESH':
        return
    # Apply transforms
    bpy.ops.object.select_all(action='DESELECT')
    bpy.context.view_layer.objects.active = obj
    obj.select_set(True)
    bpy.ops.object.transform_apply(location=False, rotation=True, scale=True)
    # BMesh cleanup
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    # Merge by distance (remove doubles) - 0.01mm tolerance
    bmesh.ops.remove_doubles(bm, verts=bm.verts[:], dist=0.01)
    # Recalculate normals
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    # Dissolve degenerate geometry
    bmesh.ops.dissolve_degenerate(bm, edges=bm.edges[:], dist=0.001)
    bm.to_mesh(obj.data)
    bm.free()
    obj.data.update()


def join_objects(objects, name="Joined"):
    """Join multiple objects into one. Returns the joined object."""
    if not objects:
        return None
    if len(objects) == 1:
        objects[0].name = name
        return objects[0]
    bpy.ops.object.select_all(action='DESELECT')
    for o in objects:
        o.select_set(True)
    bpy.context.view_layer.objects.active = objects[0]
    bpy.ops.object.join()
    result = bpy.context.active_object
    result.name = name
    return result
