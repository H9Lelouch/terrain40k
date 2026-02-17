"""
Pillar Cluster / Scatter generator for Warhammer 40K terrain.
Generates groups of gothic pillars with bases, optionally damaged.
"""

import bpy
import math
import random
from mathutils import Vector
from ..utils.mesh import (
    create_box_object,
    boolean_union,
    cleanup_mesh,
)
from .gothic_details import create_pillar, create_fluted_column, create_skull_relief
from .connectors import add_connectors
from .damage import apply_damage


def generate_pillar_cluster(params):
    """
    Generate a cluster of gothic pillars on a shared base platform.

    params dict keys:
        width (float): Cluster spread area width (default 80)
        height (float): Pillar height (default 60)
        depth (float): Cluster spread area depth (default 80)
        wall_thickness (float): Used for pillar radius scaling (default 3.0)
        detail_level (int): 0-3, affects pillar complexity
        gothic_style (int): 0-3, affects pillar style
        damage_intensity (float): 0.0-1.0
        seed (int): Random seed
        connector_type (str): 'NONE','PINS','MAGNETS','BOTH'
        split_mode (str): 'AUTO','OFF','MANUAL'

    Returns: list of objects
    """
    w = params.get('width', 80.0)
    h = params.get('height', 60.0)
    d = params.get('depth', 80.0)
    detail = params.get('detail_level', 1)
    gothic = params.get('gothic_style', 1)
    damage_val = params.get('damage_intensity', 0.2)
    seed = params.get('seed', 42)
    connector = params.get('connector_type', 'NONE')

    rng = random.Random(seed)

    # Determine pillar count based on area
    area = w * d
    base_count = max(2, min(6, int(area / 1500)))
    pillar_count = base_count + (1 if detail >= 2 else 0)

    # Pillar radius
    pillar_r = max(3.0, min(w, d) * 0.06)

    # --- Shared base platform ---
    base_h = max(3.0, h * 0.04)
    base_platform = create_box_object(
        w, base_h, d,
        location=(0, 0, base_h / 2),
        name="Pillar_Base"
    )

    # --- Generate pillars ---
    pillars = []
    positions_used = []
    for i in range(pillar_count):
        # Find a non-overlapping position
        for _attempt in range(20):
            px = rng.uniform(-w / 2 + pillar_r * 2, w / 2 - pillar_r * 2)
            py = rng.uniform(-d / 2 + pillar_r * 2, d / 2 - pillar_r * 2)
            too_close = False
            for used_x, used_y in positions_used:
                if math.sqrt((px - used_x) ** 2 + (py - used_y) ** 2) < pillar_r * 5:
                    too_close = True
                    break
            if not too_close:
                break

        positions_used.append((px, py))

        # Vary pillar height slightly for organic look
        ph = h * rng.uniform(0.7, 1.0)

        # Determine if this pillar is broken (damage)
        is_broken = rng.random() < damage_val * 0.5

        if is_broken:
            ph *= rng.uniform(0.3, 0.7)

        # Use fluted columns at gothic level 2+ for authentic look
        if gothic >= 2 and not is_broken:
            p = create_fluted_column(
                radius=pillar_r,
                height=ph,
                flute_count=max(6, gothic * 3),
                flute_depth=0.5,
                segments=max(12, 8 + gothic * 2),
                name=f"Pillar_{i}"
            )
        else:
            p = create_pillar(
                radius=pillar_r,
                height=ph,
                segments=max(8, 8 + gothic * 2),
                name=f"Pillar_{i}"
            )
        p.location = Vector((px, py, base_h))
        bpy.context.view_layer.objects.active = p
        p.select_set(True)
        bpy.ops.object.transform_apply(location=True)
        pillars.append(p)

    # --- Union all pillars with base ---
    result = base_platform
    for p in pillars:
        boolean_union(result, p, remove_other=True)

    result.name = "Pillar_Cluster"

    # --- Skull decorations on base (gothic 3) ---
    if gothic >= 3 and len(positions_used) >= 2:
        # Place skull between first two pillars
        sx = (positions_used[0][0] + positions_used[1][0]) / 2
        sy = (positions_used[0][1] + positions_used[1][1]) / 2
        skull = create_skull_relief(width=6.0, height=7.0, depth=1.0, name="_pil_skull")
        skull.location = Vector((sx, sy, base_h + 0.5))
        bpy.context.view_layer.objects.active = skull
        skull.select_set(True)
        bpy.ops.object.transform_apply(location=True)
        boolean_union(result, skull, remove_other=True)

    # --- Scatter debris around pillars ---
    if detail >= 1 and damage_val > 0.1:
        _add_debris(result, w, d, base_h, damage_val, rng)

    # --- Damage ---
    if damage_val > 0.2:
        apply_damage(result, damage_val * 0.5, seed)

    # --- Connectors ---
    add_connectors(
        result, connector,
        pin_tolerance=params.get('pin_tolerance', 0.25),
        magnet_diameter=params.get('magnet_diameter', 5.0),
        magnet_height=params.get('magnet_height', 2.0),
    )

    # --- Cleanup ---
    cleanup_mesh(result)

    return [result]


def _add_debris(target, area_w, area_d, base_h, intensity, rng):
    """Add small debris blocks around the base."""
    count = max(1, int(intensity * 5))
    for i in range(count):
        dw = rng.uniform(2.0, 6.0)
        dh = rng.uniform(1.5, 4.0)
        dd = rng.uniform(2.0, 5.0)
        dx = rng.uniform(-area_w / 2 + 3, area_w / 2 - 3)
        dy = rng.uniform(-area_d / 2 + 3, area_d / 2 - 3)
        debris = create_box_object(
            dw, dh, dd,
            location=(dx, dy, base_h + dh / 2),
            name=f"_debris_{i}"
        )
        # Random rotation for organic look
        debris.rotation_euler.x = rng.uniform(-0.3, 0.3)
        debris.rotation_euler.y = rng.uniform(-0.3, 0.3)
        debris.rotation_euler.z = rng.uniform(0, math.pi)
        bpy.context.view_layer.objects.active = debris
        debris.select_set(True)
        bpy.ops.object.transform_apply(location=True, rotation=True)
        boolean_union(target, debris, remove_other=True)
