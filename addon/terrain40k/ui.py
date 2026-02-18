"""
UI Panel for terrain40k addon.
Sidebar panel in the N-key menu under category "40K Terrain".
"""

import bpy


class TERRAIN40K_PT_main_panel(bpy.types.Panel):
    bl_label = "40K Terrain Generator"
    bl_idname = "TERRAIN40K_PT_main_panel"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "40K Terrain"

    def draw(self, context):
        layout = self.layout
        props = context.scene.terrain40k

        # Module type
        layout.prop(props, "module_type")
        layout.separator()

        # Dimensions
        box = layout.box()
        box.label(text="Dimensions (mm)", icon='ORIENTATION_LOCAL')
        box.prop(props, "width")
        box.prop(props, "height")
        if props.module_type in ('CORNER', 'PILLAR'):
            box.prop(props, "depth")
        box.prop(props, "wall_thickness")

        # Style
        box = layout.box()
        box.label(text="Style", icon='SCULPTMODE_HLT')
        box.prop(props, "window_density")
        box.prop(props, "detail_level")
        box.prop(props, "gothic_style")
        box.prop(props, "damage_state")
        if props.damage_state != 'CLEAN':
            box.prop(props, "damage_intensity", slider=True)
        box.prop(props, "bevel_width")

        # Seed
        box = layout.box()
        box.label(text="Randomization", icon='PARTICLE_DATA')
        row = box.row(align=True)
        row.prop(props, "random_seed")
        row.operator("terrain40k.randomize_seed", text="", icon='FILE_REFRESH')

        # Connectors
        box = layout.box()
        box.label(text="Connectors", icon='LINKED')
        box.prop(props, "connector_type")
        if props.connector_type in ('PINS', 'BOTH'):
            box.prop(props, "pin_tolerance")
        if props.connector_type in ('MAGNETS', 'BOTH'):
            box.prop(props, "magnet_diameter")
            box.prop(props, "magnet_height")

        # Print
        box = layout.box()
        box.label(text="3D Print", icon='MOD_SOLIDIFY')
        box.prop(props, "split_mode")

        layout.separator()
        # Generate button
        row = layout.row(align=True)
        row.scale_y = 2.0
        row.operator("terrain40k.generate", text="Generate Module", icon='MESH_CUBE')


def register():
    bpy.utils.register_class(TERRAIN40K_PT_main_panel)


def unregister():
    bpy.utils.unregister_class(TERRAIN40K_PT_main_panel)
