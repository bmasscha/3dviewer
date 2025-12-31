#version 450 core
out vec4 FragColor;

in vec2 TexCoord;

uniform sampler3D volumeTexture;
uniform sampler3D volumeTexture2;
uniform sampler1D transferFunction;
uniform sampler1D transferFunction2;
uniform int hasOverlay;

uniform int axis; // 0: XY (Z fixed), 1: XZ (Y fixed), 2: YZ (X fixed)
uniform float sliceDepth; // Normalized 0.0 to 1.0 (relative to primary)
uniform float densityMultiplier;
uniform float threshold;
uniform float densityMultiplier2;
uniform float threshold2;
uniform float tfSlope;
uniform float tfOffset;
uniform float tfSlope2;
uniform float tfOffset2;

uniform vec3 boxSize;
uniform vec3 boxSize2;
uniform vec3 overlayOffset;
uniform float overlayScale;

uniform vec3 clipMin;
uniform vec3 clipMax;
uniform vec3 clipMin2;
uniform vec3 clipMax2;

bool isInside(vec3 p, vec3 cMin, vec3 cMax, vec3 bSize) {
    vec3 localP = p / bSize;
    return all(greaterThanEqual(localP, cMin - 0.001)) && all(lessThanEqual(localP, cMax + 0.001));
}

void main()
{
    // coord in texture space [0, 1] for Volume 1
    vec3 coord;
    if (axis == 0) {
        coord = vec3(TexCoord.x, TexCoord.y, sliceDepth);
    } else if (axis == 1) {
        coord = vec3(TexCoord.x, sliceDepth, TexCoord.y);
    } else {
        coord = vec3(sliceDepth, TexCoord.x, TexCoord.y);
    }

    // pos in "World Space" [0, boxSize]
    vec3 pos = coord * boxSize;

    vec4 color1 = vec4(0.0);
    if (isInside(pos, clipMin, clipMax, boxSize)) {
        float val1 = texture(volumeTexture, coord).r;
        if (val1 > threshold) {
            float tfc1 = clamp(val1 * tfSlope + tfOffset, 0.0, 1.0);
            color1 = texture(transferFunction, tfc1);
            color1.rgb *= densityMultiplier * 2.0; // Boost slightly for slices
        }
    }

    vec4 color2 = vec4(0.0);
    if (hasOverlay == 1) {
        vec3 posV2 = (pos - (overlayOffset * boxSize)) / max(0.001, overlayScale);
        if (isInside(posV2, clipMin2, clipMax2, boxSize2)) {
            float val2 = texture(volumeTexture2, posV2 / boxSize2).r;
            if (val2 > threshold2) {
                float tfc2 = clamp(val2 * tfSlope2 + tfOffset2, 0.0, 1.0);
                color2 = texture(transferFunction2, tfc2);
                color2.rgb *= densityMultiplier2 * 2.0;
            }
        }
    }

    // Simple blending for slices
    vec4 composite = vec4(0.0);
    composite.rgb = color1.rgb * (1.0 - color2.a) + color2.rgb * color2.a;
    composite.a = max(color1.a, color2.a);

    if (composite.a < 0.01) discard;
    FragColor = vec4(composite.rgb, 1.0);
}
