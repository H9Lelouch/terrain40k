"""
Auto-split large terrain pieces to fit the BambuLab A1 print bed.
Build volume: 256 x 256 x 256 mm.
"""

import bpy
import bmesh
from mathutils import Vector
from ..utils.mesh import boolean_difference, create_box_object, cleanup_mesh

# BambuLab A1 build volume (mm)
BED_X = 256.0
BED_Y = 256.0
BED_Z = 256.0
# Safety margin
MARGIN = 2.0
MAX_X = BED_X - MARGIN
MAX_Y = BED_Y - MARGIN
MAX_Z = BED_Z - MARGIN


def get_dimensions(obj):
    """Get object dimensions from bounding box in world space."""
    bb = obj.bound_box
    min_co = Vector(bb[0])
    max_co = Vector(bb[6])
    return max_co - min_co, min_co, max_co


def should_split(obj):
    """Check if an object exceeds the print bed dimensions."""
    dims, _, _ = get_dimensions(obj)
    return dims.x > MAX_X or dims.y > MAX_Y or dims.z > MAX_Z


def split_for_print(obj, bed_x=MAX_X, bed_y=MAX_Y):
    """
    Split an object into segments that fit the print bed.
    Uses bisection along the longest axis.
    Returns list of resulting objects.
    """
    dims, min_co, max_co = get_dimensions(obj)
    if dims.x <= bed_x and dims.y <= bed_y and dims.z <= MAX_Z:
        return [obj]

    # Determine split axis (longest that exceeds bed)
    if dims.x > bed_x and dims.x >= dims.y:
        axis = 'X'
        split_pos = (min_co.x + max_co.x) / 2.0
    elif dims.y > bed_y:
        axis = 'Y'
        split_pos = (min_co.y + max_co.y) / 2.0
    else:
        axis = 'X'
        split_pos = (min_co.x + max_co.x) / 2.0

    # Create two halves using boolean intersection approach
    # Duplicate the object for the second half
    bpy.ops.object.select_all(action='DESELECT')
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj
    bpy.ops.object.duplicate()
    obj_copy = bpy.context.active_object
    obj_copy.name = obj.name + "_B"
    obj.name = obj.name + "_A"

    big = max(dims.x, dims.y, dims.z) + 10.0

    if axis == 'X':
        # Cut right half from obj (keep left)
        cutter_a = create_box_object(
            dims.x, big, big,
            location=(split_pos + dims.x / 2.0, (min_co.y + max_co.y) / 2,
                      (min_co.z + max_co.z) / 2),
            name="_split_cut_a"
        )
        boolean_difference(obj, cutter_a)
        # Cut left half from copy (keep right)
        cutter_b = create_box_object(
            dims.x, big, big,
            location=(split_pos - dims.x / 2.0, (min_co.y + max_co.y) / 2,
                      (min_co.z + max_co.z) / 2),
            name="_split_cut_b"
        )
        boolean_difference(obj_copy, cutter_b)
    else:
        cutter_a = create_box_object(
            big, dims.y, big,
            location=((min_co.x + max_co.x) / 2, split_pos + dims.y / 2.0,
                      (min_co.z + max_co.z) / 2),
            name="_split_cut_a"
        )
        boolean_difference(obj, cutter_a)
        cutter_b = create_box_object(
            big, dims.y, big,
            location=((min_co.x + max_co.x) / 2, split_pos - dims.y / 2.0,
                      (min_co.z + max_co.z) / 2),
            name="_split_cut_b"
        )
        boolean_difference(obj_copy, cutter_b)

    cleanup_mesh(obj)
    cleanup_mesh(obj_copy)

    # Recursively split if still too large
    results = []
    results.extend(split_for_print(obj, bed_x, bed_y))
    results.extend(split_for_print(obj_copy, bed_x, bed_y))
    return results
