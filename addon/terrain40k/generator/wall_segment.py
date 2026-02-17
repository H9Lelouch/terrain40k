"""
Wall Segment generator for Warhammer 40K imperial ruins.
Generates a rectangular wall with gothic arch windows, optional buttresses,
panel details, and battle damage.
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
    create_buttress,
    add_panel_lines,
)
from .connectors import add_connectors
from .damage import apply_damage
from .splitter import should_split, split_for_print


def generate_wall_segment(params):
    """
    Generate a wall segment with windows and details.

    params dict keys:
        width (float): Wall width in mm (default 100)
        height (float): Wall height in mm (default 80)
        wall_thickness (float): Thickness in mm (default 3.0)
        window_density (int): Number of windows 0-5 (default 2)
        detail_level (int): 0-3 (default 1)
        gothic_style (int): 0-3 (default 1)
        damage_intensity (float): 0.0-1.0 (default 0.3)
        seed (int): Random seed (default 42)
        connector_type (str): 'NONE','PINS','MAGNETS','BOTH'
        split_mode (str): 'AUTO','OFF','MANUAL'
        pin_tolerance (float): Tolerance for pins (default 0.25)
        magnet_diameter (float): Magnet diameter (default 5.0)
        magnet_height (float): Magnet height (default 2.0)
        bevel_width (float): Bevel on edges (default 0.0, 0=off)

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

    # --- Windows ---
    if win_count > 0:
        _add_windows(wall, w, h, t, win_count, gothic, rng)

    # --- Buttresses ---
    if gothic >= 1:
        _add_buttresses(wall, w, h, t, gothic, rng)

    # --- Panel lines / details ---
    if detail >= 2:
        add_panel_lines(wall, direction='HORIZONTAL', count=detail,
                        line_width=0.8, line_depth=0.6)

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


def _add_windows(wall, w, h, t, count, gothic_level, rng):
    """Cut gothic arch windows into the wall."""
    # Window sizing
    win_w = min(w / (count + 1) * 0.55, 25.0)  # max ~25mm wide
    win_h = min(h * 0.55, 45.0)
    if gothic_level == 0:
        # Simple rectangular windows
        win_h_rect = win_h
    else:
        win_h_rect = win_h  # gothic arch profile handles the shape

    # Spacing
    spacing = w / (count + 1)
    start_x = -w / 2 + spacing

    for i in range(count):
        cx = start_x + i * spacing
        cz = h * 0.45  # window center height

        if gothic_level > 0:
            cutter = create_gothic_arch_cutter(
                win_w, win_h, t + 2.0,
                segments=max(8, gothic_level * 4),
                name=f"_win_cut_{i}"
            )
        else:
            # Rectangular window
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

        # Optional: window frame ledge (detail level 2+)
        if gothic_level >= 2:
            frame_depth = 1.5
            frame_w = win_w + 3.0
            frame_h = 2.0
            sill = create_box_object(
                frame_w, frame_h, t + frame_depth,
                location=(cx, 0, cz - win_h / 2 - frame_h / 2 + 1.0),
                name=f"_win_sill_{i}"
            )
            boolean_union(wall, sill)


def _add_buttresses(wall, w, h, t, gothic_level, rng):
    """Add buttresses to the wall sides."""
    butt_w = max(t * 1.5, 5.0)
    butt_h = h * 0.85
    butt_d = max(t * 2.0, 8.0)
    # Place at edges
    positions_x = [-w / 2 + butt_w / 2, w / 2 - butt_w / 2]
    if gothic_level >= 2 and w > 80:
        # Add center buttress for wide walls
        positions_x.append(0.0)
    if gothic_level >= 3 and w > 120:
        positions_x.append(-w / 4)
        positions_x.append(w / 4)

    for px in positions_x:
        butt = create_buttress(
            butt_w, butt_h, butt_d,
            taper=0.6,
            name="_buttress"
        )
        butt.location = Vector((px, -(t / 2 + butt_d / 2 - 1.0), 0))
        bpy.context.view_layer.objects.active = butt
        butt.select_set(True)
        bpy.ops.object.transform_apply(location=True)
        boolean_union(wall, butt)


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


def create_gothic_arch_cutter(width, height, depth, segments=12, name="ArchCutter"):
    """Local import wrapper."""
    from .gothic_details import create_gothic_arch_cutter as _create
    return _create(width, height, depth, segments, name)
