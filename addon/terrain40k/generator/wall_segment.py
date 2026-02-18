"""
Wall Segment generator for Warhammer 40K imperial ruins.
Based on Sector Imperialis architecture:
- Gothic pointed arch windows with raised frames
- Pilaster strips between windows
- Skull motifs above windows / on wall face
- Stone block mortar pattern
- Flying buttresses with stepped bases
- Battle damage (crumbling, bullet holes, chunks)
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
    create_aquila_relief,
    add_panel_lines,
    add_stone_block_lines,
    add_rivets,
)
from .connectors import add_connectors
from .damage import apply_damage
from .splitter import should_split, split_for_print


def generate_wall_segment(params):
    """
    Generate an Imperial Gothic wall segment with authentic details.

    Detail level controls:
        0: Plain wall + windows only
        1: + buttresses + pilasters
        2: + stone block lines + window frames + skulls
        3: + aquila relief + rivets + full decoration

    Gothic style controls:
        0: Rectangular windows, no gothic elements
        1: Pointed arch windows + simple buttresses
        2: + window sills/frames + pilasters between windows
        3: + skulls above windows + aquila + full gothic

    Returns: list of objects (may be multiple if split)
    """
    w = params.get('width', 100.0)
    h = params.get('height', 80.0)
    t = params.get('wall_thickness', 3.0)
    win_count = params.get('window_density', 2)
    detail = params.get('detail_level', 1)
    gothic = params.get('gothic_style', 1)
    damage = params.get('damage_intensity', 0.3)
    seed = params.get('seed', 42)
    connector = params.get('connector_type', 'NONE')
    split_mode = params.get('split_mode', 'AUTO')
    bevel_w = params.get('bevel_width', 0.0)

    rng = random.Random(seed)

    # --- Main wall slab ---
    wall = create_box_object(w, h, t, location=(0, 0, h / 2), name="Wall_Segment")

    # --- Base plinth (foundation strip at bottom) ---
    if detail >= 1:
        plinth_h = max(h * 0.05, 3.0)
        plinth = create_box_object(
            w + 2.0, plinth_h, t + 2.0,
            location=(0, 0, plinth_h / 2), name="_wall_plinth"
        )
        boolean_union(wall, plinth)

    # --- Windows ---
    window_positions = []
    if win_count > 0:
        window_positions = _add_windows(wall, w, h, t, win_count, gothic, detail, rng)

    # --- Pilasters between windows (now from gothic 1+) ---
    if gothic >= 1 and len(window_positions) >= 2:
        _add_pilasters(wall, w, h, t, window_positions, rng)

    # --- Buttresses ---
    if gothic >= 1:
        _add_buttresses(wall, w, h, t, gothic, rng)

    # --- Skulls above windows (now from gothic 2+) ---
    if gothic >= 2 and window_positions:
        _add_skulls_above_windows(wall, window_positions, h, t, rng)

    # --- Aquila on wall center (now from gothic 3 + detail 2) ---
    if gothic >= 3 and detail >= 2 and w >= 60:
        _add_aquila(wall, w, h, t, rng)

    # --- Stone block mortar lines (now from detail 1+) ---
    if detail >= 1:
        block_h = max(6.0, h / 10.0)
        line_w = 0.6 if detail >= 2 else 0.7
        add_panel_lines(wall, direction='HORIZONTAL',
                        count=max(3, int(h / block_h)),
                        line_width=line_w, line_depth=0.4)

    # --- Rivets at detail level 3 ---
    if detail >= 3 and t >= 2.5:
        _add_wall_rivets(wall, w, h, t, rng)

    # --- Bevel ---
    if bevel_w > 0:
        _apply_bevel(wall, bevel_w)

    # --- Damage ---
    apply_damage(wall, damage, seed)

    # --- Connectors ---
    add_connectors(
        wall, connector,
        pin_tolerance=params.get('pin_tolerance', 0.25),
        magnet_diameter=params.get('magnet_diameter', 5.0),
        magnet_height=params.get('magnet_height', 2.0),
    )

    # --- Final cleanup ---
    cleanup_mesh(wall)

    # --- Split for print ---
    if split_mode == 'AUTO' and should_split(wall):
        parts = split_for_print(wall)
        for i, p in enumerate(parts):
            p.name = f"Wall_Segment_{i:02d}"
            cleanup_mesh(p)
        return parts

    return [wall]


def _add_windows(wall, w, h, t, count, gothic_level, detail_level, rng):
    """Cut gothic arch windows into the wall. Returns list of (x, z) positions."""
    # Window sizing — tall and narrow for authentic gothic look
    win_w = min(w / (count + 1) * 0.45, 22.0)
    win_h = min(h * 0.55, 45.0)
    # Gothic windows are taller than wide (aspect ratio ~1:2.5)
    if gothic_level > 0:
        win_h = min(h * 0.6, 50.0)
        win_w = min(win_w, win_h * 0.4)  # narrower for lancet look

    spacing = w / (count + 1)
    start_x = -w / 2 + spacing
    positions = []

    for i in range(count):
        cx = start_x + i * spacing
        cz = h * 0.48  # slightly above center for imposing look

        if gothic_level > 0:
            cutter = create_gothic_arch_cutter(
                win_w, win_h, t + 2.0,
                segments=max(8, gothic_level * 4),
                name=f"_win_cut_{i}"
            )
        else:
            cutter = create_box_object(
                win_w, win_h, t + 2.0,
                location=(0, 0, win_h / 2),
                name=f"_win_cut_{i}"
            )

        cutter.location.x = cx
        cutter.location.y = 0
        cutter.location.z = cz
        bpy.context.view_layer.objects.active = cutter
        cutter.select_set(True)
        bpy.ops.object.transform_apply(location=True)
        boolean_difference(wall, cutter)
        positions.append((cx, cz))

        # Raised arch frame around window (gothic 1+ detail 1+)
        if gothic_level >= 1 and detail_level >= 1:
            frame = create_arch_frame(
                win_w, win_h, depth=1.5,
                frame_thickness=1.5,
                segments=max(8, gothic_level * 4),
                name=f"_win_frame_{i}"
            )
            frame.location = Vector((cx, -(t / 2 + 0.3), cz))
            bpy.context.view_layer.objects.active = frame
            frame.select_set(True)
            bpy.ops.object.transform_apply(location=True)
            boolean_union(wall, frame)

        # Window sill / ledge
        if gothic_level >= 1 and detail_level >= 1:
            sill_w = win_w + 4.0
            sill_h = 2.0
            sill_d = t + 2.5
            sill = create_box_object(
                sill_w, sill_h, sill_d,
                location=(cx, 0, cz - win_h / 2 - sill_h / 2 + 0.5),
                name=f"_win_sill_{i}"
            )
            boolean_union(wall, sill)

    return positions


def _add_pilasters(wall, w, h, t, window_positions, rng):
    """Add pilaster strips between windows for Sector Imperialis look."""
    pil_w = max(3.0, t * 0.8)
    pil_h = h * 0.85
    pil_d = max(1.5, t * 0.5)

    # Place pilasters between each pair of windows
    if len(window_positions) < 2:
        return
    for i in range(len(window_positions) - 1):
        x1 = window_positions[i][0]
        x2 = window_positions[i + 1][0]
        px = (x1 + x2) / 2.0
        pilaster = create_pilaster(pil_w, pil_h, pil_d, name=f"_pilaster_{i}")
        pilaster.location = Vector((px, -(t / 2 + pil_d / 2 - 0.5), 0))
        bpy.context.view_layer.objects.active = pilaster
        pilaster.select_set(True)
        bpy.ops.object.transform_apply(location=True)
        boolean_union(wall, pilaster)


def _add_buttresses(wall, w, h, t, gothic_level, rng):
    """Add buttresses to wall edges and optionally center."""
    butt_w = max(t * 1.5, 5.0)
    butt_h = h * 0.88
    butt_d = max(t * 2.0, 8.0)
    positions_x = [-w / 2 + butt_w / 2, w / 2 - butt_w / 2]
    if gothic_level >= 2 and w > 80:
        positions_x.append(0.0)
    if gothic_level >= 3 and w > 120:
        positions_x.append(-w / 4)
        positions_x.append(w / 4)

    for px in positions_x:
        butt = create_buttress(
            butt_w, butt_h, butt_d,
            taper=0.55,
            name="_buttress"
        )
        butt.location = Vector((px, -(t / 2 + butt_d / 2 - 1.0), 0))
        bpy.context.view_layer.objects.active = butt
        butt.select_set(True)
        bpy.ops.object.transform_apply(location=True)
        boolean_union(wall, butt)


def _add_skulls_above_windows(wall, window_positions, h, t, rng):
    """Place skull reliefs centered above each window."""
    skull_w = max(6.0, min(10.0, h * 0.08))
    skull_h = skull_w * 1.15
    for i, (wx, wz) in enumerate(window_positions):
        skull = create_skull_relief(
            width=skull_w, height=skull_h, depth=1.2,
            name=f"_skull_{i}"
        )
        # Position above window
        skull.location = Vector((wx, -(t / 2 + 0.3), wz + 25.0))
        bpy.context.view_layer.objects.active = skull
        skull.select_set(True)
        bpy.ops.object.transform_apply(location=True)
        boolean_union(wall, skull)


def _add_aquila(wall, w, h, t, rng):
    """Place an Imperial Aquila relief on the wall center."""
    aq_w = min(w * 0.35, 40.0)
    aq_h = aq_w * 0.5
    aquila = create_aquila_relief(aq_w, aq_h, depth=1.2, name="_aquila")
    # Place in upper-center area of wall
    aquila.location = Vector((0, -(t / 2 + 0.3), h * 0.78))
    bpy.context.view_layer.objects.active = aquila
    aquila.select_set(True)
    bpy.ops.object.transform_apply(location=True)
    boolean_union(wall, aquila)


def _add_wall_rivets(wall, w, h, t, rng):
    """Add rows of rivets along the wall for industrial gothic detail."""
    rivet_positions = []
    # Rivets along bottom edge
    y_pos = -(t / 2) - 0.1
    for rx in range(-int(w / 2) + 8, int(w / 2) - 5, 12):
        rivet_positions.append(Vector((rx, y_pos, 5.0)))
        rivet_positions.append(Vector((rx, y_pos, h - 5.0)))
    add_rivets(wall, rivet_positions, rivet_radius=0.8, rivet_depth=0.8)


def _apply_bevel(obj, width):
    """Apply a bevel modifier if width > 0."""
    if width <= 0:
        return
    bpy.context.view_layer.objects.active = obj
    obj.select_set(True)
    mod = obj.modifiers.new("Bevel", 'BEVEL')
    mod.width = width
    mod.segments = 1
    mod.limit_method = 'ANGLE'
    mod.angle_limit = math.radians(60)
    try:
        bpy.ops.object.modifier_apply(modifier=mod.name)
    except RuntimeError:
        if mod.name in [m.name for m in obj.modifiers]:
            obj.modifiers.remove(mod)
