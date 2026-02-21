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
    add_stone_block_lines,
    add_rivets,
)
from .connectors import add_ground_wall_connectors
from .damage import apply_damage
from .splitter import should_split, split_for_print


# ── Style presets (calibrated from binary-STL reference measurements) ────────
# Each preset sets: window arch ratio, arch smoothness, stone block scale,
# plinth height factor, cornice height factor.
#
# VONTRAGG — cathedral-upper-wall-and-windows-wh40k (47×5.7×79 mm)
#   Fine stonework, very slender lancets (H/W ≈ 4.5:1), smooth arcs.
# VOY — VoyMakesMinis grimdark-gothic-ruins (48.5×13.9×122 mm)
#   Medium blockwork, wider lancets (H/W ≈ 3.8:1), standard.
# SIMPLE — root modular set (Wall_-_Solid 45×13.8×70 mm)
#   Coarse blocks, practical arch width, minimal ornament.
STYLE_PRESETS = {
    'VONTRAGG': {
        'win_ratio':       0.22,   # lancet H/W ≈ 4.5:1
        'arch_seg_base':   16,     # smooth arc (cathedral quality)
        'block_scale':     0.80,   # finer stonework
        'plinth_factor':   0.12,   # prominent base (9.6 mm at h=80)
        'cornice_factor':  0.09,   # generous cornice (7.2 mm at h=80)
    },
    'VOY': {
        'win_ratio':       0.26,   # H/W ≈ 3.8:1
        'arch_seg_base':   12,
        'block_scale':     1.00,
        'plinth_factor':   0.11,
        'cornice_factor':  0.08,
    },
    'SIMPLE': {
        'win_ratio':       0.32,   # wider, less ornate
        'arch_seg_base':   8,      # angular — industrial feel
        'block_scale':     1.25,   # coarse blockwork
        'plinth_factor':   0.09,
        'cornice_factor':  0.07,
    },
}


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
    t          = params.get('wall_thickness',   5.0)
    win_count  = params.get('window_density',    2)
    detail     = params.get('detail_level',      1)
    gothic     = params.get('gothic_style',      1)
    damage     = params.get('damage_intensity', 0.3)
    seed       = params.get('seed',             42)
    connector  = params.get('connector_type',  'NONE')
    split_mode = params.get('split_mode',      'AUTO')
    bevel_w    = params.get('bevel_width',      0.0)
    mortar_w   = params.get('mortar_width',     1.0)

    # ── Style preset ─────────────────────────────────────────────────────────
    sp             = STYLE_PRESETS.get(params.get('wall_style', 'VOY'), STYLE_PRESETS['VOY'])
    win_ratio      = sp['win_ratio']
    arch_seg_base  = sp['arch_seg_base']
    block_scale    = sp['block_scale']
    plinth_factor  = sp['plinth_factor']
    cornice_factor = sp['cornice_factor']

    rng = random.Random(seed)  # noqa: F841

    # ── Protrusion depths — scale with wall thickness ────────────────────────
    # This ensures nothing protrudes more than the wall is thick
    p_pillar = max(t * 2.2,  7.0)   # cornice, pilasters, buttresses — ref: 2.09×t
    p_plinth = max(t * 2.0,  7.0)   # base plinth — wider for freestanding stability
    p_sill   = p_pillar + 1.5       # window sill (slightly past structural layer)
    p_frame  = max(t * 0.6,  1.8)   # raised arch frame

    # ── Element widths — scale with wall thickness ───────────────────────────
    butt_w = max(7.0, t * 1.5)      # end buttresses: narrow fin face (ref: 4–7.4 mm)
    pil_w  = max(8.0, t * 2.0)     # internal pilasters (ref: 8–12 mm)

    # ── Vertical zones ───────────────────────────────────────────────────────
    plinth_h   = max(min(h * plinth_factor,  10.0), 7.0)
    cornice_h  = max(min(h * cornice_factor,  7.0), 5.0)
    win_zone_h = h - plinth_h - cornice_h
    win_bottom = plinth_h

    # ── Main wall slab (Z = 0 → h) ──────────────────────────────────────────
    wall = create_box_object(w, h, t, location=(0, 0, 0), name="Wall_Segment")

    # ── Pillar–window rhythm: compute layout ─────────────────────────────────
    # Bay geometry must be known before any boolean ops so windows can be
    # cut into the CLEAN slab. Cutting on a pristine mesh guarantees the
    # boolean solver succeeds; cutting after 20+ unions often fails silently.
    win_positions = []
    bay_w      = w / win_count if win_count > 0 else w
    win_xs     = [-w / 2 + (k + 0.5) * bay_w for k in range(win_count)]
    int_pil_xs = [-w / 2 + k * bay_w          for k in range(1, win_count)]

    # ── CUT WINDOWS FIRST — into the clean wall slab ─────────────────────────
    if win_count > 0 and win_zone_h > 10.0:
        win_positions = _build_windows(
            wall, win_xs, bay_w, pil_w, win_zone_h, win_bottom,
            t, gothic, detail, p_pillar, p_sill, p_frame,
            win_ratio=win_ratio, arch_seg_base=arch_seg_base,
        )

    # ── Plinth + cornice bands ───────────────────────────────────────────────
    if detail >= 1:
        _build_band(wall, w, plinth_h,  t, p_plinth, z=0,             name="_plinth",  lip_at_top=True)
        _build_band(wall, w, cornice_h, t, p_pillar, z=h - cornice_h, name="_cornice", lip_at_top=False)

    # ── Rear face detailing ───────────────────────────────────────────────────
    if detail >= 1:
        _build_rear_face(wall, w, h, t, plinth_h, cornice_h,
                         win_count, win_zone_h, win_bottom)

    # ── Buttresses + pilasters ───────────────────────────────────────────────
    if win_count > 0 and win_zone_h > 10.0:
        if gothic >= 1 and detail >= 1:
            _build_end_buttresses(wall, w, h, t, butt_w, p_pillar)

        if gothic >= 1 and detail >= 1 and int_pil_xs:
            _build_pilasters(wall, int_pil_xs, pil_w, win_zone_h, t, win_bottom, p_pillar)

        # Front string courses — arch_h from first position tuple element [2]
        if detail >= 1 and win_positions:
            _build_front_stringcourses(
                wall, w, t, win_bottom, win_positions[0][2], p_pillar
            )

    elif gothic >= 1 and detail >= 1:
        _build_end_buttresses(wall, w, h, t, butt_w, p_pillar)

    # ── Spandrel fill ─────────────────────────────────────────────────────────
    if 1 <= gothic < 3 and detail >= 1 and win_positions:
        _build_spandrel_fill(wall, win_positions, h, cornice_h, t,
                             p_frame, gothic, detail)

    # ── Skulls in spandrel above arches (gothic 3 only) ──────────────────────
    if gothic >= 3 and detail >= 2 and win_positions:
        _build_skulls(wall, win_positions, h, cornice_h, t)

    # ── Mauerwerk-Fugen — unabhängig von detail_level ─────────────────────────
    # mortar_width=0 schaltet die Fugen aus; jeder Wert >0 aktiviert sie.
    # Blockgröße skaliert mit detail (mehr Detail = feineres Mauerwerk),
    # aber die Fugen erscheinen unabhängig davon.
    if mortar_w > 0.0:
        line_d   = max(0.6, mortar_w * 0.8)   # deeper groove → more shadow
        boss_d   = 0.0  # per-block bossage disabled: boolean-union of many small boxes causes interior voids
        if detail >= 3:
            bh, bw = 8.0,  12.0
        elif detail >= 2:
            bh, bw = 10.0, 16.0
        else:
            bh, bw = 13.0, 20.0
        bh = max(6.0, bh * block_scale)
        bw = max(8.0, bw * block_scale)
        add_stone_block_lines(wall,
                              block_height=bh, block_width=bw,
                              line_width=mortar_w, line_depth=line_d,
                              front_face_y=-(t / 2),
                              boss_depth=boss_d,
                              texture_depth=0.3)

    # ── Rivets ───────────────────────────────────────────────────────────────
    if detail >= 3 and t >= 2.5:
        _add_wall_rivets(wall, w, h, t)

    # ── Bevel ────────────────────────────────────────────────────────────────
    if bevel_w > 0:
        _apply_bevel(wall, bevel_w)

    # ── Damage ───────────────────────────────────────────────────────────────
    apply_damage(wall, params.get('damage_state', 'CLEAN'), damage, seed)

    # ── Connectors ───────────────────────────────────────────────────────────
    # Ground wall: female sockets on top + both side edges. No bottom connector.
    if connector != 'NONE':
        add_ground_wall_connectors(
            wall, w=w, h=h, t=t,
            magnet_diameter=params.get('magnet_diameter', 3.0),
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

def _build_band(wall, w, band_h, t, protrude, z, name, lip_at_top=True):
    """
    Horizontal band with layered masonry (Depth Pass):
      Level 0 — main slab flush with wall back (Y = +t/2), protruding `protrude` mm
      Level 2 — shadow lip: 1.5 mm strip that protrudes 0.8 mm more than the slab,
                placed at the transition edge to cast a hard horizontal shadow
      Level 1 — recessed face panel: 1.0 mm groove on the band's front face

    lip_at_top=True  → shadow ledge at top of band  (plinth → wall zone transition)
    lip_at_top=False → shadow ledge at bottom of band (cornice hangs over wall)
    """
    band = create_box_object(
        w, band_h, t + protrude,
        location=(0, -protrude / 2, z), name=name
    )
    boolean_union(wall, band)

    if band_h < 3.0:
        return

    # Sub-plinth corbel step (plinth mode only, lip_at_top=True):
    # Extra tier at the very base — wall → plinth → sub-plinth → ground.
    # Adds a third horizontal level that gives the foundation visual weight
    # and mimics the corbelled base found on all real Gothic plinths.
    if lip_at_top:
        sub_h   = min(2.0, band_h * 0.28)
        sub_ext = 2.0
        sub_p   = protrude + sub_ext
        sub = create_box_object(
            w, sub_h, t + sub_p,
            location=(0, -sub_p / 2, z), name=name + "_sub"
        )
        boolean_union(wall, sub)

        # Horizontal accent ribs — derived from Butress_Accents.stl (3-band pattern)
        if band_h >= 5.0:
            rib_h = max(0.8, band_h * 0.14)
            rib_p = protrude + 0.8
            for i in range(3):
                rz  = z + band_h * (i + 0.5) / 3 - rib_h / 2
                rib = create_box_object(
                    w, rib_h, t + rib_p,
                    location=(0, -rib_p / 2, rz),
                    name=f"{name}_rib{i}",
                )
                boolean_union(wall, rib)

    # Shadow lip (Level 2): protrudes 0.8 mm more than the band
    lip_h   = min(1.5, band_h * 0.28)
    lip_ext = 0.8
    lip_p   = protrude + lip_ext
    lip_z   = (z + band_h - lip_h) if lip_at_top else z
    lip = create_box_object(
        w, lip_h, t + lip_p,
        location=(0, -lip_p / 2, lip_z), name=name + "_lip"
    )
    boolean_union(wall, lip)

    # Recessed face panel (Level 1): 1.0 mm groove on band front face
    # Margin accounts for lip so panel never overlaps the shadow ledge
    margin_x   = max(4.0, w * 0.04)
    margin_bot = max(1.5, band_h * 0.22) + (0.0 if lip_at_top else lip_h)
    margin_top = max(1.5, band_h * 0.22) + (lip_h if lip_at_top else 0.0)
    panel_w    = w - 2 * margin_x
    panel_h    = band_h - margin_bot - margin_top
    recess_d   = 1.0
    if panel_w >= 8.0 and panel_h >= 1.5:
        front_y = -(t / 2 + protrude)
        cut_y   = front_y + recess_d / 2
        cutter  = create_box_object(
            panel_w, panel_h, recess_d + 0.4,
            location=(0, cut_y, z + margin_bot), name=name + "_recess"
        )
        boolean_difference(wall, cutter)


# ── Rear face detailing ──────────────────────────────────────────────────────

def _build_rear_face(wall, w, h, t, plinth_h, cornice_h,
                     win_count, win_zone_h, win_bottom):
    """
    Minimal rear-face detailing: horizontal bands + shallow bay recesses.
    Provides structural hinting without mirroring the front.

    Rear protrusion formula (protrude P from back face Y = +t/2):
        depth = t + P,  loc_y = +P / 2
        → back at Y = +(t/2 + P),  front flush at Y = −t/2
    """
    p_rear        = max(t * 0.25, 0.8)   # shallow — never dominates the front
    p_rear_plinth = max(t * 0.5,  1.5)   # wider at base for freestanding stability

    # ── Rear plinth band ─────────────────────────────────────────────────────
    rb = create_box_object(
        w, plinth_h, t + p_rear_plinth,
        location=(0, p_rear_plinth / 2, 0), name="_rear_plinth"
    )
    boolean_union(wall, rb)

    # ── Rear cornice band ─────────────────────────────────────────────────────
    rc = create_box_object(
        w, cornice_h, t + p_rear,
        location=(0, p_rear / 2, h - cornice_h), name="_rear_cornice"
    )
    boolean_union(wall, rc)

    # ── Bay panel recesses (only when no windows in the bay) ─────────────────
    # When windows are present the bay already has an opening; skip to avoid
    # boolean collisions between the arch hole and the rear panel cutter.
    if win_count == 0 and win_zone_h > 10.0:
        bay_w    = w
        recess_d = min(0.8, t * 0.2)
        inset_x  = max(3.0, bay_w * 0.1)
        panel_w  = bay_w - 2 * inset_x
        inset_z  = max(3.0, win_zone_h * 0.08)
        panel_h  = win_zone_h - 2 * inset_z

        if panel_w >= 5.0 and panel_h >= 5.0:
            cutter = create_box_object(
                panel_w, panel_h, recess_d * 2,
                location=(0, t / 2, win_bottom + inset_z),
                name="_rear_panel"
            )
            boolean_difference(wall, cutter)


# ── End buttresses ───────────────────────────────────────────────────────────

def _build_end_buttresses(wall, w, h, t, butt_w, p_pillar):
    """
    Three-tier stepped buttresses at both wall ends (authentic Gothic setback profile).

    Each tier is less wide and less deep than the one below, creating hard
    horizontal shadow lines at 40 % and 72 % of buttress height — the key
    visual element that distinguishes real Gothic masonry from a simple wedge.

    Tier layout:
        Tier 1 (Z:  0   → 40 %) — full width + protrusion (structural base)
        Tier 2 (Z: 40 % → 72 %) — 86 % width, 70 % protrusion
        Tier 3 (Z: 72 % → 92 %) — 72 % width, 42 % protrusion (slender top)

    Y-formula per tier: depth = t + pN, loc_y = -pN/2 → back face always at +t/2.
    """
    p1     = p_pillar + 1.0    # full protrusion (tier 1)
    p2     = p1 * 0.70         # tier 2: -30 %
    p3     = p1 * 0.42         # tier 3: -28 % more
    butt_h = h * 0.70   # ref: Butress.stl H/wall_H = 48/70 = 0.686

    h1 = butt_h * 0.40
    h2 = butt_h * 0.32
    h3 = butt_h - h1 - h2

    for px in (-w / 2 + butt_w / 2, w / 2 - butt_w / 2):
        b1 = create_box_object(
            butt_w, h1, t + p1,
            location=(px, -p1 / 2, 0), name="_butt1"
        )
        boolean_union(wall, b1)
        b2 = create_box_object(
            butt_w * 0.92, h2, t + p2,
            location=(px, -p2 / 2, h1), name="_butt2"
        )
        boolean_union(wall, b2)
        b3 = create_box_object(
            butt_w * 0.84, h3, t + p3,
            location=(px, -p3 / 2, h1 + h2), name="_butt3"
        )
        boolean_union(wall, b3)


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

        # Recessed panel on pilaster shaft face (Level 1: 1.0 mm inset)
        # Mirrors the zone proportions used inside create_pilaster
        base_h_pil = max(pil_h * 0.07, 2.0)
        cap_h_pil  = max(pil_h * 0.06, 1.5)
        shaft_h    = pil_h - base_h_pil - cap_h_pil
        pan_margin = 1.5
        pan_w      = pil_w - 2 * pan_margin
        pan_h      = shaft_h - 2 * pan_margin
        recess_d   = 1.0
        if pan_w >= 3.0 and pan_h >= 5.0:
            front_y = -(t / 2 + p_pillar)
            cut_y   = front_y + recess_d / 2
            cutter  = create_box_object(
                pan_w, pan_h, recess_d + 0.4,
                location=(px, cut_y, z_bottom + base_h_pil + pan_margin),
                name=f"_pil_panel_{i}"
            )
            boolean_difference(wall, cutter)


# ── Front-face string courses ────────────────────────────────────────────────

def _build_front_stringcourses(wall, w, t, win_bottom, arch_h, p_pillar):
    """
    Two thin projecting courses running the full wall width on the front face.

    Gothic walls read as a stack of horizontal zones; the string courses mark
    the two most important structural transitions:
      - Sill course:     at win_bottom         (base of window zone)
      - Springer course: at win_bottom + arch_h (top of arches / base of spandrel)

    They tie together buttresses, pilasters, and window frames into a continuous
    horizontal rhythm.  Protrusion = half of pilaster depth so they are clearly
    visible but subordinate to the vertical elements.

    Y-formula: depth = t + p_sc, loc_y = -p_sc / 2.
    """
    p_sc = p_pillar * 0.5
    sc_h = 1.5
    for sc_z in (win_bottom, win_bottom + arch_h):
        sc = create_box_object(
            w, sc_h, t + p_sc,
            location=(0, -p_sc / 2, sc_z), name="_front_sc"
        )
        boolean_union(wall, sc)


# ── Windows ──────────────────────────────────────────────────────────────────

def _build_windows(wall, win_xs, bay_w, pil_w, win_zone_h, win_bottom,
                   t, gothic, detail, p_pillar, p_sill, p_frame,
                   win_ratio=0.26, arch_seg_base=12):
    """
    Cut lancet arch openings and add frames + sills.
    Returns list of (cx, win_bottom_z, arch_h) tuples.

    Arch fills ~85% of window zone; remaining ~15% (5–12 mm) = spandrel
    above the arch, reserved for skull reliefs.
    """
    spandrel_h = max(min(win_zone_h * 0.15, 12.0), 5.0)
    arch_h     = win_zone_h - spandrel_h

    margin = 2.0
    win_w  = min(bay_w - pil_w - 2 * margin, arch_h * win_ratio)
    win_w  = max(win_w, 5.0)

    segments  = max(arch_seg_base, gothic * 4)
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
        positions.append((cx, win_bottom, arch_h, win_w))

        # ── Raised arch frame (window thickness / mass rule) ──────────────
        # Always applied at gothic >= 1 so every window shows a reveal frame.
        # Thinner border at gothic 1 (1.2 mm vs 1.5 mm) stays FDM-safe.
        if gothic >= 1 and detail >= 1:
            frame_thick = 1.5 if gothic >= 2 else 1.2
            frame_d     = p_frame + 0.5   # 0.5 mm overlap into wall
            frame       = create_arch_frame(
                win_w, arch_h,
                depth=frame_d, frame_thickness=frame_thick,
                segments=segments, name=f"_frame_{i}"
            )
            frame.location = Vector((cx, -(t / 2 + p_frame / 2 - 0.25), win_bottom))
            _loc_xfm(frame)
            boolean_union(wall, frame)

        # ── Hood molding / Dripstone above arch ───────────────────────────
        # 2-step "eyebrow" projecting above the arch peak.
        # Step B (upper) protrudes more → casts a hard shadow down over the
        # arch frame and reveals window mass from a 45° viewing angle.
        # Both steps are vertical faces in FDM print orientation — no overhang.
        if gothic >= 1 and detail >= 1:
            ft           = 1.5 if gothic >= 2 else 1.2  # frame thickness ref
            hood_w_a     = win_w + ft * 2 + 2.0
            hood_w_b     = hood_w_a + 1.5
            hood_p_a     = p_frame + 1.5
            hood_p_b     = p_frame + 2.2
            hood_z       = win_bottom + arch_h
            hood_a = create_box_object(
                hood_w_a, 1.2, t + hood_p_a,
                location=(cx, -hood_p_a / 2, hood_z), name=f"_hood_a_{i}"
            )
            boolean_union(wall, hood_a)
            hood_b = create_box_object(
                hood_w_b, 1.0, t + hood_p_b,
                location=(cx, -hood_p_b / 2, hood_z + 1.2), name=f"_hood_b_{i}"
            )
            boolean_union(wall, hood_b)

        # ── Window sill / ledge (≥ 0.8 mm per window-mass rule) ───────────
        if gothic >= 1 and detail >= 1:
            sill_w = win_w + 4.0
            sill_h = 2.0
            sill   = create_box_object(
                sill_w, sill_h, t + p_sill,
                location=(cx, -p_sill / 2, win_bottom - sill_h),
                name=f"_sill_{i}"
            )
            boolean_union(wall, sill)

    return positions


# ── Skull reliefs ─────────────────────────────────────────────────────────────

def _build_skulls(wall, win_positions, h, cornice_h, t):
    """
    Skull reliefs centred in the spandrel above each arch.

    create_skull_relief convention: back face at local Y = 0, protrudes in –Y.
    Place at  Y = –(t/2 – overlap)  so the back face embeds 0.5 mm inside
    the wall front face (Y = –t/2), guaranteeing a solid boolean union.
    """
    skull_overlap = 0.5        # mm the skull back face sits inside the wall
    skull_depth   = 1.8        # relief protrusion depth

    for cx, win_btm, arch_h, _win_w in win_positions:
        spandrel_z     = win_btm + arch_h
        spandrel_avail = h - cornice_h - spandrel_z
        if spandrel_avail < 5.0:
            continue

        skull_w = max(6.0, min(12.0, spandrel_avail * 0.9))
        skull_h = min(skull_w * 1.2, spandrel_avail - 1.0)
        if skull_h < 5.0:
            continue

        skull_z = spandrel_z + (spandrel_avail - skull_h) * 0.4
        skull   = create_skull_relief(width=skull_w, height=skull_h,
                                      depth=skull_depth, name="_skull")
        # back face (local Y=0) → world Y = –(t/2) + overlap (inside wall)
        skull.location = Vector((cx, -(t / 2 - skull_overlap), skull_z))
        _loc_xfm(skull)
        boolean_union(wall, skull)


# ── Spandrel fill (gothic 1–2) ────────────────────────────────────────────────

def _build_spandrel_fill(wall, win_positions, h, cornice_h, t, p_frame, gothic, detail):
    """
    Structural / decorative fill for the spandrel zone at gothic 1–2.
    (gothic >= 3 uses skull reliefs instead — handled separately.)

    Spandrels are NEVER left empty (Depth Pass rule):
      - Lintel band directly above arch (Level 2 projection)
      - Framed recessed panel filling the remaining zone (Level 1 + Level 2)
        The panel has a raised outer border and a 0.8 mm recessed interior.
    """
    for cx, win_btm, arch_h, win_w in win_positions:
        spandrel_z     = win_btm + arch_h
        spandrel_avail = h - cornice_h - spandrel_z
        if spandrel_avail < 3.0:
            continue

        # ── Lintel band (Level 2 — protrudes p_frame from wall) ──────────────
        lintel_h = min(2.0, spandrel_avail * 0.35)
        lintel_w = win_w + 3.0
        lintel   = create_box_object(
            lintel_w, lintel_h, t + p_frame,
            location=(cx, -p_frame / 2, spandrel_z),
            name="_lintel"
        )
        boolean_union(wall, lintel)

        # ── Framed recessed panel filling the remaining spandrel (always) ─────
        # Outer frame box protrudes frame_p from wall (Level 2).
        # Interior cut 0.8 mm into the frame face (Level 1).
        panel_avail = spandrel_avail - lintel_h - 0.5
        if panel_avail >= 3.0:
            panel_h  = panel_avail
            panel_w  = min(win_w + 2.0, win_w * 1.15)
            panel_z  = spandrel_z + lintel_h + 0.5
            if panel_w >= 4.0 and panel_h >= 2.5:
                frame_p   = p_frame * 0.6
                frame_box = create_box_object(
                    panel_w, panel_h, t + frame_p,
                    location=(cx, -frame_p / 2, panel_z), name="_sp_frame"
                )
                boolean_union(wall, frame_box)

                # Recessed interior (Level 1: 0.8 mm groove on frame face)
                inner_margin = 1.2
                inner_w      = panel_w - 2 * inner_margin
                inner_h      = panel_h - 2 * inner_margin
                recess_d     = 0.8
                if inner_w >= 3.0 and inner_h >= 1.5:
                    front_y = -(t / 2 + frame_p)
                    cut_y   = front_y + recess_d / 2
                    cutter  = create_box_object(
                        inner_w, inner_h, recess_d + 0.4,
                        location=(cx, cut_y, panel_z + inner_margin),
                        name="_sp_recess"
                    )
                    boolean_difference(wall, cutter)


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
