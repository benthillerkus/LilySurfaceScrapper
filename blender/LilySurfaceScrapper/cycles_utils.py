# Copyright (c) 2019 Elie Michel
#
# This file is part of LilySurfaceScrapper, a Blender add-on to import
# materials from a single URL. It is released under the terms of the GPLv3
# license. See the LICENSE.md file for the full text.

import os
import bpy
import enum
import re
import functools
from warnings import warn
from mathutils import Vector
from pathlib import Path
from typing import List, Dict, Union, Iterable, Optional, Iterator
from itertools import chain

def getCyclesImage(imgpath):
    """Avoid reloading an image that has already been loaded."""
    for img in bpy.data.images:
        if os.path.abspath(img.filepath) == os.path.abspath(imgpath):
            return img
    return bpy.data.images.load(imgpath)

def autoAlignNodes(root: bpy.types.Node):
    """Align nodes in a node tree to be more visually pleasing."""
    def makeTree(node):
        descendentCount = 0
        children : List[bpy.types.Node] = []
        for i in node.inputs:
            for l in i.links:
                subtree = makeTree(l.from_node)
                children.append(subtree)
                descendentCount += subtree[2] + 1
        return node, children, descendentCount

    tree = makeTree(root)

    def placeNodes(tree, rootLocation, xstep = 400, ystep = 170):
        # TODO The results still aren't ideal; especially texture nodes are sometimes placed completely off
        root, children, count = tree
        root.location = rootLocation
        childLoc = rootLocation + Vector((-xstep, ystep * count / 2.))
        acc = 0.25
        for child in children:
            print(child[0].name, acc)
            acc += (child[2]+1)/2.
            placeNodes(child, childLoc + Vector((0, -ystep * acc)))
            acc += (child[2]+1)/2.

    placeNodes(tree, Vector((0,0)))

class PrincipledWorldWrapper:
    """This is a wrapper similar in use to PrincipledBSDFWrapper (located in bpy_extras.node_shader_utils) but for use with worlds.

    This is required to avoid relying on node names, which depend on Blender's UI language settings
    (see issue #7)
    """

    def __init__(self, world):
        self.node_background = None
        self.node_out = None
        for n in world.node_tree.nodes:
            if self.node_background is None and n.type == "BACKGROUND":
                self.node_background = n
            elif self.node_out is None and n.type == "OUTPUT_WORLD":
                self.node_out = n

def guessColorSpaceFromExtension(img: str) -> Dict[str, str]:
    """Guess the most appropriate color space from filename extension."""
    img = img.lower()
    if img.endswith(".jpg") or img.endswith(".jpeg") or img.endswith(".png"):
        return {
            "name": "sRGB",
            "old_name": "COLOR", # mostly for backward compatibility
        }
    else:
        return {
            "name": "Linear",
            "old_name": "NONE",
        }

class appendableNodeGroups:
    """Use this as a wrapper for appendFromBlend to append one of the node groups included within node-groups.blend.

    When adding a new node group to the blend, make sure that you put
    some kind of ID-string as the label on the group input node.
    """

    BLEND_FILE = Path(__file__).parent / "node-groups.blend"

    @staticmethod
    def __isAlreadyThere(name : str, id : str) -> Optional[bpy.types.ShaderNodeTree]:
        """Test and return for node groups.
        
        Test if there is already a node group with the same ID
        as the label on the group input in the blend file. Kinda ghetto,
        but duplicates shouldn't be a problem with this approach anymore.
        """
        def f(group : bpy.types.NodeTree) -> bool:
            if "Group Input" in group.nodes:
                return group.nodes["Group Input"].label == id
            return False

        try:
            return next(filter(f, bpy.data.node_groups))
        except StopIteration:
            return None

    # TODO Refactor this to be more generic
    @staticmethod
    def randomizeTiles() -> bpy.types.ShaderNodeTree:
        """Return the Randomize Tiles node group.

        Will append it from node-groups.blend if it's
        not already in the curent file.
        """
        return appendableNodeGroups.__isAlreadyThere("Randomize Tiles", "ID-34GH89") or \
            appendFromBlend(appendableNodeGroups.BLEND_FILE, datatype = "node_groups" , name = "Randomize Tiles")["Randomize Tiles"]

def appendFromBlend(filepath: Path, name: Optional[Union[Iterable[str], str]] = None,
    datatype: Optional[str] = None, link: bool = False) -> Union[List[bpy.types.ID], bpy.types.BlendData]:
    """Append stuff from a given blend file at file path.

    You could for example append all node_groups, Object "Suzanne" and "Cube", or everything in the file.
    Already existing data in your file will not get overwritten, Blender will but a `.001`
    at the end of the appended asset in that case.

    If `name = None`, everything will be appended. Use `link = True` to link instead of appending.
    You can also specify for which datatype[1] you are looking for.

    This function is a wrapper for `BlendDataLibraries`[2], so it's not using `bpy.ops.wm.append()`.

    [1] https://docs.blender.org/api/current/bpy.types.BlendData.html \\
    [2] https://docs.blender.org/api/current/bpy.types.BlendDataLibraries.html?highlight=blenddatalibrary
    """
    # Sanitize name
    names: Optional[List[str]] = [name] if isinstance(name, str) else None if name is None else list(name)
    blocks: Union[List[str], List[bpy.types.ID], None] = deepcopy(names)

    # Append
    with bpy.data.libraries.load(str(filepath), link = link) as (data_from, data_to):
        def append(datatype):
            if name:
                setattr(data_to, datatype, blocks) # The context manager will replace each entry in the List with a reference to the actual data.
            else:
                setattr(data_to, datatype, getattr(data_from, datatype))
        if datatype:
            append(datatype)
        else:
            for attr in dir(data_from):
                append(attr)

    # TODO data_to could be unwrapped and also exposed as a List, if that's more convenient.
    return blocks if name else data_to
