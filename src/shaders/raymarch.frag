#version 450 core
out vec4 FragColor;

in vec2 TexCoord;

uniform sampler3D volumeTexture;
uniform sampler1D transferFunction;
uniform vec3 camPos;
uniform vec3 camDir; // Front_vector
uniform vec3 camUp;
uniform vec3 camRight;

uniform vec2 resolution;
uniform float fov;
uniform vec3 boxSize;

uniform int renderMode; // 0: MIP, 1: Standard, 2: Cinematic
uniform float densityMultiplier;
uniform float threshold;
uniform float lightIntensity;
uniform float stepSize;
uniform int maxSteps;
uniform vec3 lightDir;
uniform float tfSlope;
uniform float tfOffset;

uniform float ambientLight;
uniform float diffuseLight;

uniform vec3 clipMin;
uniform vec3 clipMax;


#define SHADING_INTENSITY 0.8

// Pseudo-random function for jitter
float rand(vec2 co) {
    return fract(sin(dot(co.xy, vec2(12.9898, 78.233))) * 43758.5453);
}

// Estimate gradient for lighting
vec3 calculateGradient(vec3 p) {
    float delta = 0.01;
    float x = texture(volumeTexture, (p + vec3(delta, 0, 0)) / boxSize).r - texture(volumeTexture, (p - vec3(delta, 0, 0)) / boxSize).r;
    float y = texture(volumeTexture, (p + vec3(0, delta, 0)) / boxSize).r - texture(volumeTexture, (p - vec3(0, delta, 0)) / boxSize).r;
    float z = texture(volumeTexture, (p + vec3(0, 0, delta)) / boxSize).r - texture(volumeTexture, (p - vec3(0, 0, delta)) / boxSize).r;
    vec3 g = vec3(x, y, z);
    float l = length(g);
    if (l < 0.0001) return vec3(0.0);
    return g / l;
}

struct RayHit {
    float tNear;
    float tFar;
    vec3 normal;
};

// Simple Ray-Box Intersection with Normal
RayHit intersectBox(vec3 orig, vec3 dir) {
    vec3 boxMin = max(vec3(0.0), clipMin * boxSize);
    vec3 boxMax = min(boxSize, clipMax * boxSize); 
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
    
    // Deterministic dithering instead of random jitter to avoid salt-and-pepper noise
    // Use a simple 4x4 Bayer matrix pattern
    vec2 pixelPos = TexCoord * resolution;
    int x = int(mod(pixelPos.x, 4.0));
    int y = int(mod(pixelPos.y, 4.0));
    float bayerMatrix[16] = float[16](
        0.0/16.0,  8.0/16.0,  2.0/16.0, 10.0/16.0,
        12.0/16.0,  4.0/16.0, 14.0/16.0,  6.0/16.0,
        3.0/16.0, 11.0/16.0,  1.0/16.0,  9.0/16.0,
        15.0/16.0,  7.0/16.0, 13.0/16.0,  5.0/16.0
    );
    float dither = bayerMatrix[y * 4 + x];
    float jitter = dither * stepSize;
    
    float dist = tStart + jitter;
    vec3 pos = camPos + dist * rayDir;
    
    vec4 accumulatedColor = vec4(0.0);
    vec3 L = normalize(lightDir);
    
    // Track if we're very close to the entry point (clipping boundary)
    bool nearClipBoundary = (hit.tNear > 0.001);
    float distanceFromEntry = 0.0;
    
    if (renderMode == 0) { // MIP
        float maxVal = 0.0;
        for(int i = 0; i < maxSteps; i++) {
            if (dist >= tEnd) break;
            float val = texture(volumeTexture, pos / boxSize).r;
            float tf_coord = clamp(val * tfSlope + tfOffset, 0.0, 1.0);
            if (tf_coord > maxVal) maxVal = tf_coord;
            pos += rayDir * stepSize;
            dist += stepSize;
        }
        if (maxVal > threshold) {
            accumulatedColor = texture(transferFunction, maxVal);
        } else {
            discard;
        }
    } 
    else if (renderMode == 1 || renderMode == 2) { // Standard or Cinematic
        for(int i = 0; i < maxSteps; i++) {
            if (dist >= tEnd || accumulatedColor.a >= 0.99) break;
            
            float val = texture(volumeTexture, pos / boxSize).r;
            if (val > threshold) {
                float tf_coord = clamp(val * tfSlope + tfOffset, 0.0, 1.0);
                vec4 src = texture(transferFunction, tf_coord);
                
                // Better Alpha scaling: allow it to reach higher values per step if density is high
                float alpha = src.a * densityMultiplier * stepSize;
                alpha = 1.0 - exp(-alpha * 20.0); // Use exponential extinction for smoother and more solid look
                alpha = clamp(alpha, 0.0, 1.0);
                
                if (alpha > 0.001) {
                        vec3 normal;
                        
                        // Use gradient-based normal for lighting
                        if (nearClipBoundary && distanceFromEntry < stepSize * 2.5) {
                            // At clipping boundary, use the geometric normal
                            normal = hitNormal;
                        } else {
                            normal = -calculateGradient(pos);
                            // Fallback to geometric normal if gradient is too weak
                            if (length(normal) < 0.1) {
                                normal = hitNormal;
                            }
                        }
                        
                        float diff = max(dot(normal, L), 0.0); // Strict Lambertian term (removed 0.15 floor)
                        
                        vec3 finalColor;
                    
                    if (renderMode == 2) { // Cinematic
                        // Basic Blinn-Phong Specular
                        vec3 viewDir = -rayDir;
                        vec3 halfDir = normalize(L + viewDir);
                        float spec = pow(max(dot(normal, halfDir), 0.0), 32.0);
                        vec3 specularPart = vec3(0.6) * spec * src.a * lightIntensity;
                        
                        // Enhanced Volumetric Shadows
                        float shadow = 1.0;
                        float shadowStep = 0.015; // Fixed step size to ensure consistent reach regardless of quality
                        vec3 shadowPos = pos + normal * 0.01; // Offset to avoid self-shadowing
                        
                        for(int j=0; j<24; j++) { // Increased steps slightly for better reach (24 * 0.015 = 0.36 units)
                            shadowPos += L * shadowStep;
                            
                            // Check if we exited the volume or clipping box
                            vec3 cMin = max(vec3(0.0), clipMin * boxSize);
                            vec3 cMax = min(boxSize, clipMax * boxSize);
                            if (any(lessThan(shadowPos, cMin)) || any(greaterThan(shadowPos, cMax))) break;
                            
                            float sVal = texture(volumeTexture, shadowPos / boxSize).r;
                            if (sVal > threshold) {
                                float s_tf_coord = clamp(sVal * tfSlope + tfOffset, 0.0, 1.0);
                                vec4 sSrc = texture(transferFunction, s_tf_coord);
                                
                                // Volumetric extinction based on opacity
                                // We use a slightly different multiplier for shadows to control "hardness"
                                float shadowOpacity = sSrc.a * densityMultiplier * shadowStep * 15.0;
                                shadow *= exp(-shadowOpacity);
                                
                                if (shadow < 0.02) {
                                    shadow = 0.0;
                                    break;
                                }
                            }
                        }
                        // Final lighting: combine ambient and diffuse (scaled by shadow)
                        // Removed shadow floor (mix 0.15) to allow full darkness if ambient is 0
                        float lightingVal = (ambientLight + diffuseLight * diff * shadow) * lightIntensity;
                        finalColor = src.rgb * lightingVal + specularPart;
                    } else {
                        // Standard Shading
                        float shadedDiff = diff; // Strict diffuse for standard too
                        finalColor = src.rgb * (shadedDiff * lightIntensity);
                    }
                    
                    // Standard Front-to-Back Composition
                    accumulatedColor.rgb += (1.0 - accumulatedColor.a) * finalColor * alpha;
                    accumulatedColor.a   += (1.0 - accumulatedColor.a) * alpha;
                }
            }
            
            pos += rayDir * stepSize;
            dist += stepSize;
            distanceFromEntry += stepSize;
        }
    }
    else if (renderMode == 3) { // MIDA (Maximum Intensity Difference Accumulation)
        float maxVal = 0.0;
        for(int i = 0; i < maxSteps; i++) {
            if (dist >= tEnd || accumulatedColor.a >= 0.99) break;
            
            float val = texture(volumeTexture, pos / boxSize).r;
            if (val > threshold) {
                float tf_coord = clamp(val * tfSlope + tfOffset, 0.0, 1.0);
                
                // MIDA weighting: only accumulate the difference from the current maximum
                float delta = max(0.0, tf_coord - maxVal);
                if (delta > 0.001) {
                    vec4 src = texture(transferFunction, tf_coord);
                    
                    vec3 normal = -calculateGradient(pos);
                    // Use entry normal if gradient is weak near the surface
                    if (length(normal) < 0.1 && i < 2) {
                        normal = hitNormal;
                    }
                    
                    float diff = max(dot(normal, L), 0.15) * lightIntensity;
                    vec3 finalColor = src.rgb * diff;
                    
                    // Alpha scaling using intensity difference
                    // Weighting by (1.0 - maxVal) helps normalized the contribution
                    float alpha = src.a * densityMultiplier * stepSize * (delta / (1.0 - maxVal + 1e-6));
                    alpha = 1.0 - exp(-alpha * 20.0);
                    
                    accumulatedColor.rgb += (1.0 - accumulatedColor.a) * finalColor * alpha;
                    accumulatedColor.a   += (1.0 - accumulatedColor.a) * alpha;
                    
                    maxVal = tf_coord;
                }
            }
            
            pos += rayDir * stepSize;
            dist += stepSize;
        }
    }
    
    if (accumulatedColor.a < 0.01) discard;
    FragColor = accumulatedColor;
}
