# Copyright (c) 2019 Elie Michel
#
# This file is part of LilySurfaceScrapper, a Blender add-on to import
# materials from a single URL. It is released under the terms of the GPLv3
# license. See the LICENSE.md file for the full text.

import bpy
from bpy_extras.node_shader_utils import PrincipledBSDFWrapper
from .MaterialData import MaterialData
from .cycles_utils import getCyclesImage, autoAlignNodes

class CyclesMaterialData(MaterialData):
    # Translate our internal map names into cycles principled inputs
    input_tr = {
        'baseColor': 'Base Color',
        'normal': 'Normal',
        'roughness': 'Roughness',
        'metallic': 'Metallic',
        'specular': 'Specular',
        'opacity': 'Alpha',
        'emission': 'Emission',
        'height': '<custom>',
        'ambientOcclusion': '<custom>', # https://github.com/KhronosGroup/glTF-Blender-IO/issues/123
        'glossiness': '<custom>',
    }

    def loadImages(self):
        """This is not needed by createMaterial, but is called when
        create_material is false to load images anyway"""
        for map_name, img in self.maps.items():
            if img is None or map_name.split("_")[0] not in __class__.input_tr:
                continue
            getCyclesImage(img)

    def createMaterial(self):
        mat = bpy.data.materials.new(name=self.name)
        mat.use_nodes = True
        nodes = mat.node_tree.nodes
        links = mat.node_tree.links
        principled_mat = PrincipledBSDFWrapper(mat, is_readonly=False)
        principled = principled_mat.node_principled_bsdf
        mat_output = principled_mat.node_out
        principled_mat.roughness = 1.0
        front = {}
        back = {}

        # Create all of the texture nodes
        for map_name, img in self.maps.items():
            if img is None or map_name.split("_")[0] not in __class__.input_tr:
                continue
            
            texture_node = nodes.new(type="ShaderNodeTexImage")
            if "_back" in map_name:
                map_name = map_name[:-5] # remove "_back"
                back[map_name] = texture_node
            else:
                front[map_name] = texture_node
            
            texture_node.image = getCyclesImage(img)
            texture_node.image.colorspace_settings.name = "sRGB" if map_name == "baseColor" else "Non-Color"
            if hasattr(texture_node, "color_space"):
                texture_node.color_space = "COLOR" if map_name == "baseColor" else "NONE"
            if map_name == "opacity":
                mat.blend_method = 'BLEND'
        
        if not back: # If there is no item in the back dictionary
            (links.new(node.outputs["Color"], principled.inputs[__class__.input_tr[name]]) for name, node in front.items()) # Wire up all of the nodes traditionally
        else:
            geometry_node = nodes.new("ShaderNodeNewGeometry")
            def setup(name, front, back, mix):
                links.new(geometry_node.outputs["Backfacing"], mix.inputs[0])
                links.new(front.outputs["Color"], mix.inputs[1])
                links.new(back.outputs["Color"], mix.inputs[2])
                links.new(mix.outputs["Color"], principled.inputs[__class__.input_tr[name]])
            (setup(name, node, back[name], nodes.new(type="ShaderNodeMixRGB")) for name, node in front.items() if back.get(name))

        autoAlignNodes(mat_output)

        return mat
