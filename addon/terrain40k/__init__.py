"""
terrain40k - Warhammer 40K Terrain Generator for Blender

Procedurally generates modular imperial/gothic ruin terrain
optimized for FDM 3D printing on BambuLab A1.

All meshes are manifold, boolean-safe, and watertight.
1 Blender Unit = 1 mm in this addon's convention.
"""

bl_info = {
    "name": "40K Terrain Generator",
    "author": "terrain40k contributors",
    "version": (0, 1, 0),
    "blender": (4, 0, 0),
    "location": "View3D > Sidebar > 40K Terrain",
    "description": "Procedural Warhammer 40K gothic ruin terrain for 3D printing",
    "category": "Mesh",
    "doc_url": "",
    "tracker_url": "",
}

from . import properties
from . import operators
from . import ui


def register():
    properties.register()
    operators.register()
    ui.register()


def unregister():
    ui.unregister()
    operators.unregister()
    properties.unregister()


if __name__ == "__main__":
    register()
