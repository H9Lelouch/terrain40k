"""
Wall Segment generator for Warhammer 40K imperial ruins.
Based on Sector Imperialis architecture (GW standard: 127 mm / 5").

Vertical zones (Z = 0 at ground):
    plinth_h  (5–8 mm)   foundation band — protrudes _P_PILLAR from wall face
    win_zone  (bulk)     [ Buttress | Window | Pilaster | Window | Buttress ]
    spandrel  (~10 mm)   solid zone above arch; skulls placed here
    cornice_h (4–6 mm)   top molding band — same protrusion as plinth

Pillar rhythm (N windows → N+1 vertical elements):
    - End buttresses at X = ±(w/2 − butt_w/2)  [deeper, structural]
    - Internal pilasters at bay boundaries X = −w/2 + k·bay_w  (k = 1…N−1)
    - Windows centered in each bay at X = −w/2 + (k + ½)·bay_w

Protrusion from wall front face (Y = −t/2, negative = forward):
    pillar / buttress / plinth / cornice : 5.0 mm  (structural)
    window sill                          : 6.0 mm  (ledge, past structural)
    window arch frame                    : 2.0 mm  (decorative ring)
    wall surface                         : 0.0 mm  (baseline)

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

# ── Protrusion constants (mm beyond wall front face) ─────────────────────────
_P_PILLAR = 5.0   # pilasters, buttresses, plinth, cornice
_P_SILL   = 6.0   # window sills (past structural layer)
_P_FRAME  = 2.0   # raised arch frame


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

    rng = random.Random(seed)  # noqa: F841  (available for future stochastic details)

    # ── Vertical zones ───────────────────────────────────────────────────────
    plinth_h   = max(min(h * 0.07, 8.0), 5.0)
    cornice_h  = max(min(h * 0.05, 6.0), 4.0)
    win_zone_h = h - plinth_h - cornice_h
    win_bottom = plinth_h   # Z where window zone starts

    # ── Main wall slab (Z = 0 → h) ──────────────────────────────────────────
    wall = create_box_object(w, h, t, location=(0, 0, 0), name="Wall_Segment")

    # ── Plinth + cornice bands ───────────────────────────────────────────────
    if detail >= 1:
        _build_band(wall, w, plinth_h,  t, _P_PILLAR, z=0,             name="_plinth")
        _build_band(wall, w, cornice_h, t, _P_PILLAR, z=h - cornice_h, name="_cornice")

    # ── Pillar–window rhythm ─────────────────────────────────────────────────
    win_positions = []   # (cx, win_bottom_z, arch_h)
    if win_count > 0 and win_zone_h > 10.0:
        bay_w      = w / win_count
        win_xs     = [-w / 2 + (k + 0.5) * bay_w for k in range(win_count)]
        int_pil_xs = [-w / 2 + k * bay_w          for k in range(1, win_count)]
        pil_w      = max(t * 1.2, 6.0)

        # End buttresses at wall edges
        if gothic >= 1 and detail >= 1:
            _build_end_buttresses(wall, w, h, t)

        # Internal pilasters at bay boundaries between windows
        if gothic >= 1 and detail >= 1 and int_pil_xs:
            _build_pilasters(wall, int_pil_xs, pil_w, win_zone_h, t, win_bottom)

        # Window openings (arch cutter) + frames + sills
        win_positions = _build_windows(
            wall, win_xs, bay_w, pil_w, win_zone_h, win_bottom, t, gothic, detail
        )

    elif gothic >= 1 and detail >= 1:
        # No windows but still dress the ends
        _build_end_buttresses(wall, w, h, t)

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


# ── Shared transform helper ──────────────────────────────────────────────────

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
        → back  at Y = +t/2
        → front at Y = −(t/2 + protrude)
    """
    band = create_box_object(
        w, band_h, t + protrude,
        location=(0, -protrude / 2, z), name=name
    )
    boolean_union(wall, band)


# ── End buttresses ───────────────────────────────────────────────────────────

def _build_end_buttresses(wall, w, h, t):
    """
    Stepped, tapered buttresses at both wall ends.
    Deeper than internal pilasters for a structural, load-bearing look.
    Span nearly full wall height, overlapping plinth and cornice zones.
    """
    butt_w = max(t * 2.0, 8.0)
    butt_h = h * 0.92
    extra  = 2.0                       # extra protrusion vs. pilasters
    protrude = _P_PILLAR + extra       # 7 mm total
    butt_d   = t + protrude
    loc_y    = -protrude / 2

    for px in (-w / 2 + butt_w / 2, w / 2 - butt_w / 2):
        butt = create_buttress(butt_w, butt_h, butt_d, taper=0.55, name="_butt")
        butt.location = Vector((px, loc_y, 0))
        _loc_xfm(butt)
        boolean_union(wall, butt)


# ── Internal pilasters ───────────────────────────────────────────────────────

def _build_pilasters(wall, pil_xs, pil_w, pil_h, t, z_bottom):
    """
    Thin pilasters at internal bay boundaries (window edges).
    Same protrusion depth as plinth / cornice for visual continuity.
    Z range: z_bottom → z_bottom + pil_h  (window zone only).
    """
    pil_d = t + _P_PILLAR
    loc_y = -_P_PILLAR / 2
    for i, px in enumerate(pil_xs):
        pil = create_pilaster(pil_w, pil_h, pil_d, name=f"_pil_{i}")
        pil.location = Vector((px, loc_y, z_bottom))
        _loc_xfm(pil)
        boolean_union(wall, pil)


# ── Windows ──────────────────────────────────────────────────────────────────

def _build_windows(wall, win_xs, bay_w, pil_w, win_zone_h, win_bottom,
                   t, gothic, detail):
    """
    Cut lancet arch openings and optionally add raised frames + sills.

    Arch height:
        Fills ~85 % of the window zone; the remaining ~15 % (capped to 5–12 mm)
        becomes the spandrel — a solid band above the arch for skull reliefs.

    Window width:
        Constrained by bay width minus pilaster width and side margins,
        then further constrained by the lancet ratio (w:h ≤ 1:3).

    Returns list of (cx, win_bottom_z, arch_h) for each window.
    """
    # Spandrel above arch: between 5 mm and 12 mm
    spandrel_h = max(min(win_zone_h * 0.15, 12.0), 5.0)
    arch_h     = win_zone_h - spandrel_h

    # Lancet width: narrowest of bay-minus-pillars or 1:3 ratio
    margin = 2.0
    win_w  = min(bay_w - pil_w - 2 * margin, arch_h * 0.33)
    win_w  = max(win_w, 5.0)

    segments  = max(8, gothic * 4)
    positions = []

    for i, cx in enumerate(win_xs):

        # ── Arch cutter (removes wall material) ──────────────────────────
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
        # Arch profile starts at Z = 0; position its bottom at win_bottom
        cutter.location = Vector((cx, 0, win_bottom))
        _loc_xfm(cutter)
        boolean_difference(wall, cutter)
        positions.append((cx, win_bottom, arch_h))

        # ── Raised arch frame (decorative border, protrudes _P_FRAME) ────
        if gothic >= 2 and detail >= 2:
            frame_d = _P_FRAME + 0.5   # 0.5 mm overlap into wall for clean boolean
            frame   = create_arch_frame(
                win_w, arch_h,
                depth=frame_d, frame_thickness=1.5,
                segments=segments, name=f"_frame_{i}"
            )
            # extrude_profile_to_solid centers frame at Y = 0.
            # Target: back face 0.5 mm inside wall front face, front protrudes _P_FRAME.
            #   back  = loc_y + frame_d/2 = -(t/2 - 0.5)
            #   → loc_y = -(t/2 + _P_FRAME/2 - 0.25)
            frame.location = Vector((cx, -(t / 2 + _P_FRAME / 2 - 0.25), win_bottom))
            _loc_xfm(frame)
            boolean_union(wall, frame)

        # ── Window sill (ledge below arch, protrudes _P_SILL) ────────────
        if gothic >= 1 and detail >= 2:
            sill_w = win_w + pil_w * 0.5   # slightly wider than opening
            sill_h = 3.0
            sill   = create_box_object(
                sill_w, sill_h, t + _P_SILL,
                location=(cx, -_P_SILL / 2, win_bottom - sill_h),
                name=f"_sill_{i}"
            )
            boolean_union(wall, sill)

    return positions


# ── Skull reliefs ─────────────────────────────────────────────────────────────

def _build_skulls(wall, win_positions, h, cornice_h, t):
    """
    Imperial skull reliefs centred in the spandrel above each arch.
    Spandrel = zone between arch top and cornice bottom.
    Skulls only placed when spandrel >= 5 mm; sized to fit.
    """
    for cx, win_btm, arch_h in win_positions:
        spandrel_z   = win_btm + arch_h
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
