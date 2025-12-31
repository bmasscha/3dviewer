import OpenGL.GL as gl
import numpy as np
import ctypes

class ShaderProgram:
    def __init__(self, vertex_source, fragment_source):
        self.program = self.create_program(vertex_source, fragment_source)

    def create_shader(self, source, shader_type):
        shader = gl.glCreateShader(shader_type)
        gl.glShaderSource(shader, source)
        gl.glCompileShader(shader)
        
        if not gl.glGetShaderiv(shader, gl.GL_COMPILE_STATUS):
            error = gl.glGetShaderInfoLog(shader).decode()
            print(f"Shader compilation error ({shader_type}):\n{error}")
            raise RuntimeError("Shader compilation failed")
        return shader

    def create_program(self, vertex_source, fragment_source):
        vertex_shader = self.create_shader(vertex_source, gl.GL_VERTEX_SHADER)
        fragment_shader = self.create_shader(fragment_source, gl.GL_FRAGMENT_SHADER)

        program = gl.glCreateProgram()
        gl.glAttachShader(program, vertex_shader)
        gl.glAttachShader(program, fragment_shader)
        gl.glLinkProgram(program)

        if not gl.glGetProgramiv(program, gl.GL_LINK_STATUS):
            error = gl.glGetProgramInfoLog(program).decode()
            print(f"Program linking error:\n{error}")
            raise RuntimeError("Program linking failed")

        gl.glDeleteShader(vertex_shader)
        gl.glDeleteShader(fragment_shader)
        return program

    def use(self):
        gl.glUseProgram(self.program)

    def set_int(self, name, value):
        loc = gl.glGetUniformLocation(self.program, name)
        gl.glUniform1i(loc, value)
    
    def set_float(self, name, value):
        loc = gl.glGetUniformLocation(self.program, name)
        gl.glUniform1f(loc, value)
    
    def set_vec3(self, name, x, y, z):
        loc = gl.glGetUniformLocation(self.program, name)
        gl.glUniform3f(loc, x, y, z)

    def set_vec2(self, name, x, y):
        loc = gl.glGetUniformLocation(self.program, name)
        gl.glUniform2f(loc, x, y)
        
    def set_mat4(self, name, value):
        loc = gl.glGetUniformLocation(self.program, name)
        gl.glUniformMatrix4fv(loc, 1, gl.GL_FALSE, value)


class VolumeRenderer:
    def __init__(self):
        self.texture_id = None
        self.volume_dim = (0, 0, 0) # W, H, D

    def create_texture(self, data, width, height, depth):
        """
        Uploads 16-bit volume data to a 3D OpenGL Texture.
        """
        if self.texture_id:
            gl.glDeleteTextures(1, [self.texture_id])

        self.texture_id = gl.glGenTextures(1)
        gl.glBindTexture(gl.GL_TEXTURE_3D, self.texture_id)

        # Set texture parameters
        gl.glTexParameteri(gl.GL_TEXTURE_3D, gl.GL_TEXTURE_WRAP_S, gl.GL_CLAMP_TO_EDGE)
        gl.glTexParameteri(gl.GL_TEXTURE_3D, gl.GL_TEXTURE_WRAP_T, gl.GL_CLAMP_TO_EDGE)
        gl.glTexParameteri(gl.GL_TEXTURE_3D, gl.GL_TEXTURE_WRAP_R, gl.GL_CLAMP_TO_EDGE)
        gl.glTexParameteri(gl.GL_TEXTURE_3D, gl.GL_TEXTURE_MAG_FILTER, gl.GL_LINEAR)
        gl.glTexParameteri(gl.GL_TEXTURE_3D, gl.GL_TEXTURE_MIN_FILTER, gl.GL_LINEAR)

        # Pixel storage mode for unpacking (alignment)
        gl.glPixelStorei(gl.GL_UNPACK_ALIGNMENT, 1)

        # Internal format: GL_R16
        # Format: GL_RED
        # Type: GL_UNSIGNED_SHORT
        
        gl.glTexImage3D(
            gl.GL_TEXTURE_3D,
            0,
            gl.GL_R16,
            width,
            height,
            depth,
            0,
            gl.GL_RED,
            gl.GL_UNSIGNED_SHORT,
            data
        )
        self.volume_dim = (width, height, depth)

    def bind_texture(self, unit=0):
        if self.texture_id:
            gl.glActiveTexture(gl.GL_TEXTURE0 + unit)
            gl.glBindTexture(gl.GL_TEXTURE_3D, self.texture_id)

    def create_tf_texture(self, data):
        """
        Uploads (256, 4) float32 data to a 1D OpenGL Texture.
        """
        if hasattr(self, 'tf_texture_id') and self.tf_texture_id:
            gl.glDeleteTextures(1, [self.tf_texture_id])
        
        self.tf_texture_id = gl.glGenTextures(1)
        gl.glBindTexture(gl.GL_TEXTURE_1D, self.tf_texture_id)
        
        gl.glTexParameteri(gl.GL_TEXTURE_1D, gl.GL_TEXTURE_WRAP_S, gl.GL_CLAMP_TO_EDGE)
        gl.glTexParameteri(gl.GL_TEXTURE_1D, gl.GL_TEXTURE_MAG_FILTER, gl.GL_LINEAR)
        gl.glTexParameteri(gl.GL_TEXTURE_1D, gl.GL_TEXTURE_MIN_FILTER, gl.GL_LINEAR)
        
        import sys
        import traceback
        try:
            gl.glTexImage1D(
                gl.GL_TEXTURE_1D,
                0,
                gl.GL_RGBA32F,
                data.shape[0],
                0,
                gl.GL_RGBA,
                gl.GL_FLOAT,
                data
            )
        except Exception as e:
            print(f"Error in create_tf_texture: {e}")
            traceback.print_exc()

    def bind_tf_texture(self, unit=1):
        if hasattr(self, 'tf_texture_id') and self.tf_texture_id:
            gl.glActiveTexture(gl.GL_TEXTURE0 + unit)
            gl.glBindTexture(gl.GL_TEXTURE_1D, self.tf_texture_id)
