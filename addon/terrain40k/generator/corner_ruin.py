"""
Corner Ruin generator for Warhammer 40K imperial terrain.
Two wall segments meeting at 90 degrees, forming an L-shaped ruin.
Full Sector Imperialis details: stone blocks, pilasters, skulls, arch frames.
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
)
from .gothic_details import (
    create_gothic_arch_cutter,
    create_arch_frame,
    create_buttress,
    create_pilaster,
    create_skull_relief,
    add_stone_block_lines,
    add_panel_lines,
)
from .connectors import add_connectors
from .damage import apply_damage
from .splitter import should_split, split_for_print


def generate_corner_ruin(params):
    """
    Generate an L-shaped corner ruin with full Imperial Gothic details.
    Details visible from gothic_style/detail_level 1 upward.
    """
    w = params.get('width', 80.0)
    h = params.get('height', 70.0)
    d = params.get('depth', None) or w
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

    # --- Corner fill block ---
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

    # --- Base plinth (foundation strip) ---
    plinth_h = max(h * 0.05, 2.5)
    # Plinth along wing A
    plinth_a = create_box_object(
        d + 3.0, plinth_h, t + 3.0,
        location=(d / 2, 0, plinth_h / 2),
        name="_plinth_a"
    )
    boolean_union(corner, plinth_a)
    # Plinth along wing B
    plinth_b = create_box_object(
        t + 3.0, plinth_h, d + 3.0,
        location=(0, d / 2, plinth_h / 2),
        name="_plinth_b"
    )
    boolean_union(corner, plinth_b)

    # --- Windows in both wings ---
    win_positions_a = []
    win_positions_b = []
    if win_count > 0 and d > 30:
        win_positions_a = _add_wing_windows(
            corner, d, h, t, win_count, gothic, detail, 'X', rng
        )
        win_positions_b = _add_wing_windows(
            corner, d, h, t, win_count, gothic, detail, 'Y', rng
        )

    # --- Pilasters between windows on wing A ---
    if gothic >= 1 and len(win_positions_a) >= 2:
        _add_wing_pilasters(corner, win_positions_a, h, t, 'X')
    # --- Pilasters between windows on wing B ---
    if gothic >= 1 and len(win_positions_b) >= 2:
        _add_wing_pilasters(corner, win_positions_b, h, t, 'Y')

    # --- Buttresses at wing ends and corner ---
    _add_corner_buttresses(corner, d, h, t, gothic, rng)

    # --- Skulls above windows ---
    if gothic >= 2:
        _add_wing_skulls(corner, win_positions_a, h, t, 'X')
        _add_wing_skulls(corner, win_positions_b, h, t, 'Y')

    # --- Stone block / panel lines ---
    if detail >= 2:
        # Stone blocks are hard on L-shape, use panel lines instead
        _add_wall_panel_lines(corner, d, h, t, detail)
    elif detail >= 1:
        add_panel_lines(corner, direction='HORIZONTAL',
                        count=max(2, int(h / 20)),
                        line_width=0.7, line_depth=0.4)

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


def _add_wing_windows(corner, wing_len, h, t, count, gothic, detail, axis, rng):
    """Cut gothic windows into a wing, with frames and sills. Returns positions."""
    # Tall narrow lancet proportions
    win_w = min(wing_len / (count + 1) * 0.4, 18.0)
    win_h = min(h * 0.6, 48.0)
    if gothic > 0:
        win_w = min(win_w, win_h * 0.38)  # narrow lancet ratio

    spacing = wing_len / (count + 1)
    positions = []

    for i in range(count):
        pos_along = spacing * (i + 1)
        cz = h * 0.46

        # Create cutter
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
            cutter.location = Vector((pos_along, 0, cz))
            positions.append((pos_along, cz))
        else:
            cutter.location = Vector((0, pos_along, cz))
            positions.append((pos_along, cz))

        bpy.context.view_layer.objects.active = cutter
        cutter.select_set(True)
        bpy.ops.object.transform_apply(location=True)

        if axis == 'Y':
            cutter.rotation_euler.z = math.radians(90)
            bpy.ops.object.transform_apply(rotation=True)

        boolean_difference(corner, cutter)

        # Raised arch frame around window
        if gothic >= 1 and detail >= 1:
            frame = create_arch_frame(
                win_w, win_h, depth=1.5, frame_thickness=1.5,
                segments=max(8, gothic * 4),
                name=f"_cframe_{axis}_{i}"
            )
            if axis == 'X':
                frame.location = Vector((pos_along, -(t / 2 + 0.3), cz))
            else:
                frame.location = Vector((-(t / 2 + 0.3), pos_along, cz))
                frame.rotation_euler.z = math.radians(90)
            bpy.context.view_layer.objects.active = frame
            frame.select_set(True)
            bpy.ops.object.transform_apply(location=True, rotation=True)
            boolean_union(corner, frame)

        # Window sill
        sill_w = win_w + 4.0
        sill_h = 2.0
        sill_d = t + 2.0
        if axis == 'X':
            sill = create_box_object(
                sill_w, sill_h, sill_d,
                location=(pos_along, 0, cz - win_h / 2 - sill_h / 2 + 0.5),
                name=f"_csill_{axis}_{i}"
            )
        else:
            sill = create_box_object(
                sill_d, sill_h, sill_w,
                location=(0, pos_along, cz - win_h / 2 - sill_h / 2 + 0.5),
                name=f"_csill_{axis}_{i}"
            )
        boolean_union(corner, sill)

    return positions


def _add_wing_pilasters(corner, positions, h, t, axis):
    """Add pilasters between window positions on a wing."""
    pil_w = max(2.5, t * 0.7)
    pil_h = h * 0.82
    pil_d = max(1.5, t * 0.5)
    for i in range(len(positions) - 1):
        p1 = positions[i][0]
        p2 = positions[i + 1][0]
        mid = (p1 + p2) / 2.0
        pilaster = create_pilaster(pil_w, pil_h, pil_d, name=f"_cpil_{axis}_{i}")
        if axis == 'X':
            pilaster.location = Vector((mid, -(t / 2 + pil_d / 2 - 0.5), 0))
        else:
            pilaster.location = Vector((-(t / 2 + pil_d / 2 - 0.5), mid, 0))
            pilaster.rotation_euler.z = math.radians(90)
        bpy.context.view_layer.objects.active = pilaster
        pilaster.select_set(True)
        bpy.ops.object.transform_apply(location=True, rotation=True)
        boolean_union(corner, pilaster)


def _add_corner_buttresses(corner, d, h, t, gothic, rng):
    """Add buttresses at wing ends and inner/outer corner."""
    butt_w = max(t * 1.8, 6.0)
    butt_h = h * 0.85
    butt_d = max(t * 2.5, 10.0)

    buttress_positions = []
    # Wing A end (far X)
    buttress_positions.append((d - butt_w / 2, 0, 0, 'X'))
    # Wing B end (far Y)
    buttress_positions.append((0, d - butt_w / 2, math.radians(90), 'Y'))

    if gothic >= 2:
        # Outer corner buttress (diagonal)
        buttress_positions.append((t + butt_w, -(butt_d / 2 - 1), 0, 'X'))

    for px, py, rot, axis in buttress_positions:
        butt = create_buttress(
            butt_w, butt_h, butt_d,
            taper=0.5, name="_cbutt"
        )
        if axis == 'X':
            butt.location = Vector((px, -(t / 2 + butt_d / 2 - 1.0), 0))
        else:
            butt.location = Vector((-(t / 2 + butt_d / 2 - 1.0), px, 0))
            butt.rotation_euler.z = math.radians(90)
        bpy.context.view_layer.objects.active = butt
        butt.select_set(True)
        bpy.ops.object.transform_apply(location=True, rotation=True)
        boolean_union(corner, butt)


def _add_wing_skulls(corner, positions, h, t, axis):
    """Place skulls above windows on a wing."""
    skull_w = 6.0
    skull_h = 7.0
    for i, (pos, wz) in enumerate(positions):
        skull = create_skull_relief(skull_w, skull_h, depth=1.2,
                                    name=f"_cskull_{axis}_{i}")
        skull_z = min(wz + 28.0, h - 5.0)
        if axis == 'X':
            skull.location = Vector((pos, -(t / 2 + 0.3), skull_z))
        else:
            skull.location = Vector((-(t / 2 + 0.3), pos, skull_z))
            skull.rotation_euler.z = math.radians(90)
        bpy.context.view_layer.objects.active = skull
        skull.select_set(True)
        bpy.ops.object.transform_apply(location=True, rotation=True)
        boolean_union(corner, skull)


def _add_wall_panel_lines(corner, d, h, t, detail):
    """Add horizontal panel lines to simulate stone courses."""
    count = max(3, int(h / 12))
    add_panel_lines(corner, direction='HORIZONTAL', count=count,
                    line_width=0.7, line_depth=0.4)
