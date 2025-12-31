#version 450 compatibility

out vec2 TexCoord;

void main()
{
    gl_Position = gl_Vertex;
    TexCoord = gl_MultiTexCoord0.xy;
}
