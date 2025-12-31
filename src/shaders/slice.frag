#version 450 core
out vec4 FragColor;

in vec2 TexCoord;

uniform sampler3D volumeTexture;
uniform sampler1D transferFunction;
uniform int axis; // 0: XY (Z fixed), 1: XZ (Y fixed), 2: YZ (X fixed)
uniform float sliceDepth; // Normalized 0.0 to 1.0
uniform float densityMultiplier;
uniform float threshold;
uniform float tfSlope;
uniform float tfOffset;

void main()
{
    vec3 coord;
    if (axis == 0) {
        // XY plane, Z is depth
        coord = vec3(TexCoord.x, TexCoord.y, sliceDepth);
    } else if (axis == 1) {
        // XZ plane, Y is depth
        coord = vec3(TexCoord.x, sliceDepth, TexCoord.y);
    } else {
        // YZ plane, X is depth
        coord = vec3(sliceDepth, TexCoord.x, TexCoord.y);
    }

    float val = texture(volumeTexture, coord).r;
    
    if (val < threshold) {
        discard;
    }
    
    float tf_coord = clamp(val * tfSlope + tfOffset, 0.0, 1.0);
    vec4 color = texture(transferFunction, tf_coord);
    color.rgb *= densityMultiplier; // Simple intensity scale
    
    FragColor = vec4(color.rgb, 1.0);
}
