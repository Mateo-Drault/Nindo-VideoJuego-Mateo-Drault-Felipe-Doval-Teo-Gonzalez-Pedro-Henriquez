// Silueta de Kaito cuando lo tapa un personaje grande (el cuerpo del koi, la armadura de Kokuyō, el sumo): tinta
// translúcida con el borde dorado de la bandana. La dibuja FX/XRaySilhouette con copias de sus mallas.
// ZTest Greater (la escena está más cerca de la cámara que Kaito) y además el stencil: solo donde lo visible es un
// personaje grande (bit 32, lo escribe Nindo/OccluderMark). Antes bastaba el ZTest con la malla adelantada 0.5 m y
// sus propias partes (el brazo detrás del torso, la katana detrás de la pierna) se marcaban en amarillo encima de él;
// los píxeles de Kaito nunca tienen la marca, así que eso ya no puede pasar. Los aleros y árboles los aparta
// CameraOcclusion: no hace falta silueta para ellos.
Shader "Nindo/CharacterXRay"
{
    Properties
    {
        _Ink ("Tinta", Color) = (0.05, 0.04, 0.07, 0.55)
        _Rim ("Borde", Color) = (1, 0.78, 0.3, 1)
        _Pull ("Adelanto hacia la cámara (m)", Float) = 0.05
    }

    SubShader
    {
        Tags { "RenderType" = "Transparent" "Queue" = "Transparent+20" "RenderPipeline" = "UniversalPipeline" "IgnoreProjector" = "True" }

        Pass
        {
            Name "XRay"
            Tags { "LightMode" = "UniversalForward" }
            ZTest Greater
            ZWrite Off
            Stencil { Ref 32 ReadMask 32 Comp Equal }
            Cull Back
            Blend SrcAlpha OneMinusSrcAlpha

            HLSLPROGRAM
            #pragma vertex vert
            #pragma fragment frag
            #include "Packages/com.unity.render-pipelines.universal/ShaderLibrary/Core.hlsl"

            CBUFFER_START(UnityPerMaterial)
                half4 _Ink, _Rim;
                float _Pull;
            CBUFFER_END

            struct A { float4 pos : POSITION; float3 normal : NORMAL; };
            struct V { float4 pos : SV_POSITION; float3 n : TEXCOORD0; float3 v : TEXCOORD1; };

            V vert(A i)
            {
                V o;
                float3 ws = TransformObjectToWorld(i.pos.xyz);
                float3 toCam = normalize(GetCameraPositionWS() - ws);
                o.n = TransformObjectToWorldNormal(i.normal);
                o.v = toCam;
                o.pos = TransformWorldToHClip(ws + toCam * _Pull);
                return o;
            }

            half4 frag(V i) : SV_Target
            {
                half rim = (half)pow(1.0 - saturate(dot(normalize(i.n), normalize(i.v))), 2.0);
                // borde con corte duro (como el resto de Nindō): adentro tinta, afuera oro
                half edge = step(0.45h, rim);
                half3 col = lerp(_Ink.rgb, _Rim.rgb * 1.5h, edge);
                return half4(col, lerp(_Ink.a, _Rim.a * 0.9h, edge));
            }
            ENDHLSL
        }
    }

    FallBack Off
}
