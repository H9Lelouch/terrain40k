"""
Operators for terrain40k addon.
"""

import bpy
from .generator.wall_segment import generate_wall_segment
from .generator.corner_ruin import generate_corner_ruin
from .generator.pillar_cluster import generate_pillar_cluster


class TERRAIN40K_OT_generate(bpy.types.Operator):
    """Generate a 40K terrain module based on current settings"""
    bl_idname = "terrain40k.generate"
    bl_label = "Generate Module"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        props = context.scene.terrain40k
        params = {
            'width': props.width,
            'height': props.height,
            'depth': props.depth,
            'wall_thickness': props.wall_thickness,
            'floor_count': props.floor_count,
            'window_density': props.window_density,
            'detail_level': props.detail_level,
            'gothic_style': props.gothic_style,
            'damage_intensity': props.damage_intensity,
            'seed': props.random_seed,
            'connector_type': props.connector_type,
            'split_mode': props.split_mode,
            'bevel_width': props.bevel_width,
            'pin_tolerance': props.pin_tolerance,
            'magnet_diameter': props.magnet_diameter,
            'magnet_height': props.magnet_height,
        }

        generators = {
            'WALL': generate_wall_segment,
            'CORNER': generate_corner_ruin,
            'PILLAR': generate_pillar_cluster,
        }

        gen_func = generators.get(props.module_type)
        if gen_func is None:
            self.report({'ERROR'}, f"Unknown module type: {props.module_type}")
            return {'CANCELLED'}

        try:
            results = gen_func(params)
            count = len(results) if results else 0
            self.report({'INFO'},
                        f"Generated {count} object(s): {props.module_type}")
        except Exception as e:
            self.report({'ERROR'}, f"Generation failed: {e}")
            import traceback
            traceback.print_exc()
            return {'CANCELLED'}

        return {'FINISHED'}


class TERRAIN40K_OT_randomize_seed(bpy.types.Operator):
    """Randomize the seed and regenerate"""
    bl_idname = "terrain40k.randomize_seed"
    bl_label = "Randomize Seed"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        import random
        context.scene.terrain40k.random_seed = random.randint(0, 99999)
        return {'FINISHED'}


def register():
    bpy.utils.register_class(TERRAIN40K_OT_generate)
    bpy.utils.register_class(TERRAIN40K_OT_randomize_seed)


def unregister():
    bpy.utils.unregister_class(TERRAIN40K_OT_randomize_seed)
    bpy.utils.unregister_class(TERRAIN40K_OT_generate)
