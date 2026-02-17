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
