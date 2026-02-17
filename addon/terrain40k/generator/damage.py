"""
Destruction / damage effects for terrain pieces.
Generates printable damage: wall breaks, chipped edges, bullet holes.
All damage is achieved via boolean operations for watertight results.
"""

import bpy
import bmesh
import math
import random
from mathutils import Vector
from ..utils.mesh import (
    create_box_object,
    create_cylinder_object,
    boolean_difference,
)


def apply_damage(obj, intensity=0.5, seed=42):
    """
    Master damage function. Intensity 0.0-1.0.
    Combines edge damage, bullet holes, and chunk removal.
    """
    if intensity <= 0.0:
        return
    rng = random.Random(seed)
    if intensity > 0.15:
        damage_top_edge(obj, intensity, rng)
    if intensity > 0.3:
        count = max(1, int(intensity * 6))
        add_bullet_holes(obj, count, rng)
    if intensity > 0.6:
        remove_chunks(obj, int(intensity * 3), rng)


def damage_top_edge(obj, intensity=0.5, rng=None):
    """
    Create irregular top edge by cutting random boxes from the top.
    Simulates crumbling / battle damage on walls.
    """
    if rng is None:
        rng = random.Random(42)
    bb = obj.bound_box
    min_co = Vector(bb[0])
    max_co = Vector(bb[6])
    size = max_co - min_co
    # Number of cuts based on width and intensity
    num_cuts = max(2, int(size.x / 15.0 * intensity * 3))
    for i in range(num_cuts):
        cut_w = rng.uniform(3.0, size.x * 0.2 * intensity)
        cut_h = rng.uniform(size.z * 0.05, size.z * 0.35 * intensity)
        cut_d = size.y + 2.0  # cut through full depth
        cut_x = rng.uniform(min_co.x + cut_w / 2, max_co.x - cut_w / 2)
        cut_z = max_co.z - cut_h / 2 + 0.5
        cutter = create_box_object(
            cut_w, cut_h, cut_d,
            location=(cut_x, (min_co.y + max_co.y) / 2, cut_z),
            name=f"_dmg_top_{i}"
        )
        # Slight random rotation for more organic look
        angle = rng.uniform(-0.15, 0.15)
        cutter.rotation_euler.y = angle
        bpy.context.view_layer.objects.active = cutter
        cutter.select_set(True)
        bpy.ops.object.transform_apply(rotation=True)
        boolean_difference(obj, cutter)


def add_bullet_holes(obj, count=3, rng=None):
    """
    Add small impact craters / bullet holes using cylinder boolean cuts.
    Min diameter >= 1.5mm for FDM visibility.
    """
    if rng is None:
        rng = random.Random(42)
    bb = obj.bound_box
    min_co = Vector(bb[0])
    max_co = Vector(bb[6])
    size = max_co - min_co
    for i in range(count):
        radius = rng.uniform(1.0, 2.5)
        depth = rng.uniform(size.y * 0.3, size.y + 1.0)
        x = rng.uniform(min_co.x + 5, max_co.x - 5)
        z = rng.uniform(min_co.z + 5, max_co.z - 8)
        y = min_co.y - 0.5
        hole = create_cylinder_object(
            radius, depth, segments=8,
            location=(x, y, z),
            name=f"_bullet_{i}"
        )
        # Rotate to point into the wall (along Y axis)
        hole.rotation_euler.x = math.radians(90)
        # Small random angle for variety
        hole.rotation_euler.y = rng.uniform(-0.3, 0.3)
        hole.rotation_euler.z = rng.uniform(-0.3, 0.3)
        bpy.context.view_layer.objects.active = hole
        hole.select_set(True)
        bpy.ops.object.transform_apply(rotation=True)
        boolean_difference(obj, hole)


def remove_chunks(obj, count=1, rng=None):
    """
    Remove larger chunks from corners/edges for heavy destruction.
    Uses angled box cutters.
    """
    if rng is None:
        rng = random.Random(42)
    bb = obj.bound_box
    min_co = Vector(bb[0])
    max_co = Vector(bb[6])
    size = max_co - min_co
    for i in range(count):
        chunk_w = rng.uniform(size.x * 0.1, size.x * 0.3)
        chunk_h = rng.uniform(size.z * 0.1, size.z * 0.4)
        chunk_d = size.y + 4.0
        # Place at a corner/edge
        side = rng.choice(['left', 'right'])
        if side == 'left':
            cx = min_co.x + chunk_w * 0.3
        else:
            cx = max_co.x - chunk_w * 0.3
        cz = rng.uniform(min_co.z, max_co.z - chunk_h)
        cutter = create_box_object(
            chunk_w, chunk_h, chunk_d,
            location=(cx, (min_co.y + max_co.y) / 2, cz + chunk_h / 2),
            name=f"_chunk_{i}"
        )
        # Rotate for irregular shape
        cutter.rotation_euler.x = rng.uniform(-0.2, 0.2)
        cutter.rotation_euler.y = rng.uniform(-0.4, 0.4)
        cutter.rotation_euler.z = rng.uniform(-0.3, 0.3)
        bpy.context.view_layer.objects.active = cutter
        cutter.select_set(True)
        bpy.ops.object.transform_apply(rotation=True)
        boolean_difference(obj, cutter)
