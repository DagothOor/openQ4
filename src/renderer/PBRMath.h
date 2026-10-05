// Copyright (C) 2026 DarkMatter Productions
// Original shared scalar equations for authored metallic/roughness materials.
#ifndef OPENQ4_PBR_MATH_H
#define OPENQ4_PBR_MATH_H

// Keep the scalar kernel executable by both the native numerical tests and
// GLSL. GL embeds the string below; offline Vulkan shaders include this file.
// No renderer state, texture transfer, or legacy-material policy lives here.
// The 0.045 perceptual floor bounds the mirror peak in a half-float HDR target.
#define OPENQ4_PBR_INLINE
#define OPENQ4_PBR_SCALAR_FUNCTIONS \
OPENQ4_PBR_INLINE float PBRClamp(float x, float lo, float hi) { return x < lo ? lo : (x > hi ? hi : x); } \
OPENQ4_PBR_INLINE float PBRRoughness(float r) { return PBRClamp(r, 0.045, 1.0); } \
/* N.V for direct shading. A normal map can turn the shading normal away     \
   from a view the surface itself faces, chiefly at silhouettes. Cutting the \
   light there blacked those pixels out, and the cut flipped with the last   \
   bit of interpolation; clamping keeps every term continuous (Neubelt and   \
   Pettineo 2013). */ \
OPENQ4_PBR_INLINE float PBRShadingNoV(float NoV) { return PBRClamp(NoV, 1.0e-4, 1.0); } \
OPENQ4_PBR_INLINE float PBRFilteredRoughness(float perceptualRoughness, float normalVariance) { \
    float r = PBRRoughness(perceptualRoughness); \
    float alpha = r * r; \
    float kernel = PBRClamp(2.0 * normalVariance, 0.0, 0.18); \
    return sqrt(sqrt(PBRClamp(alpha * alpha + kernel, 0.0, 1.0))); \
} \
OPENQ4_PBR_INLINE float PBRSRGBToLinear(float value) { \
    float x = PBRClamp(value, 0.0, 1.0); \
    return x <= 0.04045 ? x / 12.92 : pow((x + 0.055) / 1.055, 2.4); \
} \
OPENQ4_PBR_INLINE float PBRLinearToSRGB(float value) { \
    float x = PBRClamp(value, 0.0, 1.0); \
    return x <= 0.0031308 ? x * 12.92 : 1.055 * pow(x, 1.0 / 2.4) - 0.055; \
} \
/* The same transfer pair continued above one, for display-referred HDR      \
   framebuffers: Quake 4's FP16 scene holds encoded values beyond white.     \
   Negative input is treated as black. */ \
OPENQ4_PBR_INLINE float PBRSRGBToLinearExtended(float value) { \
    float x = value > 0.0 ? value : 0.0; \
    return x <= 0.04045 ? x / 12.92 : pow((x + 0.055) / 1.055, 2.4); \
} \
OPENQ4_PBR_INLINE float PBRLinearToSRGBExtended(float value) { \
    float x = value > 0.0 ? value : 0.0; \
    return x <= 0.0031308 ? x * 12.92 : 1.055 * pow(x, 1.0 / 2.4) - 0.055; \
} \
/* A classic light term (projection x falloff x color, with the classic     \
   light scale) is display-referred: it is what a white classic surface      \
   shows. Read as encoded radiance, a white Lambertian PBR surface leaves    \
   the same radiance at normal incidence when the light's irradiance is pi   \
   times its decoded value. PBR keeps cosine falloff and its specular lobe. */ \
OPENQ4_PBR_INLINE float PBRClassicLightIrradiance(float displayLight) { \
    return 3.141592653589793 * PBRSRGBToLinearExtended(displayLight); \
} \
OPENQ4_PBR_INLINE float PBRFresnelWeight(float VoH) { \
    float x = 1.0 - PBRClamp(VoH, 0.0, 1.0); \
    float x2 = x * x; \
    return x2 * x2 * x; \
} \
OPENQ4_PBR_INLINE float PBRDistributionGGX(float NoH, float perceptualRoughness) { \
    float r = PBRRoughness(perceptualRoughness); \
    float alpha = r * r; \
    float n = PBRClamp(NoH, 0.0, 1.0); \
    float aNoH = alpha * n; \
    float denominator = (1.0 - n) * (1.0 + n) + aNoH * aNoH; \
    float ratio = alpha / denominator; \
    return ratio * ratio / 3.141592653589793; \
} \
OPENQ4_PBR_INLINE float PBRVisibilitySmithGGX(float NoV, float NoL, float perceptualRoughness) { \
    float v = PBRClamp(NoV, 0.0, 1.0); \
    float l = PBRClamp(NoL, 0.0, 1.0); \
    if (v <= 0.0 || l <= 0.0) { return 0.0; } \
    float r = PBRRoughness(perceptualRoughness); \
    float alpha = r * r; \
    float a2 = alpha * alpha; \
    float lambdaV = l * sqrt(a2 + (1.0 - a2) * v * v); \
    float lambdaL = v * sqrt(a2 + (1.0 - a2) * l * l); \
    return 0.5 / (lambdaV + lambdaL); \
} \
/* Directional albedo E of the single-scattering lobe above with F = 1, the  \
   A + B of the split-sum table. A rough white conductor keeps only 31% of   \
   the light (1 - ln 2). 15-term fit in r and sqrt(NoV) over NoV in [0.1, 1] \
   (grazing views use 0.1); 1/E stays within 3.5% of a visible-normal        \
   reference. Prefer the table where a pass binds it. */ \
OPENQ4_PBR_INLINE float PBRSpecularAlbedo(float NoV, float perceptualRoughness) { \
    float r = PBRRoughness(perceptualRoughness); \
    float u = sqrt(PBRClamp(NoV, 0.1, 1.0)); \
    float c0 = 1.30429459 + u * (-0.93026197 + u * 0.659094632); \
    float c1 = -4.92084694 + u * (15.8142557 + u * (-11.6078072)); \
    float c2 = 14.91817 + u * (-55.1149101 + u * 44.208828); \
    float c3 = -15.5533714 + u * (63.1911125 + u * (-55.7175789)); \
    float c4 = 5.33295727 + u * (-24.152729 + u * 22.883503); \
    return PBRClamp(c0 + r * (c1 + r * (c2 + r * (c3 + r * c4))), 0.3, 1.0); \
} \
/* Multiple-scattering energy compensation for one F0 channel: scale the     \
   single-scattering specular so a white conductor reflects all of a uniform \
   environment. Dielectrics change by at most 9%, rough metals up to 3.3x. */ \
OPENQ4_PBR_INLINE float PBREnergyCompensation(float f0, float specularAlbedo) { \
    return 1.0 + PBRClamp(f0, 0.0, 1.0) * (1.0 / PBRClamp(specularAlbedo, 0.3, 1.0) - 1.0); \
} \
/* Specular occlusion derived from ambient occlusion (Lagarde and de         \
   Rousiers 2014): rough lobes follow the AO, smooth lobes viewed head-on    \
   escape most of it, and grazing views are occluded more. AO 0 stays 0. */  \
OPENQ4_PBR_INLINE float PBRSpecularOcclusion(float NoV, float ao, float perceptualRoughness) { \
    float r = PBRRoughness(perceptualRoughness); \
    float a = PBRClamp(ao, 0.0, 1.0); \
    float lobe = exp2(-16.0 * r * r - 1.0); \
    return PBRClamp(pow(PBRClamp(NoV, 0.0, 1.0) + a, lobe) - 1.0 + a, 0.0, 1.0); \
} \
/* Multi-bounce occlusion for one albedo channel (Jimenez et al. 2016):      \
   light trapped by occluders still bounces off bright surfaces, so a bright \
   albedo darkens less than the raw visibility. Bounded to [v, 1]. */ \
OPENQ4_PBR_INLINE float PBRMultiBounceAO(float visibility, float albedo) { \
    float v = PBRClamp(visibility, 0.0, 1.0); \
    float x = PBRClamp(albedo, 0.0, 1.0); \
    float bounced = ((v * (2.0404 * x - 0.3324) + (0.6417 - 4.7951 * x)) * v + (2.7552 * x + 0.6903)) * v; \
    return PBRClamp(bounced, v, 1.0); \
} \
/* Fade reflections that a normal map turns below the geometric surface;     \
   the argument is dot(reflection, interpolated vertex normal). */ \
OPENQ4_PBR_INLINE float PBRHorizonOcclusion(float RoN) { \
    float h = PBRClamp(1.0 + RoN, 0.0, 1.0); \
    return h * h; \
}

#ifdef __cplusplus
#define OPENQ4_PBR_STRING_IMPL(...) #__VA_ARGS__
#define OPENQ4_PBR_STRING(...) OPENQ4_PBR_STRING_IMPL(__VA_ARGS__)
static const char OPENQ4_PBR_SCALAR_GLSL[] =
    OPENQ4_PBR_STRING(OPENQ4_PBR_SCALAR_FUNCTIONS);
#undef OPENQ4_PBR_STRING
#undef OPENQ4_PBR_STRING_IMPL

#include <cmath>
#undef OPENQ4_PBR_INLINE
#define OPENQ4_PBR_INLINE inline
namespace openq4PBRMath {
using std::exp2;
using std::pow;
using std::sqrt;
OPENQ4_PBR_SCALAR_FUNCTIONS
}
#else
OPENQ4_PBR_SCALAR_FUNCTIONS
#endif

#endif
