"""
Corner Ruin generator for Warhammer 40K imperial terrain.
Two wall segments meeting at 90 degrees, forming an L-shaped ruin.
"""

import bpy
import math
import random
from mathutils import Vector
from ..utils.mesh import (
    create_box_object,
    boolean_union,
    boolean_difference,
    cleanup_mesh,
    join_objects,
)
from .gothic_details import (
    create_gothic_arch_cutter,
    create_buttress,
)
from .connectors import add_connectors
from .damage import apply_damage
from .splitter import should_split, split_for_print


def generate_corner_ruin(params):
    """
    Generate an L-shaped corner ruin piece.

    params dict keys: same as wall_segment plus:
        depth (float): depth of each wing (default = width)

    Returns: list of objects
    """
    w = params.get('width', 80.0)
    h = params.get('height', 70.0)
    d = params.get('depth', None) or w  # each wing length
    t = params.get('wall_thickness', 3.0)
    win_count = params.get('window_density', 1)
    detail = params.get('detail_level', 1)
    gothic = params.get('gothic_style', 1)
    damage_val = params.get('damage_intensity', 0.4)
    seed = params.get('seed', 42)
    connector = params.get('connector_type', 'NONE')
    split_mode = params.get('split_mode', 'AUTO')

    rng = random.Random(seed)

    # --- Wing A: along +X axis ---
    wing_a = create_box_object(
        d, h, t,
        location=(d / 2, 0, h / 2),
        name="Corner_WingA"
    )

    # --- Wing B: along +Y axis ---
    wing_b = create_box_object(
        t, h, d,
        location=(0, d / 2, h / 2),
        name="Corner_WingB"
    )

    # --- Corner fill block (overlap area) ---
    corner_block = create_box_object(
        t, h, t,
        location=(t / 2, t / 2, h / 2),
        name="_corner_fill"
    )

    # Union all parts
    boolean_union(wing_a, corner_block)
    boolean_union(wing_a, wing_b)
    corner = wing_a
    corner.name = "Corner_Ruin"

    # --- Windows in Wing A ---
    if win_count > 0 and d > 30:
        _add_corner_windows(corner, d, h, t, win_count, gothic, 'X', rng)

    # --- Windows in Wing B ---
    if win_count > 0 and d > 30:
        _add_corner_windows(corner, d, h, t, win_count, gothic, 'Y', rng)

    # --- Buttress at outer corner ---
    if gothic >= 1:
        butt = create_buttress(
            max(t * 1.5, 5.0), h * 0.75, max(t * 2, 8.0),
            taper=0.55, name="_corner_buttress"
        )
        # Place at outer corner
        butt.location = Vector((d + 2, 0, 0))
        bpy.context.view_layer.objects.active = butt
        butt.select_set(True)
        bpy.ops.object.transform_apply(location=True)
        boolean_union(corner, butt)

    # --- Damage ---
    apply_damage(corner, damage_val, seed)

    # --- Connectors ---
    add_connectors(
        corner, connector,
        pin_tolerance=params.get('pin_tolerance', 0.25),
        magnet_diameter=params.get('magnet_diameter', 5.0),
        magnet_height=params.get('magnet_height', 2.0),
    )

    # --- Cleanup ---
    cleanup_mesh(corner)

    # --- Split ---
    if split_mode == 'AUTO' and should_split(corner):
        parts = split_for_print(corner)
        for i, p in enumerate(parts):
            p.name = f"Corner_Ruin_{i:02d}"
            cleanup_mesh(p)
        return parts

    return [corner]


def _add_corner_windows(corner, wing_len, h, t, count, gothic, axis, rng):
    """Add windows to a wing of the corner piece."""
    win_w = min(wing_len / (count + 1) * 0.5, 22.0)
    win_h = min(h * 0.5, 40.0)
    spacing = wing_len / (count + 1)

    for i in range(count):
        pos_along = spacing * (i + 1)

        if gothic > 0:
            cutter = create_gothic_arch_cutter(
                win_w, win_h, t + 2.0,
                segments=max(8, gothic * 4),
                name=f"_cwin_{axis}_{i}"
            )
        else:
            cutter = create_box_object(
                win_w, win_h, t + 2.0,
                location=(0, 0, win_h / 2),
                name=f"_cwin_{axis}_{i}"
            )

        if axis == 'X':
            cutter.location = Vector((pos_along, 0, h * 0.42))
        else:
            cutter.location = Vector((0, pos_along, h * 0.42))

        bpy.context.view_layer.objects.active = cutter
        cutter.select_set(True)
        bpy.ops.object.transform_apply(location=True)

        if axis == 'Y':
            # Rotate cutter 90 degrees to cut along Y-axis wall
            cutter.rotation_euler.z = math.radians(90)
            bpy.ops.object.transform_apply(rotation=True)

        boolean_difference(corner, cutter)
