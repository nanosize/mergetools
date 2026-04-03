"""Shader related stuff."""
import bpy
import gpu
from mathutils import Vector
from gpu_extras.presets import draw_circle_2d
from gpu_extras.batch import batch_for_shader
from .util import find_center


# Blender versions higher than 4.0 don't support 3D_UNIFORM_COLOR but versions below 3.4 require it
# Blender versions below 4.5 don't support POINT_UNIFORM_COLOR
if bpy.app.version[0] >= 5:
    line_type = 'POLYLINE_UNIFORM_COLOR'
    point_type = 'POINT_UNIFORM_COLOR'
elif bpy.app.version[0] == 4:
    line_type = 'POLYLINE_UNIFORM_COLOR'
    point_type = 'UNIFORM_COLOR'
    if bpy.app.version[1] >= 5:
        point_type = 'POINT_UNIFORM_COLOR'
elif bpy.app.version[0] == 3 and bpy.app.version[1] >= 4:
    line_type = 'POLYLINE_UNIFORM_COLOR'
    point_type = 'UNIFORM_COLOR'
else:
    line_type = '3D_POLYLINE_UNIFORM_COLOR'
    point_type = '3D_UNIFORM_COLOR'

try:
    # gpu_backend was added in 3.5
    # Valid return results are ('OPENGL', 'METAL', 'VULKAN')
    backend = bpy.context.preferences.system.gpu_backend
except:
    # Assume Opengl for older versions
    backend = 'OPENGL'

# Dashed lines
# gpu.types.GPUShader is deprecated on Vulkan in 4.5 and completely removed in 5.0
shader_v = None


def get_shader_v():
    global shader_v

    if shader_v is None:
        vert_out = gpu.types.GPUStageInterfaceInfo("my_interface")
        vert_out.smooth('FLOAT', "v_ArcLength")

        shader_info = gpu.types.GPUShaderCreateInfo()
        shader_info.push_constant('MAT4', "u_ViewProjectionMatrix")
        shader_info.push_constant('FLOAT', "u_Scale")
        shader_info.push_constant('VEC4', "u_Color")
        shader_info.vertex_in(0, 'VEC3', "position")
        shader_info.vertex_in(1, 'FLOAT', "arcLength")
        shader_info.vertex_out(vert_out)
        shader_info.fragment_out(0, 'VEC4', "FragColor")

        shader_info.vertex_source(
            "void main()"
            "{"
            "  v_ArcLength = arcLength;"
            "  gl_Position = u_ViewProjectionMatrix * vec4(position, 1.0f);"
            "}"
        )

        shader_info.fragment_source(
            "void main()"
            "{"
            "  if (step(sin(v_ArcLength * u_Scale), 0.5) == 1) discard;"
            "  FragColor = vec4(u_Color);"
            "}"
        )

        shader_v = gpu.shader.create_from_info(shader_info)
        del vert_out
        del shader_info

    return shader_v

if backend != 'VULKAN' and bpy.app.version[0] < 5:
    vertex_shader = '''
        uniform mat4 u_ViewProjectionMatrix;

        in vec3 position;
        in float arcLength;

        out float v_ArcLength;

        void main()
        {
            v_ArcLength = arcLength;
            gl_Position = u_ViewProjectionMatrix * vec4(position, 1.0f);
        }
    '''

    fragment_shader = '''
        uniform float u_Scale;
        uniform vec4 u_Color;

        in float v_ArcLength;
        out vec4 FragColor;

        void main()
        {
            if (step(sin(v_ArcLength * u_Scale), 0.5) == 1) discard;
            FragColor = vec4(u_Color);
        }
    '''


class DrawPoint():
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.shader = None
        self.coords = None
        self.size = None
        self.color = None

    def draw(self):
        batch = batch_for_shader(self.shader, 'POINTS', {"pos": self.coords})
        self.shader.bind()
        self.shader.uniform_float("color", self.color)
        try:  # Needed for Vulkan. Only applicable to Blender >= 4.5
            self.shader.uniform_float("size", self.size)
        except:
            pass
        batch.draw(self.shader)

    def add(self, shader, coords, size, color):
        self.shader = shader
        if isinstance(coords, Vector):
            self.coords = [coords]
        else:
            self.coords = coords
        self.size = size
        self.color = color
        self.draw()


class DrawLine():
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.shader = None
        self.coords = None
        self.width = None
        self.color = None

    def draw(self):
        region = bpy.context.region
        batch = batch_for_shader(self.shader, 'LINES', {"pos": self.coords})
        self.shader.bind()
        self.shader.uniform_float("viewportSize", (region.width, region.height))
        self.shader.uniform_float("color", self.color)
        self.shader.uniform_float("lineWidth", self.width)
        batch.draw(self.shader)

    def add(self, shader, coords, width, color):
        self.shader = shader
        self.coords = coords
        self.width = width
        self.color = color
        self.draw()


class DrawLineDashed():
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.shader = None
        self.coords = None
        self.width = None
        self.color = None
        self.arc_lengths = None

    def draw(self):
        batch = batch_for_shader(self.shader, 'LINES', {"position": self.coords, "arcLength": self.arc_lengths})
        self.shader.bind()
        matrix = bpy.context.region_data.perspective_matrix
        self.shader.uniform_float("u_ViewProjectionMatrix", matrix)
        self.shader.uniform_float("u_Scale", 50)
        self.shader.uniform_float("u_Color", self.color)
        batch.draw(self.shader)

    def add(self, shader, coords, width, color):
        self.shader = shader
        self.coords = coords 
        self.width = width
        self.color = color
        self.arc_lengths = [0]
        for a, b in zip(self.coords[:-1], self.coords[1:]):
            self.arc_lengths.append(self.arc_lengths[-1] + (a - b).length)
        self.draw()


def draw_callback_3d(self, context):
    if self.started and self.start_comp is not None:
        gpu.state.blend_set("ALPHA")
        gpu.state.point_size_set(self.prefs.point_size)
        shader_line = gpu.shader.from_builtin(line_type)
        shader_point = gpu.shader.from_builtin(point_type)
        if self.end_comp is not None and self.end_comp != self.start_comp:
            gpu.state.line_width_set(self.prefs.line_width)
            if not self.multi_merge:
                line_coords = [self.start_comp_transformed, self.end_comp_transformed]
            else:
                line_coords = []
                vert_coords = []
                if self.merge_location == 'CENTER':
                    vert_list = [v.co for v in self.start_sel]
                    if self.end_comp not in self.start_sel:
                        vert_list.append(self.end_comp.co)
                    for v in self.start_sel:
                        line_coords.append(self.world_matrix @ v.co)
                        line_coords.append(self.world_matrix @ find_center(vert_list))
                        vert_coords.append(self.world_matrix @ v.co)
                    line_coords.append(self.end_comp_transformed)
                    line_coords.append(self.world_matrix @ find_center(vert_list))
                elif self.merge_location == 'LAST':
                    for v in self.start_sel:
                        line_coords.append(self.world_matrix @ v.co)
                        line_coords.append(self.end_comp_transformed)
                        vert_coords.append(self.world_matrix @ v.co)
                elif self.merge_location == 'FIRST':
                    for v in self.start_sel:
                        line_coords.append(self.world_matrix @ v.co)
                        line_coords.append(self.start_comp_transformed)
                        vert_coords.append(self.world_matrix @ v.co)
                    line_coords.append(self.end_comp_transformed)
                    line_coords.append(self.start_comp_transformed)

            # Line that connects the start and end position (draw first so it's beneath the vertices)
            if not self.multi_merge:
                tool_line = DrawLine()
                tool_line.add(shader_line, line_coords, self.prefs.line_width, self.prefs.line_color)
            else:
                if backend == 'VULKAN' or bpy.app.version[0] >= 5:
                    shader_dashed = get_shader_v()
                else:
                    shader_dashed = gpu.types.GPUShader(vertex_shader, fragment_shader)
                tool_line = DrawLineDashed()
                tool_line.add(shader_dashed, line_coords, self.prefs.line_width, self.prefs.line_color)

            # Ending edge
            if self.sel_mode == 'EDGE':
                gpu.state.line_width_set(self.prefs.edge_width)
                e1v = [self.world_matrix @ v.co for v in self.end_comp.verts]

                end_edge = DrawLine()
                if self.merge_location in ('FIRST', 'CENTER'):
                    end_edge.add(shader_line, e1v, self.prefs.edge_width, self.prefs.start_color)
                else:
                    end_edge.add(shader_line, e1v, self.prefs.edge_width, self.prefs.end_color)

            # Ending point
            end_point = DrawPoint()
            if self.multi_merge:
                end_point.add(shader_point, vert_coords, self.prefs.point_size, self.prefs.start_color)
            if self.merge_location in ('FIRST', 'CENTER'):
                end_point.add(shader_point, self.end_comp_transformed, self.prefs.point_size, self.prefs.start_color)
            else:
                end_point.add(shader_point, self.end_comp_transformed, self.prefs.point_size, self.prefs.end_color)

            # Middle point
            if self.merge_location == 'CENTER':
                if self.sel_mode == 'VERT':
                    if self.multi_merge:
                        midpoint = self.world_matrix @ find_center(vert_list)
                    else:
                        midpoint = self.world_matrix @ find_center([self.start_comp, self.end_comp])
                elif self.sel_mode == 'EDGE':
                    midpoint = self.world_matrix @ \
                            find_center([find_center(self.start_comp), find_center(self.end_comp)])

                mid_point = DrawPoint()
                mid_point.add(shader_point, midpoint, self.prefs.point_size, self.prefs.end_color)

        # Starting edge
        if self.sel_mode == 'EDGE':
            gpu.state.line_width_set(self.prefs.edge_width)
            e0v = [self.world_matrix @ v.co for v in self.start_comp.verts]

            start_edge = DrawLine()
            if self.merge_location == 'FIRST':
                start_edge.add(shader_line, e0v, self.prefs.edge_width, self.prefs.end_color)
            else:
                start_edge.add(shader_line, e0v, self.prefs.edge_width, self.prefs.start_color)

        # Starting point
        start_point = DrawPoint()
        if self.merge_location == 'FIRST':
            start_point.add(shader_point, self.start_comp_transformed, self.prefs.point_size, self.prefs.end_color)
        else:
            start_point.add(shader_point, self.start_comp_transformed, self.prefs.point_size, self.prefs.start_color)

        gpu.state.line_width_set(1.0)
        gpu.state.point_size_set(1.0)
        gpu.state.blend_set('NONE')


def draw_callback_2d(self, context):
    # Have to add 1 for some reason in order to get proper number of segments.
    # This could potentially also be a ratio with the radius.
    circ_segments = 8 + 1
    draw_circle_2d(self.m_coord, self.prefs.circ_color, self.prefs.circ_radius, segments=circ_segments)
