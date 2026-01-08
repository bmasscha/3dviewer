#version 450 core
out vec4 FragColor;

in vec2 TexCoord;

uniform sampler3D volumeTexture;
uniform sampler3D volumeTexture2;
uniform sampler1D transferFunction;
uniform sampler1D transferFunction2;
uniform int hasOverlay;

uniform vec3 camPos;
uniform vec3 camDir; // Front_vector
uniform vec3 camUp;
uniform vec3 camRight;

uniform vec2 resolution;
uniform float fov;
uniform vec3 boxSize;
uniform vec3 boxSize2;

uniform vec3 overlayOffset;
uniform float overlayScale;

uniform int renderMode; // Primary: 0: MIP, 1: Std, 2: Cin, 3: MIDA
uniform int renderMode2; // Overlay: 0: MIP, 1: Std, 2: Cin, 3: MIDA
uniform float densityMultiplier;
uniform float threshold;
uniform float densityMultiplier2;
uniform float threshold2;

uniform float lightIntensity;
uniform float stepSize;
uniform int maxSteps;
uniform vec3 lightDir;
uniform float tfSlope;
uniform float tfOffset;
uniform float tfSlope2;
uniform float tfOffset2;

uniform float ambientLight;
uniform float diffuseLight;
uniform float specularIntensity;
uniform float shininess;
uniform float gradientWeight;

uniform vec3 clipMin;
uniform vec3 clipMax;
uniform vec3 clipMin2;
uniform vec3 clipMax2;


#define SHADING_INTENSITY 0.8

// Pseudo-random function for jitter
float rand(vec2 co) {
    return fract(sin(dot(co.xy, vec2(12.9898, 78.233))) * 43758.5453);
}

// Estimate gradient for lighting using Central Difference
vec3 calculateGradient(sampler3D tex, vec3 p, vec3 bSize) {
    vec3 uv = p / bSize;
    vec3 texSize = vec3(textureSize(tex, 0));
    vec3 dt = vec3(1.0) / texSize;
    
    float val = texture(tex, uv).r; // Sample center for potential optimization or debug? Not needed for Central Diff.
    
    // Central Difference
    float dx = texture(tex, uv + vec3(dt.x, 0, 0)).r - texture(tex, uv - vec3(dt.x, 0, 0)).r;
    float dy = texture(tex, uv + vec3(0, dt.y, 0)).r - texture(tex, uv - vec3(0, dt.y, 0)).r;
    float dz = texture(tex, uv + vec3(0, 0, dt.z)).r - texture(tex, uv - vec3(0, 0, dt.z)).r;
    
    return vec3(dx, dy, dz);
}

struct RayHit {
    float tNear;
    float tFar;
    vec3 normal;
};

// Simple Ray-Box Intersection with Normal
RayHit intersectBox(vec3 orig, vec3 dir) {
    // Intersect with the full box bounds [0, boxSize]
    // The specific clipping for each volume happens inside the loop.
    vec3 boxMin = vec3(0.0);
    vec3 boxMax = boxSize; 
    vec3 invDir = 1.0 / dir;
    vec3 tmin = (boxMin - orig) * invDir;
    vec3 tmax = (boxMax - orig) * invDir;
    vec3 t1 = min(tmin, tmax);
    vec3 t2 = max(tmin, tmax);
    float tNear = max(max(t1.x, t1.y), t1.z);
    float tFar = min(min(t2.x, t2.y), t2.z);
    
    vec3 normal = vec3(0.0);
    if (tNear > 0.0) {
        if (tNear == t1.x) normal = vec3(-sign(dir.x), 0, 0);
        else if (tNear == t1.y) normal = vec3(0, -sign(dir.y), 0);
        else if (tNear == t1.z) normal = vec3(0, 0, -sign(dir.z));
    }
    
    return RayHit(tNear, tFar, normal);
}

// Helper to check if a point is within a clip box
bool isInside(vec3 p, vec3 cMin, vec3 cMax, vec3 bSize) {
    vec3 localP = p / bSize;
    return all(greaterThanEqual(localP, cMin - 0.001)) && all(lessThanEqual(localP, cMax + 0.001));
}


void main()
{
    // Generate ray direction for this pixel
    vec2 uv = (TexCoord - 0.5) * 2.0;
    uv.x *= resolution.x / resolution.y;
    
    vec3 rayDir = normalize(camDir + uv.x * camRight + uv.y * camUp);
    
    RayHit hit = intersectBox(camPos, rayDir);
    
    if (hit.tNear > hit.tFar || hit.tFar < 0.0) {
        discard;
    }

    float tStart = max(0.0, hit.tNear);
    float tEnd = hit.tFar;
    vec3 hitNormal = hit.normal;
    
    vec2 pixelPos = TexCoord * resolution;
    int x_bayer = int(mod(pixelPos.x, 4.0));
    int y_bayer = int(mod(pixelPos.y, 4.0));
    float bayerMatrix[16] = float[16](
        0.0/16.0,  8.0/16.0,  2.0/16.0, 10.0/16.0,
        12.0/16.0,  4.0/16.0, 14.0/16.0,  6.0/16.0,
        3.0/16.0, 11.0/16.0,  1.0/16.0,  9.0/16.0,
        15.0/16.0,  7.0/16.0, 13.0/16.0,  5.0/16.0
    );
    float dither = bayerMatrix[y_bayer * 4 + x_bayer];
    float jitter = dither * stepSize;
    
    float dist = tStart + jitter;
    vec3 pos = camPos + dist * rayDir;
    
    vec4 accumulatedColor = vec4(0.0);
    vec3 L = normalize(lightDir);
    
    float maxVal1 = 0.0;
    float maxVal2 = 0.0;
    
    // Unified Loop handles all modes and independent clipping
    for(int i = 0; i < maxSteps; i++) {
        if (dist >= tEnd || accumulatedColor.a >= 0.99) break;
        
        vec4 stepColor1 = vec4(0.0);
        vec4 stepColor2 = vec4(0.0);

        // --- Volume 1 Processing (Primary) ---
        if (isInside(pos, clipMin, clipMax, boxSize)) {
            float val1 = texture(volumeTexture, pos / boxSize).r;
            if (renderMode == 0) { // MIP
                float tfc1 = clamp(val1 * tfSlope + tfOffset, 0.0, 1.0);
                if (tfc1 > maxVal1) maxVal1 = tfc1;
            } else { // VR / MIDA
                if (val1 > threshold) {
                    float tfc1 = clamp(val1 * tfSlope + tfOffset, 0.0, 1.0);
                    vec4 src1 = texture(transferFunction, tfc1);
                    float a1 = 0.0;
                    
                    if (renderMode == 3) { // MIDA
                        float delta = max(0.0, tfc1 - maxVal1);
                        if (delta > 0.001) {
                            a1 = 1.0 - exp(-src1.a * densityMultiplier * stepSize * (delta / (1.0 - maxVal1 + 1e-6)) * 20.0);
                            maxVal1 = max(maxVal1, tfc1);
                        }
                    } else { // Standard / Cinematic
                        a1 = 1.0 - exp(-src1.a * densityMultiplier * stepSize * 20.0);
                    }
                    
                    if (a1 > 0.0) {
                        vec3 g1 = calculateGradient(volumeTexture, pos, boxSize);
                        float gMag1 = length(g1);
                        
                        // Edge Enhancement (Only in mode 5)
                        if (renderMode == 5 && gradientWeight > 0.0) {
                            // Amplify gradient to ensure edges reach 1.0, then raise to power to kill low-gradient noise
                            float normalizedG = clamp(gMag1 * 10.0, 0.0, 1.0);
                            float edgeFactor = pow(normalizedG, max(1.0, gradientWeight * 0.5));
                            a1 *= edgeFactor;
                        }

                        if (a1 > 0.001) {
                            vec3 n1 = -normalize(g1);
                            if (gMag1 < 0.001) n1 = hitNormal;
                            
                            // Decide Shading Type
                            vec3 color1;
                            if (renderMode >= 4) { // Advanced Shaded Modes (Shaded VR / Edge Enhanced)
                                // Blinn-Phong
                                float diff1 = max(dot(n1, L), 0.15);
                                vec3 V = -rayDir;
                                vec3 H = normalize(L + V);
                                float spec1 = pow(max(dot(n1, H), 0.0), shininess);
                                color1 = src1.rgb * (ambientLight + diffuseLight * diff1) * lightIntensity;
                                color1 += specularIntensity * spec1 * lightIntensity;
                            } else {
                                // Standard / Cinematic / MIDA (Simple Shading)
                                float diff1 = max(dot(n1, L), (renderMode == 2 ? 0.0 : 0.15));
                                color1 = src1.rgb * (ambientLight + diffuseLight * diff1) * lightIntensity;
                            }
                            
                            stepColor1 = vec4(color1, a1);
                        }
                    }
                }
            }
        }

        // --- Volume 2 Processing (Overlay) ---
        if (hasOverlay == 1) {
            vec3 posV2 = (pos - (overlayOffset * boxSize)) / max(0.001, overlayScale);
            if (isInside(posV2, clipMin2, clipMax2, boxSize2)) {
                float val2 = texture(volumeTexture2, posV2 / boxSize2).r;
                if (renderMode2 == 0) { // MIP
                    float tfc2 = clamp(val2 * tfSlope2 + tfOffset2, 0.0, 1.0);
                    if (tfc2 > maxVal2) maxVal2 = tfc2;
                } else { // VR / MIDA
                    if (val2 > threshold2) {
                        float tfc2 = clamp(val2 * tfSlope2 + tfOffset2, 0.0, 1.0);
                        vec4 src2 = texture(transferFunction2, tfc2);
                        float a2 = 0.0;
                        
                        if (renderMode2 == 3) { // MIDA
                            float delta = max(0.0, tfc2 - maxVal2);
                            if (delta > 0.001) {
                                a2 = 1.0 - exp(-src2.a * densityMultiplier2 * stepSize * (delta / (1.0 - maxVal2 + 1e-6)) * 20.0);
                                maxVal2 = max(maxVal2, tfc2);
                            }
                        } else { // Standard / Cinematic
                            a2 = 1.0 - exp(-src2.a * densityMultiplier2 * stepSize * 20.0);
                        }

                        if (a2 > 0.0) {
                            vec3 g2 = calculateGradient(volumeTexture2, posV2, boxSize2);
                            float gMag2 = length(g2);
                            
                            // Edge Enhancement (Only in mode 5)
                            if (renderMode2 == 5 && gradientWeight > 0.0) {
                                float normalizedG = clamp(gMag2 * 10.0, 0.0, 1.0);
                                float edgeFactor = pow(normalizedG, max(1.0, gradientWeight * 0.5));
                                a2 *= edgeFactor;
                            }

                            if (a2 > 0.001) {
                                vec3 n2 = -normalize(g2);
                                if (gMag2 < 0.001) n2 = hitNormal;
                                
                                // Decide Shading Type
                                vec3 color2;
                                if (renderMode2 >= 4) { // Advanced Shaded Modes
                                    // Blinn-Phong
                                    float diff2 = max(dot(n2, L), 0.15);
                                    vec3 V = -rayDir;
                                    vec3 H = normalize(L + V);
                                    float spec2 = pow(max(dot(n2, H), 0.0), shininess);
                                    color2 = src2.rgb * (ambientLight + diffuseLight * diff2) * lightIntensity;
                                    color2 += specularIntensity * spec2 * lightIntensity;
                                } else {
                                    // Standard / Cinematic / MIDA (Simple Shading)
                                    float diff2 = max(dot(n2, L), (renderMode2 == 2 ? 0.0 : 0.15));
                                    color2 = src2.rgb * (ambientLight + diffuseLight * diff2) * lightIntensity;
                                }
                                
                                stepColor2 = vec4(color2, a2);
                            }
                        }
                    }
                }
            }
        }

        // --- Compositing for the Step ---
        // Blend non-MIP contributions
        vec4 composite = vec4(0.0);
        composite.rgb = stepColor1.rgb * stepColor1.a * (1.0 - stepColor2.a) + stepColor2.rgb * stepColor2.a;
        composite.a = 1.0 - (1.0 - stepColor1.a) * (1.0 - stepColor2.a);

        if (composite.a > 0.0) {
            accumulatedColor.rgb += (1.0 - accumulatedColor.a) * composite.rgb;
            accumulatedColor.a   += (1.0 - accumulatedColor.a) * composite.a;
        }

        pos += rayDir * stepSize;
        dist += stepSize;
    }

    // --- Post-Pass: Blend MIP result ---
    // If a channel was in MIP mode, its contribution hasn't been added yet.
    if (renderMode == 0 && maxVal1 > threshold) {
        vec4 mipC1 = texture(transferFunction, maxVal1);
        // Blend under the VR if we want occlusion, but for multimodality 
        // it's often better to blend as an overlay.
        accumulatedColor.rgb = accumulatedColor.rgb * (1.0 - mipC1.a) + mipC1.rgb * mipC1.a;
        accumulatedColor.a = max(accumulatedColor.a, mipC1.a);
    }
    if (hasOverlay == 1 && renderMode2 == 0 && maxVal2 > threshold2) {
        vec4 mipC2 = texture(transferFunction2, maxVal2);
        accumulatedColor.rgb = accumulatedColor.rgb * (1.0 - mipC2.a) + mipC2.rgb * mipC2.a;
        accumulatedColor.a = max(accumulatedColor.a, mipC2.a);
    }
    
    if (accumulatedColor.a < 0.01) discard;
    FragColor = accumulatedColor;
}
