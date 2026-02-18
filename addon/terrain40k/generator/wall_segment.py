"""
Wall Segment generator for Warhammer 40K imperial ruins.
Based on Sector Imperialis architecture (GW standard: 127 mm / 5").

Vertical zones (Z = 0 at ground):
    plinth_h  (5–8 mm)   foundation band — protrudes p_pillar from wall face
    win_zone  (bulk)     [ Buttress | Window | Pilaster | Window | Buttress ]
    spandrel  (~10 mm)   solid zone above arch; skulls placed here
    cornice_h (4–6 mm)   top molding band — same protrusion as plinth

Pillar rhythm (N windows → N+1 vertical elements):
    - End buttresses at X = ±(w/2 − butt_w/2)  [wider + deeper, structural]
    - Internal pilasters at bay boundaries X = −w/2 + k·bay_w  (k = 1…N−1)
    - Windows centered in each bay at X = −w/2 + (k + ½)·bay_w

Protrusion depths scale with wall thickness t (not fixed mm):
    p_pillar = max(t × 0.8, 2.5)   structural layer (plinth/cornice/pilasters/buttresses)
    p_sill   = p_pillar + 1.0       window sill (just past structural)
    p_frame  = max(t × 0.4, 1.2)   arch frame (decorative ring)

Y coordinate formula for element protruding P mm (flush with wall back):
    depth = t + P,  loc_y = −P / 2
    → back face at Y = +t/2,  front face at Y = −(t/2 + P)
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
    add_panel_lines,
    add_stone_block_lines,
    add_rivets,
)
from .connectors import add_connectors
from .damage import apply_damage
from .splitter import should_split, split_for_print


def generate_wall_segment(params):
    """
    Generate an Imperial Gothic wall segment.

    Detail levels:
        0: plain slab + window openings only
        1: + plinth / cornice bands + pilasters + horizontal courses
        2: + window frames + sills + skulls (requires gothic >= 2/3)
        3: + full stone block grid + rivets

    Gothic levels:
        0: rectangular windows, no gothic elements
        1: lancet arch windows + pilasters + buttresses
        2: + raised window frames + window sills
        3: + skull reliefs in spandrel above arches
    """
    w          = params.get('width',          100.0)
    h          = params.get('height',          80.0)
    t          = params.get('wall_thickness',   3.0)
    win_count  = params.get('window_density',    2)
    detail     = params.get('detail_level',      1)
    gothic     = params.get('gothic_style',      1)
    damage     = params.get('damage_intensity', 0.3)
    seed       = params.get('seed',             42)
    connector  = params.get('connector_type',  'NONE')
    split_mode = params.get('split_mode',      'AUTO')
    bevel_w    = params.get('bevel_width',      0.0)

    rng = random.Random(seed)  # noqa: F841

    # ── Protrusion depths — scale with wall thickness ────────────────────────
    # This ensures nothing protrudes more than the wall is thick
    p_pillar = max(t * 0.8, 2.5)   # plinth, cornice, pilasters, buttresses
    p_sill   = p_pillar + 1.0       # window sill (slightly past structural layer)
    p_frame  = max(t * 0.4, 1.2)   # raised arch frame

    # ── Element widths — scale with wall thickness ───────────────────────────
    butt_w = max(t * 4.0, 12.0)    # end buttresses: wide and structural
    pil_w  = max(t * 2.5,  8.0)    # internal pilasters

    # ── Vertical zones ───────────────────────────────────────────────────────
    plinth_h   = max(min(h * 0.07, 8.0), 5.0)
    cornice_h  = max(min(h * 0.05, 6.0), 4.0)
    win_zone_h = h - plinth_h - cornice_h
    win_bottom = plinth_h

    # ── Main wall slab (Z = 0 → h) ──────────────────────────────────────────
    wall = create_box_object(w, h, t, location=(0, 0, 0), name="Wall_Segment")

    # ── Plinth + cornice bands ───────────────────────────────────────────────
    if detail >= 1:
        _build_band(wall, w, plinth_h,  t, p_pillar, z=0,             name="_plinth")
        _build_band(wall, w, cornice_h, t, p_pillar, z=h - cornice_h, name="_cornice")

    # ── Pillar–window rhythm ─────────────────────────────────────────────────
    win_positions = []
    if win_count > 0 and win_zone_h > 10.0:
        bay_w      = w / win_count
        win_xs     = [-w / 2 + (k + 0.5) * bay_w for k in range(win_count)]
        int_pil_xs = [-w / 2 + k * bay_w          for k in range(1, win_count)]

        if gothic >= 1 and detail >= 1:
            _build_end_buttresses(wall, w, h, t, butt_w, p_pillar)

        if gothic >= 1 and detail >= 1 and int_pil_xs:
            _build_pilasters(wall, int_pil_xs, pil_w, win_zone_h, t, win_bottom, p_pillar)

        win_positions = _build_windows(
            wall, win_xs, bay_w, pil_w, win_zone_h, win_bottom,
            t, gothic, detail, p_pillar, p_sill, p_frame
        )

    elif gothic >= 1 and detail >= 1:
        _build_end_buttresses(wall, w, h, t, butt_w, p_pillar)

    # ── Skulls in spandrel above arches ─────────────────────────────────────
    if gothic >= 3 and detail >= 2 and win_positions:
        _build_skulls(wall, win_positions, h, cornice_h, t)

    # ── Surface texture ──────────────────────────────────────────────────────
    if detail >= 3:
        add_stone_block_lines(wall, block_height=8.0, block_width=12.0,
                              line_width=0.6, line_depth=0.4)
    elif detail >= 1:
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


# ── Shared helper ────────────────────────────────────────────────────────────

def _loc_xfm(obj):
    """Bake the object's location offset into its mesh data."""
    bpy.context.view_layer.objects.active = obj
    obj.select_set(True)
    bpy.ops.object.transform_apply(location=True)


# ── Horizontal bands (plinth / cornice) ─────────────────────────────────────

def _build_band(wall, w, band_h, t, protrude, z, name):
    """
    Horizontal slab flush with wall back (Y = +t/2), protruding `protrude` mm
    beyond the wall front face (Y = −t/2).

    Y formula:  depth = t + protrude,  loc_y = −protrude / 2
    """
    band = create_box_object(
        w, band_h, t + protrude,
        location=(0, -protrude / 2, z), name=name
    )
    boolean_union(wall, band)


# ── End buttresses ───────────────────────────────────────────────────────────

def _build_end_buttresses(wall, w, h, t, butt_w, p_pillar):
    """
    Wide stepped buttresses at both wall ends.
    1 mm deeper than internal pilasters for a structural, load-bearing look.
    Span nearly full wall height so they visually anchor plinth and cornice.
    """
    extra    = 1.0
    protrude = p_pillar + extra
    butt_d   = t + protrude
    loc_y    = -protrude / 2
    butt_h   = h * 0.92

    for px in (-w / 2 + butt_w / 2, w / 2 - butt_w / 2):
        butt = create_buttress(butt_w, butt_h, butt_d, taper=0.55, name="_butt")
        butt.location = Vector((px, loc_y, 0))
        _loc_xfm(butt)
        boolean_union(wall, butt)


# ── Internal pilasters ───────────────────────────────────────────────────────

def _build_pilasters(wall, pil_xs, pil_w, pil_h, t, z_bottom, p_pillar):
    """
    Flat pilasters at internal bay boundaries (window edges).
    Same protrusion as plinth / cornice for visual continuity.
    """
    pil_d = t + p_pillar
    loc_y = -p_pillar / 2
    for i, px in enumerate(pil_xs):
        pil = create_pilaster(pil_w, pil_h, pil_d, name=f"_pil_{i}")
        pil.location = Vector((px, loc_y, z_bottom))
        _loc_xfm(pil)
        boolean_union(wall, pil)


# ── Windows ──────────────────────────────────────────────────────────────────

def _build_windows(wall, win_xs, bay_w, pil_w, win_zone_h, win_bottom,
                   t, gothic, detail, p_pillar, p_sill, p_frame):
    """
    Cut lancet arch openings and add frames + sills.
    Returns list of (cx, win_bottom_z, arch_h) tuples.

    Arch fills ~85% of window zone; remaining ~15% (5–12 mm) = spandrel
    above the arch, reserved for skull reliefs.
    """
    spandrel_h = max(min(win_zone_h * 0.15, 12.0), 5.0)
    arch_h     = win_zone_h - spandrel_h

    margin = 2.0
    win_w  = min(bay_w - pil_w - 2 * margin, arch_h * 0.33)
    win_w  = max(win_w, 5.0)

    segments  = max(8, gothic * 4)
    positions = []

    for i, cx in enumerate(win_xs):

        # ── Arch cutter ───────────────────────────────────────────────────
        if gothic >= 1:
            cutter = create_gothic_arch_cutter(
                win_w, arch_h, t + 2.0,
                segments=segments, name=f"_win_cut_{i}"
            )
        else:
            cutter = create_box_object(
                win_w, arch_h, t + 2.0,
                location=(0, 0, 0), name=f"_win_cut_{i}"
            )
        cutter.location = Vector((cx, 0, win_bottom))
        _loc_xfm(cutter)
        boolean_difference(wall, cutter)
        positions.append((cx, win_bottom, arch_h))

        # ── Raised arch frame ─────────────────────────────────────────────
        if gothic >= 2 and detail >= 2:
            frame_d = p_frame + 0.5       # 0.5 mm overlap into wall
            frame   = create_arch_frame(
                win_w, arch_h,
                depth=frame_d, frame_thickness=1.5,
                segments=segments, name=f"_frame_{i}"
            )
            # Back 0.5 mm inside wall front → protrudes p_frame forward
            frame.location = Vector((cx, -(t / 2 + p_frame / 2 - 0.25), win_bottom))
            _loc_xfm(frame)
            boolean_union(wall, frame)

        # ── Window sill ───────────────────────────────────────────────────
        if gothic >= 1 and detail >= 2:
            sill_w = win_w + 4.0          # only slightly wider than opening
            sill_h = 2.0                  # low ledge, not a shelf
            sill   = create_box_object(
                sill_w, sill_h, t + p_sill,
                location=(cx, -p_sill / 2, win_bottom - sill_h),
                name=f"_sill_{i}"
            )
            boolean_union(wall, sill)

    return positions


# ── Skull reliefs ─────────────────────────────────────────────────────────────

def _build_skulls(wall, win_positions, h, cornice_h, t):
    """Skull reliefs centred in the spandrel above each arch."""
    for cx, win_btm, arch_h in win_positions:
        spandrel_z     = win_btm + arch_h
        spandrel_avail = h - cornice_h - spandrel_z
        if spandrel_avail < 5.0:
            continue

        skull_w = max(5.0, min(10.0, spandrel_avail * 0.8))
        skull_h = min(skull_w * 1.15, spandrel_avail - 1.0)
        if skull_h < 4.0:
            continue

        skull_z = spandrel_z + (spandrel_avail - skull_h) * 0.4
        skull   = create_skull_relief(width=skull_w, height=skull_h,
                                      depth=1.2, name="_skull")
        skull.location = Vector((cx, -(t / 2 + 0.3), skull_z))
        _loc_xfm(skull)
        boolean_union(wall, skull)


# ── Rivets ────────────────────────────────────────────────────────────────────

def _add_wall_rivets(wall, w, h, t):
    """Rows of rivets at base and top band for industrial gothic flavour."""
    y_pos = -(t / 2) - 0.1
    positions = []
    for rx in range(-int(w / 2) + 8, int(w / 2) - 5, 12):
        positions.append(Vector((rx, y_pos, 6.0)))
        positions.append(Vector((rx, y_pos, h - 6.0)))
    add_rivets(wall, positions, rivet_radius=0.8, rivet_depth=0.8)


# ── Bevel ─────────────────────────────────────────────────────────────────────

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
