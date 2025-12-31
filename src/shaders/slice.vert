#version 450 compatibility

out vec2 TexCoord;

void main()
{
    gl_Position = gl_ModelViewProjectionMatrix * gl_Vertex;
    // However, we are drawing full screen quad manually 
    // code says: glVertex3f...
    // The previous shader: gl_Position = vec4(aPos, 1.0);
    // Let's keep assuming identity matrices for the full screen quad?
    // main.py sets identity? NO, it doesn't set matrices for slice view in render_quad logic itself?
    // render_quad sends -1 to 1 coords.
    
    gl_Position = gl_Vertex;
    TexCoord = gl_MultiTexCoord0.xy;
}
