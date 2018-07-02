#
# This source file is part of appleseed.
# Visit http://appleseedhq.net/ for additional information and resources.
#
# This software is released under the MIT license.
#
# Copyright (c) 2014-2018 The appleseedhq Organization
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
# THE SOFTWARE.
#

import appleseed as asr
import bpy

from .translator import Translator, ObjectKey
from ..logger import get_logger

logger = get_logger()


class MaterialTranslator(Translator):

    #
    # Constructor.
    #

    def __init__(self, mat, asset_handler, preview=False):
        super(MaterialTranslator, self).__init__(mat)

        self._preview = preview
        self.__asset_handler = asset_handler

        self.__shader_group = None

        if self.bl_node_tree:
            self.__shaders = self.bl_node_tree.nodes

    #
    # Properties.
    #

    @property
    def bl_mat(self):
        return self._bl_obj

    @property
    def bl_node_tree(self):
        return self.bl_mat.appleseed.osl_node_tree

    #
    # Entity translation.
    #

    def create_entities(self, scene):
        mat_name = str(ObjectKey(self.bl_mat)) + "_mat" if not self._preview else "preview_mat"
        as_mat_data = self.bl_mat.appleseed
        osl_params = {'surface_shader': "{0}_surface_shader".format(mat_name)}
        shader_params = {'lighting_samples': as_mat_data.shader_lighting_samples} if hasattr(as_mat_data, "shader_lighting_samples") else {}

        self.__as_shader = asr.SurfaceShader("physical_surface_shader",
                                             "{0}_surface_shader".format(mat_name), shader_params)
        if self.bl_node_tree:
            osl_params['osl_surface'] = self.bl_node_tree.name

            if self.__shader_group == None:
                self.__shader_group = asr.ShaderGroup(self.bl_node_tree.name)
            self.set_shader_group_parameters(scene)

        self.__as_mat = asr.Material('osl_material', mat_name, osl_params)

    def flush_entities(self, assembly):

        assembly.surface_shaders().insert(self.__as_shader)
        assembly.materials().insert(self.__as_mat)
        if self.bl_node_tree:
            assembly.shader_groups().insert(self.__shader_group)

    def update_material(self, mat, assembly, scene):
        self.reset(mat)
        if self.bl_node_tree:
            self.__shaders = self.bl_node_tree.nodes

        mat = assembly.materials().get_by_name(self.appleseed_name)
        assembly.materials().remove(mat)
        self.create_entities(scene)
        self.flush_entities(assembly)

    #
    # Internal methods.
    #

    def set_shader_group_parameters(self, scene):
        for shader in self.__shaders:
            if shader.node_type == 'osl_surface':
                surface_shader = shader
                self.__shader_list = surface_shader.traverse_tree()

        self.__shader_group.clear()

        for shader in self.__shader_list:
            parameters = {}
            parameter_types = shader.parameter_types
            shader_keys = dir(shader)
            for key in parameter_types.keys():
                if key in shader_keys:
                    parameter_value = parameter_types[key]
                    parameter = getattr(shader, key)
                    if key in shader.filepaths:
                        parameter = self.__asset_handler.resolve_path(parameter)
                        if scene.appleseed.sub_textures is True:
                            parameter = self.__asset_handler.substitute_texture(parameter)

                    if parameter_value == "int checkbox":
                        parameter_value = "int"
                        parameter = int(parameter)
                    if parameter_value in ('color', 'vector', 'normal', 'float[2]'):
                        parameter = " ".join(map(str, parameter))
                    parameters[key] = parameter_value + " " + str(parameter)

            for socket in shader.inputs:
                if not socket.is_linked:
                    if socket.socket_value != "":
                        parameter_value = parameter_types[socket.socket_osl_id]
                        parameter = socket.get_socket_value(True)
                        if parameter_value in ('color', 'vector', 'normal', 'float[2]'):
                            parameter = " ".join(map(str, parameter))
                            if parameter_value == 'float[2]':
                                parameter_value = 'float[]'
                        parameters[socket.socket_osl_id] = parameter_value + " " + str(parameter)

            self.__shader_group.add_shader("shader", shader.file_name, shader.name, parameters)

            for output in shader.outputs:
                if output.is_linked:
                    for link in output.links:
                        self.__shader_group.add_connection(shader.name, output.socket_osl_id, link.to_node.name, link.to_socket.socket_osl_id)

        self.__shader_group.add_shader("surface", surface_shader.file_name, surface_shader.name, {})
