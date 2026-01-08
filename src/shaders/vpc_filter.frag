#version 450 core
out vec4 FragColor;

in vec2 TexCoord;

uniform sampler2D textureSampler;
uniform float distance;   // Propagation distance (z)
uniform float wavelength; // Effective wavelength (lambda)
uniform int enabled;      // Toggle VPC

// 3x3 Laplacian Kernel
//  0  1  0
//  1 -4  1
//  0  1  0
// (Or similar discrete approximation)

void main()
{
    vec4 color = texture(textureSampler, TexCoord);
    
    if (enabled == 0) {
        FragColor = color;
        return;
    }

    if (color.a < 0.01) {
        discard;
    }
    
    // We process the RGB intensity. Assuming grayscale, R=G=B.
    // Use Red channel for calculation.
    float I_center = color.r;
    
    // Avoid log(0)
    float eps = 1e-4;
    float P_center = log(max(I_center, eps));
    
    // Laplacian Calculation
    vec2 texSize = vec2(textureSize(textureSampler, 0));
    vec2 dt = 1.0 / texSize;
    
    float P_left  = log(max(texture(textureSampler, TexCoord + vec2(-dt.x, 0.0)).r, eps));
    float P_right = log(max(texture(textureSampler, TexCoord + vec2( dt.x, 0.0)).r, eps));
    float P_down  = log(max(texture(textureSampler, TexCoord + vec2(0.0, -dt.y)).r, eps));
    float P_up    = log(max(texture(textureSampler, TexCoord + vec2(0.0,  dt.y)).r, eps));
    
    // Discrete Laplacian: (f(x+h) + f(x-h) + f(y+h) + f(y-h) - 4f(x,y)) / h^2
    // We treat 'h' as 1 pixel unit effectively, scaling is absorbed in 'distance'.
    float laplacian = (P_left + P_right + P_down + P_up - 4.0 * P_center);
    
    // TIE transport term: - (z * lambda / 2pi) * laplacian
    // We absorb 1/2pi and pixel scale factors into the user-controlled 'distance' for simplicity.
    // The simplified Paganin filter often looks like I_out = I_in * (1 + gamma * Laplacian(phi))
    // Here we use the form: I_vpc = I_abs * (1 - factor * laplacian)
    
    float factor = distance * wavelength * 10.0; // Scaling factor for usability
    float correction = 1.0 - factor * laplacian;
    
    vec3 outRGB = color.rgb * correction;
    
    // Clamp to valid range
    // outRGB = clamp(outRGB, 0.0, 1.0); 
    // Sometimes phase contrast can produce values > 1.0 (constructive interference), 
    // but monitors clamp anyway.
    
    FragColor = vec4(outRGB, color.a);
}
