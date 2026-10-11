// Marca en el stencil (bit 32) los píxeles donde lo visible es un personaje grande (jefe, sumo). No pinta color.
// La dibuja FX/XRayOccluder con copias de las mallas del personaje, después de todos los opacos: con ZTest LEqual
// solo pasa donde el personaje quedó delante (si Kaito está delante, su profundidad gana y no se marca). La silueta
// de Kaito (Nindo/CharacterXRay) se dibuja solo sobre esa marca, así sus propias partes nunca se tapan a sí mismas.
// El bit 32 no se cruza con los 64/128 de la sombra de Kokuyō (NindoShadowInk).
Shader "Nindo/OccluderMark"
{
    SubShader
    {
        Tags { "RenderType" = "Opaque" "Queue" = "Geometry+499" "RenderPipeline" = "UniversalPipeline" "IgnoreProjector" = "True" }

        Pass
        {
            Name "OccluderMark"
            Tags { "LightMode" = "UniversalForward" }
            ZTest LEqual
            ZWrite Off
            ColorMask 0
            Cull Back
            Offset -1, -1
            Stencil { Ref 32 WriteMask 32 Comp Always Pass Replace }

            HLSLPROGRAM
            #pragma vertex vert
            #pragma fragment frag
            #include "Packages/com.unity.render-pipelines.universal/ShaderLibrary/Core.hlsl"

            struct A { float4 pos : POSITION; };
            struct V { float4 pos : SV_POSITION; };

            V vert(A i) { V o; o.pos = TransformObjectToHClip(i.pos.xyz); return o; }
            half4 frag(V i) : SV_Target { return 0; }
            ENDHLSL
        }
    }

    FallBack Off
}
