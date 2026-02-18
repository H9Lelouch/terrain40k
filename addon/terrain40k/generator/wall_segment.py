"""
Wall Segment generator for Warhammer 40K imperial ruins.
Based on Sector Imperialis architecture (GW standard: 127 mm / 5").

Wall structure from Z=0 (ground):
    base_h  (~18 %)  solid foundation band / plinth zone
    win_h   (~55 %)  lancet arch window zone
    top_h   (~15 %)  solid top band (cornice / battlements later)

Key style rules:
    - Lancet ratio 1:2.8–1:3.5 (width:height) — very narrow
    - Buttresses at both wall ends, every 80 mm at gothic 2+
    - Pilasters between windows at gothic 1+
    - Skulls above windows at gothic 2+
    - Stone mortar courses across full height at detail 1+
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

    Detail level:
        0: Plain wall + windows only
        1: Plinth + buttresses + pilasters + mortar lines
        2: + window frames + sills + skulls
        3: + aquila relief + rivets

    Gothic style:
        0: Rectangular windows, no gothic elements
        1: Pointed arch windows + buttresses
        2: + pilasters + window sills/frames
        3: + skulls + aquila

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

    # ── Main wall slab ───────────────────────────────────────────────────────
    # Sits on ground: Z = 0 → h
    wall = create_box_object(w, h, t, location=(0, 0, 0), name="Wall_Segment")

    # ── Base plinth (foundation strip) ───────────────────────────────────────
    # Slightly wider and deeper than wall, sits at Z = 0 → plinth_h
    if detail >= 1:
        plinth_h = max(h * 0.06, 4.0)
        plinth = create_box_object(
            w + 4.0, plinth_h, t + 4.0,
            location=(0, 0, 0), name="_wall_plinth"
        )
        boolean_union(wall, plinth)

    # ── Windows ─────────────────────────────────────────────────────────────
    # Returns list of (cx, win_bottom, win_h) tuples
    window_positions = []
    if win_count > 0:
        window_positions = _add_windows(wall, w, h, t, win_count, gothic, detail, rng)

    # ── Pilasters between windows ────────────────────────────────────────────
    if gothic >= 1 and len(window_positions) >= 2:
        _add_pilasters(wall, h, t, window_positions)

    # ── Buttresses at wall ends (and optionally center) ──────────────────────
    if gothic >= 1:
        _add_buttresses(wall, w, h, t, gothic)

    # ── Skulls above windows ─────────────────────────────────────────────────
    if gothic >= 2 and detail >= 2 and window_positions:
        _add_skulls_above_windows(wall, window_positions, h, t)

    # ── Aquila on wall center ────────────────────────────────────────────────
    if gothic >= 3 and detail >= 2 and w >= 60:
        _add_aquila(wall, w, h, t)

    # ── Horizontal mortar / stone-course lines ───────────────────────────────
    if detail >= 1:
        course_h = max(7.0, h / 9.0)
        add_panel_lines(wall, direction='HORIZONTAL',
                        count=max(3, int(h / course_h)),
                        line_width=0.6, line_depth=0.4)

    # ── Rivets ───────────────────────────────────────────────────────────────
    if detail >= 3 and t >= 2.5:
        _add_wall_rivets(wall, w, h, t)

    # ── Bevel ────────────────────────────────────────────────────────────────
    if bevel_w > 0:
        _apply_bevel(wall, bevel_w)

    # ── Damage ───────────────────────────────────────────────────────────────
    apply_damage(wall, params.get('damage_state', 'CLEAN'), damage, seed)

    # ── Connectors ───────────────────────────────────────────────────────────
    add_connectors(
        wall, connector,
        pin_tolerance=params.get('pin_tolerance', 0.25),
        magnet_diameter=params.get('magnet_diameter', 5.0),
        magnet_height=params.get('magnet_height', 2.0),
    )

    # ── Cleanup ──────────────────────────────────────────────────────────────
    cleanup_mesh(wall)

    # ── Split for print ──────────────────────────────────────────────────────
    if split_mode == 'AUTO' and should_split(wall):
        parts = split_for_print(wall)
        for i, p in enumerate(parts):
            p.name = f"Wall_Segment_{i:02d}"
            cleanup_mesh(p)
        return parts

    return [wall]


# ── Window zone ────────────────────────────────────────────────────────────

def _wall_zones(h):
    """
    Return (base_h, win_h, top_h) for a wall of height h.
    All three sum to h; win_h capped at 60 mm for very tall walls.
    """
    base_h = max(h * 0.18, 12.0)
    top_h  = max(h * 0.15, 10.0)
    avail  = h - base_h - top_h
    win_h  = max(min(avail, 60.0), 15.0)
    # If win_h was capped, spread the surplus to top zone
    surplus = avail - win_h
    top_h += surplus
    return base_h, win_h, top_h


def _add_windows(wall, w, h, t, count, gothic_level, detail_level, rng):
    """
    Cut lancet arch windows into the wall.
    Returns list of (cx, win_bottom, win_h) tuples.

    Window zone sits between base_h (bottom) and base_h+win_h (top),
    leaving a solid top band of top_h mm.
    """
    base_h, win_h, top_h = _wall_zones(h)
    win_bottom = base_h  # window arch starts here (Z)

    # Spacing and width
    spacing = w / (count + 1)
    # Lancet: width 30–36 % of height → classic narrow proportion
    win_w = min(spacing * 0.58, win_h * 0.36, 20.0)
    win_w = max(win_w, 5.0)  # minimum printable width

    start_x = -w / 2 + spacing
    positions = []

    for i in range(count):
        cx = start_x + i * spacing

        # ── Arch cutter — profile begins at Z=0, placed at win_bottom ──────
        if gothic_level > 0:
            cutter = create_gothic_arch_cutter(
                win_w, win_h, t + 2.0,
                segments=max(8, gothic_level * 4),
                name=f"_win_cut_{i}"
            )
        else:
            # Flat-topped rectangular window, also starting at Z=0
            cutter = create_box_object(
                win_w, win_h, t + 2.0,
                location=(0, 0, 0),
                name=f"_win_cut_{i}"
            )

        cutter.location.x = cx
        cutter.location.y = 0
        cutter.location.z = win_bottom
        bpy.context.view_layer.objects.active = cutter
        cutter.select_set(True)
        bpy.ops.object.transform_apply(location=True)
        boolean_difference(wall, cutter)
        positions.append((cx, win_bottom, win_h))

        # ── Raised arch frame on front face ──────────────────────────────
        if gothic_level >= 1 and detail_level >= 1:
            frame = create_arch_frame(
                win_w, win_h,
                depth=1.5, frame_thickness=1.5,
                segments=max(8, gothic_level * 4),
                name=f"_win_frame_{i}"
            )
            # Frame profile also starts at Z=0 → position at win_bottom
            frame.location = Vector((cx, -(t / 2 + 0.3), win_bottom))
            bpy.context.view_layer.objects.active = frame
            frame.select_set(True)
            bpy.ops.object.transform_apply(location=True)
            boolean_union(wall, frame)

        # ── Window sill — ledge below the arch opening ───────────────────
        if gothic_level >= 1 and detail_level >= 1:
            sill_w = win_w + 6.0
            sill_h = 3.0
            sill_d = t + 6.0   # protrudes visibly from wall face
            # Sill top flush with window bottom; front-biased protrusion
            sill_cy = -(t / 2 + sill_d / 2 - t / 2)   # front-face biased
            sill = create_box_object(
                sill_w, sill_h, sill_d,
                location=(cx, sill_cy, win_bottom - sill_h),
                name=f"_win_sill_{i}"
            )
            boolean_union(wall, sill)

    return positions


# ── Pilasters ──────────────────────────────────────────────────────────────

def _add_pilasters(wall, h, t, window_positions):
    """Pilaster strips between window pairs — typical Sector Imperialis look."""
    pil_w = max(3.5, t * 0.9)
    pil_h = h * 0.88          # nearly full wall height
    pil_d = max(1.8, t * 0.55)

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


# ── Buttresses ─────────────────────────────────────────────────────────────

def _add_buttresses(wall, w, h, t, gothic_level):
    """
    Stepped buttresses at wall ends, with additional ones for wider walls.
    Buttresses start at Z=0 and taper upward — Sector Imperialis standard.
    """
    butt_w = max(t * 1.8, 6.0)
    butt_h = h * 0.90
    butt_d = max(t * 2.5, 10.0)

    positions_x = [-w / 2 + butt_w / 2, w / 2 - butt_w / 2]
    if gothic_level >= 2 and w > 80:
        positions_x.append(0.0)
    if gothic_level >= 3 and w > 130:
        positions_x.append(-w / 4)
        positions_x.append(w / 4)

    for px in positions_x:
        butt = create_buttress(butt_w, butt_h, butt_d, taper=0.55, name="_buttress")
        butt.location = Vector((px, -(t / 2 + butt_d / 2 - 1.0), 0))
        bpy.context.view_layer.objects.active = butt
        butt.select_set(True)
        bpy.ops.object.transform_apply(location=True)
        boolean_union(wall, butt)


# ── Skull reliefs ──────────────────────────────────────────────────────────

def _add_skulls_above_windows(wall, window_positions, h, t):
    """
    Skull reliefs in the top band, centered above each window.
    Placed in the solid zone between window top and wall top.
    """
    skull_w = max(6.0, min(10.0, h * 0.09))
    skull_h = skull_w * 1.15

    for wx, win_bottom, win_h in window_positions:
        win_top = win_bottom + win_h
        top_zone = h - win_top
        if top_zone < skull_h + 2.0:
            continue  # not enough space
        # Center skull in the top band
        skull_z = win_top + (top_zone - skull_h) * 0.40

        skull = create_skull_relief(
            width=skull_w, height=skull_h, depth=1.2,
            name="_skull"
        )
        skull.location = Vector((wx, -(t / 2 + 0.3), skull_z))
        bpy.context.view_layer.objects.active = skull
        skull.select_set(True)
        bpy.ops.object.transform_apply(location=True)
        boolean_union(wall, skull)


# ── Aquila ─────────────────────────────────────────────────────────────────

def _add_aquila(wall, w, h, t):
    """Imperial Aquila relief centered in the top band."""
    aq_w = min(w * 0.30, 35.0)
    aq_h = aq_w * 0.5
    aquila = create_aquila_relief(aq_w, aq_h, depth=1.2, name="_aquila")
    # Top-center of wall, in upper zone
    aquila.location = Vector((0, -(t / 2 + 0.3), h * 0.80))
    bpy.context.view_layer.objects.active = aquila
    aquila.select_set(True)
    bpy.ops.object.transform_apply(location=True)
    boolean_union(wall, aquila)


# ── Rivets ─────────────────────────────────────────────────────────────────

def _add_wall_rivets(wall, w, h, t):
    """Rows of rivets at base and top for industrial gothic flavour."""
    y_pos = -(t / 2) - 0.1
    rivet_positions = []
    for rx in range(-int(w / 2) + 8, int(w / 2) - 5, 12):
        rivet_positions.append(Vector((rx, y_pos, 6.0)))
        rivet_positions.append(Vector((rx, y_pos, h - 6.0)))
    add_rivets(wall, rivet_positions, rivet_radius=0.8, rivet_depth=0.8)


# ── Bevel ──────────────────────────────────────────────────────────────────

def _apply_bevel(obj, width):
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
