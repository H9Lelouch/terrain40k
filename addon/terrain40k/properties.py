"""
Addon properties for terrain40k.
All user-configurable parameters for terrain generation.
"""

import bpy
from bpy.props import (
    BoolProperty,
    EnumProperty,
    FloatProperty,
    IntProperty,
    StringProperty,
)


class Terrain40KProperties(bpy.types.PropertyGroup):
    module_type: EnumProperty(
        name="Module Type",
        items=[
            ('WALL', "Wall Segment", "Straight wall with windows and buttresses"),
            ('CORNER', "Corner Ruin", "L-shaped corner ruin piece"),
            ('PILLAR', "Pillar Cluster", "Group of gothic pillars on base"),
        ],
        default='WALL',
        description="Type of terrain module to generate",
    )
    width: FloatProperty(
        name="Width (mm)",
        default=100.0,
        min=20.0, max=500.0,
        step=100,
        precision=1,
        subtype='NONE',
        description="Module width in mm",
    )
    height: FloatProperty(
        name="Height (mm)",
        default=80.0,
        min=15.0, max=300.0,
        step=100,
        precision=1,
        subtype='NONE',
        description="Module height in mm",
    )
    depth: FloatProperty(
        name="Depth (mm)",
        default=80.0,
        min=15.0, max=300.0,
        step=100,
        precision=1,
        subtype='NONE',
        description="Module depth (for corner/pillar cluster) in mm",
    )
    wall_thickness: FloatProperty(
        name="Wall Thickness",
        default=5.0,
        min=1.6, max=10.0,
        step=10,
        precision=1,
        description="Wall thickness in mm (min 1.6 for FDM)",
    )
    floor_count: IntProperty(
        name="Floor Count",
        default=1,
        min=1, max=4,
        description="Number of floors / levels",
    )
    wall_style: bpy.props.EnumProperty(
        name="Wall Style",
        items=[
            ('VONTRAGG', "Vontragg Cathedral",
             "Fine stonework, very slender lancet arches (gothic_wall ref)"),
            ('VOY',      "Grimdark Ruins",
             "Medium blockwork, wide lancets, coarser masonry (VoyMakesMinis ref)"),
            ('SIMPLE',   "Simple Modular",
             "Coarse blocks, wider arches, plain profile (root set ref)"),
        ],
        default='VOY',
        description="Reference style preset — sets window ratio, arch smoothness and block scale",
    )
    window_density: IntProperty(
        name="Window Count",
        default=2,
        min=0, max=6,
        description="Number of windows per wall segment",
    )
    detail_level: IntProperty(
        name="Detail Level",
        default=1,
        min=0, max=3,
        description="0=minimal, 1=standard, 2=detailed, 3=max",
    )
    gothic_style: IntProperty(
        name="Gothic Style",
        default=1,
        min=0, max=3,
        description="0=plain, 1=basic arches, 2=buttresses+sills, 3=full gothic",
    )
    mortar_width: FloatProperty(
        name="Mortar Width",
        default=1.0,
        min=0.0, max=3.0,
        step=5,
        precision=1,
        description="Breite der Mauerwerk-Fugen in mm (0 = keine Fugen)",
    )
    damage_state: EnumProperty(
        name="Damage State",
        items=[
            ('CLEAN',   "Clean",   "Pristine – no structural damage"),
            ('DAMAGED', "Damaged", "Cracks, chips, bullet holes, mini-breaks"),
            ('RUINED',  "Ruined",  "Large holes, breakouts, missing segments"),
            ('HALF',    "Half",    "30–60 % gone – collapse break"),
        ],
        default='CLEAN',
        description="Damage level preset",
    )
    damage_intensity: FloatProperty(
        name="Damage Intensity",
        default=0.3,
        min=0.0, max=1.0,
        step=5,
        precision=2,
        description="0=pristine, 1=heavily destroyed",
    )
    random_seed: IntProperty(
        name="Random Seed",
        default=42,
        min=0, max=99999,
        description="Seed for procedural variation",
    )
    connector_type: EnumProperty(
        name="Connectors",
        items=[
            ('NONE', "None", "No connectors"),
            ('PINS', "Pins", "Pin/hole connectors"),
            ('MAGNETS', "Magnets", "Magnet seat pockets"),
            ('BOTH', "Both", "Pins and magnet seats"),
        ],
        default='NONE',
        description="Type of modular connectors to add",
    )
    split_mode: EnumProperty(
        name="Split for Print",
        items=[
            ('AUTO', "Auto", "Auto-split if exceeds A1 bed (256mm)"),
            ('OFF', "Off", "No splitting"),
        ],
        default='AUTO',
        description="Auto-split large pieces for BambuLab A1 print bed",
    )
    bevel_width: FloatProperty(
        name="Bevel Width",
        default=0.0,
        min=0.0, max=3.0,
        step=1,
        precision=1,
        description="Edge bevel in mm (0=off). Only if printable.",
    )
    pin_tolerance: FloatProperty(
        name="Pin Tolerance",
        default=0.25,
        min=0.1, max=0.5,
        step=1,
        precision=2,
        description="Clearance per side for pin connectors (mm)",
    )
    magnet_diameter: FloatProperty(
        name="Magnet Diameter",
        default=3.0,
        min=2.0, max=6.0,
        step=5,
        precision=1,
        description="Magnet diameter in mm (default: 3 mm small magnets)",
    )
    magnet_height: FloatProperty(
        name="Magnet Height",
        default=2.0,
        min=1.0, max=5.0,
        step=10,
        precision=1,
        description="Magnet height in mm (common: 2)",
    )
    auto_clear: BoolProperty(
        name="Clear on Generate",
        default=True,
        description="Delete previously generated terrain objects before generating a new one",
    )


def register():
    bpy.utils.register_class(Terrain40KProperties)
    bpy.types.Scene.terrain40k = bpy.props.PointerProperty(type=Terrain40KProperties)


def unregister():
    del bpy.types.Scene.terrain40k
    bpy.utils.unregister_class(Terrain40KProperties)
