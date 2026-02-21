"""
Connector system for modular terrain pieces.
Supports pins, magnet seats, or both.
All dimensions in mm.
"""

import bpy
import math
from mathutils import Vector
from ..utils.mesh import (
    create_cylinder_object,
    create_box_object,
    boolean_union,
    boolean_difference,
)


# Default connector dimensions
DEFAULT_PIN_RADIUS = 2.0
DEFAULT_PIN_HEIGHT = 4.0
DEFAULT_PIN_TOLERANCE = 0.25  # per side for female
DEFAULT_MAGNET_DIAMETER = 5.0
DEFAULT_MAGNET_HEIGHT = 2.0
DEFAULT_MAGNET_TOLERANCE = 0.15


def _get_edge_positions(obj, edge='BOTTOM', count=2, inset=8.0):
    """
    Calculate connector positions along an edge of the object's bounding box.
    Returns list of Vector positions.
    """
    bb = obj.bound_box
    min_co = Vector(bb[0])
    max_co = Vector(bb[6])
    positions = []
    for i in range(count):
        t = (i + 1) / (count + 1)
        x = min_co.x + (max_co.x - min_co.x) * t
        y = (min_co.y + max_co.y) / 2.0
        if edge == 'BOTTOM':
            z = min_co.z
        elif edge == 'TOP':
            z = max_co.z
        elif edge == 'LEFT':
            x = min_co.x
            z = min_co.z + (max_co.z - min_co.z) * t
        elif edge == 'RIGHT':
            x = max_co.x
            z = min_co.z + (max_co.z - min_co.z) * t
        else:
            z = min_co.z
        positions.append(Vector((x, y, z)))
    return positions


def add_pin_male(target_obj, positions, pin_radius=DEFAULT_PIN_RADIUS,
                 pin_height=DEFAULT_PIN_HEIGHT):
    """Add protruding pin connectors (male) at specified positions."""
    for pos in positions:
        pin = create_cylinder_object(
            pin_radius, pin_height, segments=12,
            location=(pos.x, pos.y, pos.z),
            name="_pin_male"
        )
        boolean_union(target_obj, pin, remove_other=True)


def add_pin_female(target_obj, positions, pin_radius=DEFAULT_PIN_RADIUS,
                   pin_height=DEFAULT_PIN_HEIGHT, tolerance=DEFAULT_PIN_TOLERANCE):
    """Cut pin holes (female) at specified positions."""
    hole_radius = pin_radius + tolerance
    hole_depth = pin_height + 0.5  # slightly deeper for easy insertion
    for pos in positions:
        hole = create_cylinder_object(
            hole_radius, hole_depth, segments=12,
            location=(pos.x, pos.y, pos.z - 0.3),
            name="_pin_hole"
        )
        boolean_difference(target_obj, hole, remove_cutter=True)


def add_magnet_seats(target_obj, positions,
                     magnet_diameter=DEFAULT_MAGNET_DIAMETER,
                     magnet_height=DEFAULT_MAGNET_HEIGHT,
                     tolerance=DEFAULT_MAGNET_TOLERANCE):
    """
    Cut cylindrical pockets for magnets at specified positions.
    Pocket is cut into the surface (boolean difference).
    """
    pocket_radius = (magnet_diameter / 2.0) + tolerance
    pocket_depth = magnet_height + 0.3  # slight extra depth
    for pos in positions:
        pocket = create_cylinder_object(
            pocket_radius, pocket_depth, segments=16,
            location=(pos.x, pos.y, pos.z - 0.1),
            name="_magnet_pocket"
        )
        boolean_difference(target_obj, pocket, remove_cutter=True)


def add_connectors(target_obj, connector_type, positions=None,
                   is_male_side=True, pin_radius=DEFAULT_PIN_RADIUS,
                   pin_height=DEFAULT_PIN_HEIGHT, pin_tolerance=DEFAULT_PIN_TOLERANCE,
                   magnet_diameter=DEFAULT_MAGNET_DIAMETER,
                   magnet_height=DEFAULT_MAGNET_HEIGHT):
    """
    High-level function to add connectors based on type.
    connector_type: 'NONE', 'PINS', 'MAGNETS', 'BOTH'
    If positions is None, auto-detect from bottom edge.
    """
    if connector_type == 'NONE':
        return
    if positions is None:
        count = 2
        positions = _get_edge_positions(target_obj, edge='BOTTOM', count=count)
    if connector_type in ('PINS', 'BOTH'):
        if is_male_side:
            add_pin_male(target_obj, positions, pin_radius, pin_height)
        else:
            add_pin_female(target_obj, positions, pin_radius, pin_height,
                           pin_tolerance)
    if connector_type in ('MAGNETS', 'BOTH'):
        # Magnet seats are always female (recessed pockets)
        mag_positions = positions
        if connector_type == 'BOTH':
            # Offset magnet positions slightly from pin positions
            mag_positions = [p + Vector((0, 0, -pin_height - 2)) for p in positions]
            mag_positions = _get_edge_positions(target_obj, edge='BOTTOM', count=2,
                                                inset=15.0)
        add_magnet_seats(target_obj, mag_positions, magnet_diameter, magnet_height)


# ── Ground Floor Wall connectors ─────────────────────────────────────────────

def add_ground_wall_connectors(obj, w, h, t,
                                magnet_diameter=3.0,
                                magnet_height=2.0):
    """
    Ground floor wall: 3-hole connector clusters on three edges.
    No bottom connectors — this module is the stack base.

    TOP EDGE  (drilled –Z, 3 holes along X):
        left_buttress: magnet | wall_centre: lego_pin | right_buttress: magnet

    LEFT / RIGHT EDGE  (drilled horizontally in ±X, 3 holes along Z):
        top: magnet | middle: lego_pin | bottom: magnet
        A shallow reinforcement boss is unioned at each end to ensure
        ≥ 1 mm wall around every hole even at 3 mm wall thickness.

    Lego Technic pin socket : Ø 4.85 mm × 8 mm deep (female).
    Magnet pockets          : (magnet_diameter/2 + 0.1) radius, magnet_height + 0.3 deep.
    """
    p_pillar      = max(t * 2.2, 7.0)
    p_rear        = max(t * 0.25, 0.8)
    butt_w        = max(7.0, t * 1.5)
    butt_protrude = p_pillar + 1.0          # same formula as wall_segment
    plinth_h      = max(min(h * 0.07, 8.0), 5.0)
    cornice_h     = max(min(h * 0.05, 6.0), 4.0)

    bb     = obj.bound_box
    min_co = Vector(bb[0])
    max_co = Vector(bb[6])

    lego_r   = 2.425          # Ø 4.85 mm / 2 — standard Lego Technic pin socket
    lego_d   = 8.0
    mag_r    = magnet_diameter / 2.0 + 0.1   # +0.1 mm press-fit tolerance
    mag_d    = magnet_height + 0.3
    min_wall = 1.0

    # ── TOP EDGE ─────────────────────────────────────────────────────────
    # Y centre of the cornice cross-section
    cy_top = (-(t / 2 + p_pillar) + (t / 2 + p_rear)) / 2.0
    top_z  = max_co.z

    # Top-centre hole is a magnet, not a lego pin.
    # Reason: cornice cross-section (t + p_pillar + p_rear ≈ 6.3 mm) is too shallow
    # for a Ø4.85 mm pin with ≥ 1 mm wall on all sides (needs ≥ 6.85 mm).
    # Three magnets keep the top connection simple and within wall-thickness rules.
    _cut_top_hole(obj, min_co.x + butt_w / 2,     cy_top, top_z, mag_r, mag_d, "_top_mag_l")
    _cut_top_hole(obj, (min_co.x + max_co.x) / 2, cy_top, top_z, mag_r, mag_d, "_top_mag_c")
    _cut_top_hole(obj, max_co.x - butt_w / 2,     cy_top, top_z, mag_r, mag_d, "_top_mag_r")

    # ── LEFT / RIGHT EDGES ────────────────────────────────────────────────
    # Reinforcement boss: extends the buttress delta_y mm further in –Y so
    # that every side hole has ≥ min_wall mm of material on all sides.
    butt_d  = t + butt_protrude
    delta_y = max(0.0, 2.0 * (lego_r + min_wall) - butt_d) + 1.5
    boss_d  = butt_d + delta_y

    # Y centre of the reinforced cross-section
    front_y = -(t / 2.0 + butt_protrude + delta_y)
    cy_side = (front_y + t / 2.0) / 2.0

    # Z positions of the three side holes (inside safe structural zone)
    hz_bot = plinth_h + 10.0
    hz_mid = h / 2.0
    hz_top = h - cornice_h - 10.0

    for side, face_x, boss_cx in [
        (-1, min_co.x, min_co.x + butt_w / 2.0),
        (+1, max_co.x, max_co.x - butt_w / 2.0),
    ]:
        boss_z0 = plinth_h
        boss_zh = min(h * 0.92, h - cornice_h) - plinth_h
        sfx     = 'l' if side < 0 else 'r'

        # Core boss — full depth so every connector hole has ≥ min_wall material
        boss = create_box_object(
            butt_w, boss_zh, boss_d,
            location=(boss_cx, cy_side, boss_z0),
            name=f"_side_boss_{sfx}",
        )
        boolean_union(obj, boss)

        # Gothic pilaster styling — matches internal pilasters in wall_segment.py
        # Base and cap protrude extra_y mm beyond the boss front face.
        # The recessed shaft panel uses the same Y-formula as _build_pilasters.
        base_h_b = max(boss_zh * 0.07, 2.0)
        cap_h_b  = max(boss_zh * 0.06, 1.5)
        extra_y  = 1.0                       # extra front protrusion for base/cap

        # Width stays butt_w — no X-overflow past the flat connector side face.
        # The pilaster effect comes from the extra Y-depth only.
        base_b = create_box_object(
            butt_w, base_h_b, boss_d + extra_y,
            location=(boss_cx, cy_side - extra_y / 2, boss_z0),
            name=f"_boss_base_{sfx}",
        )
        boolean_union(obj, base_b)

        cap_b = create_box_object(
            butt_w, cap_h_b, boss_d + extra_y,
            location=(boss_cx, cy_side - extra_y / 2,
                      boss_z0 + boss_zh - cap_h_b),
            name=f"_boss_cap_{sfx}",
        )
        boolean_union(obj, cap_b)

        # Recessed panel on shaft face (1 mm groove into front_y surface)
        shaft_h_b = boss_zh - base_h_b - cap_h_b
        pan_m     = 1.5
        pan_w_b   = butt_w - 2 * pan_m
        pan_h_b   = shaft_h_b - 2 * pan_m
        recess_d  = 1.0
        if pan_w_b >= 3.0 and pan_h_b >= 5.0:
            cut_y_b = front_y + recess_d / 2
            cutter  = create_box_object(
                pan_w_b, pan_h_b, recess_d + 0.4,
                location=(boss_cx, cut_y_b,
                          boss_z0 + base_h_b + pan_m),
                name=f"_boss_panel_{sfx}",
            )
            boolean_difference(obj, cutter)

        # Three horizontal holes drilled from the end face
        _cut_side_hole(obj, face_x, cy_side, hz_bot, mag_r,  mag_d,  side, "_side_mag_bot")
        _cut_side_hole(obj, face_x, cy_side, hz_mid, lego_r, lego_d, side, "_side_lego")
        _cut_side_hole(obj, face_x, cy_side, hz_top, mag_r,  mag_d,  side, "_side_mag_top")


def _cut_top_hole(obj, cx, cy, top_z, radius, depth, name):
    """Drill a downward cylindrical hole (–Z) from the top face."""
    cyl = create_cylinder_object(
        radius, depth + 0.5,
        segments=16,
        location=(cx, cy, top_z - depth),
        name=name,
    )
    boolean_difference(obj, cyl, remove_cutter=True)


def _cut_side_hole(obj, face_x, cy, cz, radius, depth, side, name):
    """
    Drill a horizontal cylindrical hole from a wall end face (X direction).
    side: –1 = left face (drill in +X), +1 = right face (drill in –X).

    Cylinder is created along Z then rotated 90° around Y.
    After Ry(90°): (x, y, z) → (z, y, –x), so:
        Z-extent [oz, oz+h] maps to X-extent [oz, oz+h]
        XY-ring  centred at (ox, oy) maps to YZ-ring centred at (oy, –ox)
    """
    oz = (face_x - 0.5) if side < 0 else (face_x - depth - 0.5)
    cyl = create_cylinder_object(
        radius, depth + 1.0,
        segments=16,
        location=(-cz, cy, oz),
        name=name,
    )
    cyl.rotation_euler.y = math.radians(90)
    bpy.context.view_layer.objects.active = cyl
    cyl.select_set(True)
    bpy.ops.object.transform_apply(rotation=True)
    boolean_difference(obj, cyl, remove_cutter=True)
