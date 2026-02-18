"""
Destruction / damage effects for terrain pieces.

Four damage states:
    CLEAN   – Pristine. No booleans applied.
    DAMAGED – Cracks, chips, bullet holes, mini-breaks.
    RUINED  – Large holes, major breakouts, missing segments.
    HALF    – 30–60 % of wall gone with angled collapse break.

intensity (0.0–1.0) scales the amount within the chosen state.
All damage via boolean operations → watertight output.
"""

import bpy
import math
import random
from mathutils import Vector
from ..utils.mesh import (
    create_box_object,
    create_cylinder_object,
    boolean_difference,
)


def apply_damage(obj, state='CLEAN', intensity=0.5, seed=42):
    """
    state:     'CLEAN' | 'DAMAGED' | 'RUINED' | 'HALF'
    intensity: 0.0–1.0, scales damage within the state.
    """
    rng = random.Random(seed)
    if state == 'CLEAN':
        return
    elif state == 'DAMAGED':
        _apply_damaged(obj, intensity, rng)
    elif state == 'RUINED':
        _apply_ruined(obj, intensity, rng)
    elif state == 'HALF':
        _apply_half(obj, intensity, rng)


# ── helpers ────────────────────────────────────────────────────────────────

def _bb(obj):
    """Return (min_co, max_co, size, cy) from object bounding box."""
    bb = obj.bound_box
    mn = Vector(bb[0])
    mx = Vector(bb[6])
    return mn, mx, mx - mn, (mn.y + mx.y) / 2.0


def _xfm(obj):
    """Apply rotation transform to obj."""
    bpy.context.view_layer.objects.active = obj
    obj.select_set(True)
    bpy.ops.object.transform_apply(rotation=True)


# ── CLEAN ──────────────────────────────────────────────────────────────────
# Nothing to do – no booleans, pristine geometry.


# ── DAMAGED ────────────────────────────────────────────────────────────────

def _apply_damaged(obj, intensity, rng):
    """
    Cracks, chips, bullet holes, mini-breaks at top.
    intensity 0→1 scales frequency and severity.
    """
    mn, mx, sz, cy = _bb(obj)

    # Bullet holes (always present)
    n_holes = max(1, round(1 + intensity * 5))
    for i in range(n_holes):
        r = rng.uniform(1.0, 2.5)
        d = rng.uniform(sz.y * 0.5, sz.y + 2.0)
        cx = rng.uniform(mn.x + 4, mx.x - 4)
        cz = rng.uniform(mn.z + 5, mx.z - 8)
        h = create_cylinder_object(r, d, segments=8,
                                   location=(cx, mn.y - 0.5, cz),
                                   name=f"_hole{i}")
        h.rotation_euler.x = math.radians(90)
        h.rotation_euler.y = rng.uniform(-0.25, 0.25)
        h.rotation_euler.z = rng.uniform(-0.25, 0.25)
        _xfm(h)
        boolean_difference(obj, h)

    # Surface chips (biased toward edges)
    n_chips = max(1, round(1 + intensity * 4))
    for i in range(n_chips):
        cw = rng.uniform(1.5, min(5.0, sz.x * 0.08))
        ch = rng.uniform(1.5, min(4.0, sz.z * 0.07))
        cd = rng.uniform(1.5, 3.5)
        if rng.random() < 0.45:
            cx = rng.choice([mn.x + cw * rng.uniform(0.2, 1.0),
                             mx.x - cw * rng.uniform(0.2, 1.0)])
        else:
            cx = rng.uniform(mn.x + cw, mx.x - cw)
        cz = rng.uniform(mn.z, mx.z - ch)
        c = create_box_object(cw, ch, cd,
                              location=(cx, mn.y, cz),
                              name=f"_chip{i}")
        c.rotation_euler.z = rng.uniform(-0.4, 0.4)
        c.rotation_euler.x = rng.uniform(-0.2, 0.2)
        _xfm(c)
        boolean_difference(obj, c)

    # Cracks – diagonal on wall face, rotate around Y
    if intensity > 0.25:
        n_cracks = max(1, round((intensity - 0.25) * 4))
        for i in range(n_cracks):
            cw = rng.uniform(1.0, 1.5)
            ch = rng.uniform(sz.z * 0.15, sz.z * 0.50)
            cd = rng.uniform(sz.y * 0.5, sz.y + 2.0)
            cx = rng.uniform(mn.x + 5, mx.x - 5)
            cz = rng.uniform(mn.z + ch * 0.1, mx.z - ch)
            c = create_box_object(cw, ch, cd,
                                  location=(cx, cy, cz),
                                  name=f"_crack{i}")
            # Diagonal on XZ wall face
            c.rotation_euler.y = rng.uniform(0.35, 1.05)
            c.rotation_euler.z = rng.uniform(-0.15, 0.15)
            _xfm(c)
            boolean_difference(obj, c)

    # Mini-breaks at top edge
    if intensity > 0.55:
        n_mini = max(1, round((intensity - 0.55) * 6))
        for i in range(n_mini):
            bw = rng.uniform(3.0, sz.x * 0.12)
            bh = rng.uniform(sz.z * 0.04, sz.z * 0.14)
            bd = sz.y + 4.0
            cx = rng.uniform(mn.x + bw, mx.x - bw)
            c = create_box_object(bw, bh, bd,
                                  location=(cx, cy, mx.z - bh * 0.6),
                                  name=f"_minibreak{i}")
            c.rotation_euler.y = rng.uniform(-0.2, 0.2)
            c.rotation_euler.z = rng.uniform(-0.15, 0.15)
            _xfm(c)
            boolean_difference(obj, c)


# ── RUINED ─────────────────────────────────────────────────────────────────

def _apply_ruined(obj, intensity, rng):
    """
    Large holes, major edge breakouts, missing wall segment.
    intensity 0→1 scales severity.
    """
    mn, mx, sz, cy = _bb(obj)

    # Large holes through the full wall thickness
    n_holes = max(1, round(1 + intensity * 3))
    for i in range(n_holes):
        r = rng.uniform(5.0, 8.0 + intensity * 6.0)
        safe_w = max(r + 3, sz.x * 0.15)
        cx = rng.uniform(mn.x + safe_w, mx.x - safe_w)
        cz = rng.uniform(mn.z + r + 2, mx.z - r - 4)
        h = create_cylinder_object(r, sz.y + 6.0, segments=12,
                                   location=(cx, mn.y - 0.5, cz),
                                   name=f"_rhole{i}")
        h.rotation_euler.x = math.radians(90)
        h.rotation_euler.y = rng.uniform(-0.15, 0.15)
        _xfm(h)
        boolean_difference(obj, h)

    # Major edge breakouts (top corners)
    if intensity > 0.2:
        n_breaks = max(1, round((intensity - 0.2) * 4))
        for i in range(n_breaks):
            bw = rng.uniform(sz.x * 0.10, sz.x * 0.28)
            bh = rng.uniform(sz.z * 0.15, sz.z * 0.50)
            bd = sz.y + 6.0
            side = rng.choice(['left', 'right'])
            cx = (mn.x + bw * 0.35) if side == 'left' else (mx.x - bw * 0.35)
            cz = mx.z - bh * 0.5 + rng.uniform(-bh * 0.3, bh * 0.2)
            b = create_box_object(bw, bh, bd,
                                  location=(cx, cy, cz),
                                  name=f"_rbreak{i}")
            b.rotation_euler.z = rng.uniform(-0.5, 0.5)
            b.rotation_euler.x = rng.uniform(-0.2, 0.2)
            _xfm(b)
            boolean_difference(obj, b)

    # Missing wall segment from one edge
    if intensity > 0.55:
        seg_frac = 0.18 + (intensity - 0.55) * 0.34  # 18–30 % of width
        sw = sz.x * seg_frac
        sd = sz.y + 6.0
        side = rng.choice(['left', 'right'])
        cx = (mn.x + sw * 0.45) if side == 'left' else (mx.x - sw * 0.45)
        sh = sz.z * rng.uniform(0.55, 0.90)
        s = create_box_object(sw, sh, sd,
                              location=(cx, cy, mx.z - sh),
                              name="_rseg")
        s.rotation_euler.y = rng.uniform(-0.1, 0.1)
        _xfm(s)
        boolean_difference(obj, s)


# ── HALF ───────────────────────────────────────────────────────────────────

def _apply_half(obj, intensity, rng):
    """
    Remove 30–60 % of wall with an angled break edge and jagged chunks.
    intensity 0→1 controls how much is removed (30 %→60 %).
    """
    mn, mx, sz, cy = _bb(obj)

    cut_fraction = 0.30 + intensity * 0.30   # 30–60 %
    from_left = rng.choice([True, False])
    break_x = (mn.x + sz.x * cut_fraction) if from_left else (mx.x - sz.x * cut_fraction)

    # Break angle in the XZ wall-face plane (rotate around Y): 15–40°
    angle_deg = rng.uniform(15.0, 40.0)
    if rng.random() < 0.5:
        angle_deg = -angle_deg

    # Main cutter – oversized box, rotation creates angled break line in XZ
    big = sz.x + 60.0
    cut_cx = (break_x - big / 2) if from_left else (break_x + big / 2)

    main = create_box_object(big, sz.z + 20.0, sz.y + 20.0,
                             location=(cut_cx, cy, mn.z - 10.0),
                             name="_half_main")
    main.rotation_euler.y = math.radians(angle_deg)
    _xfm(main)
    boolean_difference(obj, main)

    # Jagged chunks along the break edge
    n_jags = 3 + round(intensity * 4)
    for i in range(n_jags):
        jw = rng.uniform(sz.x * 0.04, sz.x * 0.10)
        jh = rng.uniform(sz.z * 0.08, sz.z * 0.30)
        jd = sz.y + 6.0
        jz = rng.uniform(mn.z, mx.z - jh)
        jx = break_x + rng.uniform(-sz.x * 0.08, sz.x * 0.08)
        jag = create_box_object(jw, jh, jd,
                                location=(jx, cy, jz),
                                name=f"_jag{i}")
        jag.rotation_euler.z = rng.uniform(-0.55, 0.55)
        jag.rotation_euler.x = rng.uniform(-0.15, 0.15)
        _xfm(jag)
        boolean_difference(obj, jag)
