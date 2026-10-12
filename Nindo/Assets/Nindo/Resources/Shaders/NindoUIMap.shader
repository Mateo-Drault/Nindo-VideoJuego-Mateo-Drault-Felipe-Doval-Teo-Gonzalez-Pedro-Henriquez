// Mapa del mundo de Nindō (UI/UIMap.cs): la lámina pintada (Resources/UI/WorldMap.jpg) bajo la niebla de lo no
// explorado. La niebla es tinta aguada que respira:
//  * dónde hay niebla lo dice _FogTex (Alpha8, una celda de 4 m por texel, 255 = sin explorar, ya desenfocada por
//    MapFog): su borde se deforma ±3 m con ruido y la fibra del papel, así no se ve la grilla;
//  * la niebla son nubes de tinta (dos capas que se mueven despacio en sentidos opuestos, con el lomo que da a la luna
//    del noroeste más claro) y, encima, las líneas de las nubes kasumi de los biombos, cada una en su lugar;
//  * donde la tinta de la niebla se seca contra lo explorado se junta el pigmento (la línea de marea de la aguada);
//  * al abrir el mapa lo descubierto desde la última vez se despeja a manchas (_FogPrev -> _FogTex con _Reveal);
//  * el borde rasgado del papel arriba y abajo (los costados van contra las varillas del pergamino).
// Todo en el espacio de color del proyecto (Gamma): la misma cuenta que Tools/UI/world_map_preview.py composite(),
// que es donde se juzga sin Unity. _T = tiempo sin escala. Basado en UI/Default (máscaras, RectMask2D con suavizado).
Shader "Nindo/UI Map"
{
    Properties
    {
        [PerRendererData] _MainTex ("Lámina", 2D) = "white" {}
        _Color ("Tinte", Color) = (1, 1, 1, 1)
        _FogTex ("Niebla (Alpha8)", 2D) = "black" {}
        _FogPrev ("Niebla al cerrar (Alpha8)", 2D) = "black" {}
        _MistTex ("Niebla: R fibra, G nubes, B kasumi, A deformación", 2D) = "gray" {}
        _SheetM ("Lámina en metros (x, z)", Vector) = (516, 428, 0, 0)
        _MistK ("Repeticiones por lámina (nubes finas, nubes gruesas)", Vector) = (2.69, 1.58, 0, 0)
        _FogLight ("Niebla clara", Color) = (0.34, 0.36, 0.43, 1)
        _FogDark ("Niebla oscura", Color) = (0.19, 0.2, 0.26, 1)
        _Kasumi ("Líneas kasumi (a = fuerza)", Color) = (0.8, 0.77, 0.68, 0.45)
        _Tide ("Línea de marea (a = fuerza)", Color) = (0.045, 0.04, 0.065, 0.62)
        _Reveal ("Lo nuevo se despeja (0..1)", Range(0, 1)) = 1
        _T ("Tiempo sin escala", Float) = 0

        _StencilComp ("Stencil Comparison", Float) = 8
        _Stencil ("Stencil ID", Float) = 0
        _StencilOp ("Stencil Operation", Float) = 0
        _StencilWriteMask ("Stencil Write Mask", Float) = 255
        _StencilReadMask ("Stencil Read Mask", Float) = 255
        _ColorMask ("Color Mask", Float) = 15
        [Toggle(UNITY_UI_ALPHACLIP)] _UseUIAlphaClip ("Use Alpha Clip", Float) = 0
    }

    SubShader
    {
        Tags { "Queue" = "Transparent" "IgnoreProjector" = "True" "RenderType" = "Transparent" "PreviewType" = "Plane" "CanUseSpriteAtlas" = "True" }
        Stencil
        {
            Ref [_Stencil]
            Comp [_StencilComp]
            Pass [_StencilOp]
            ReadMask [_StencilReadMask]
            WriteMask [_StencilWriteMask]
        }
        Cull Off
        Lighting Off
        ZWrite Off
        ZTest [unity_GUIZTestMode]
        Blend One OneMinusSrcAlpha
        ColorMask [_ColorMask]

        Pass
        {
            Name "Default"
        CGPROGRAM
            #pragma vertex vert
            #pragma fragment frag
            #pragma target 3.0
            #include "UnityCG.cginc"
            #include "UnityUI.cginc"
            #pragma multi_compile_local _ UNITY_UI_CLIP_RECT
            #pragma multi_compile_local _ UNITY_UI_ALPHACLIP

            struct appdata_t
            {
                float4 vertex : POSITION;
                float4 color : COLOR;
                float2 texcoord : TEXCOORD0;
                UNITY_VERTEX_INPUT_INSTANCE_ID
            };

            struct v2f
            {
                float4 vertex : SV_POSITION;
                fixed4 color : COLOR;
                float2 uv : TEXCOORD0;
                float4 mask : TEXCOORD1;
                UNITY_VERTEX_OUTPUT_STEREO
            };

            sampler2D _MainTex;
            float4 _MainTex_ST;
            sampler2D _FogTex, _FogPrev, _MistTex;
            fixed4 _Color;
            fixed4 _TextureSampleAdd;
            float4 _ClipRect;
            float _UIMaskSoftnessX, _UIMaskSoftnessY;
            float4 _SheetM, _MistK;
            fixed4 _FogLight, _FogDark, _Kasumi, _Tide;
            float _Reveal, _T;

            v2f vert(appdata_t v)
            {
                v2f o;
                UNITY_SETUP_INSTANCE_ID(v);
                UNITY_INITIALIZE_VERTEX_OUTPUT_STEREO(o);
                float4 pos = UnityObjectToClipPos(v.vertex);
                o.vertex = pos;
                o.uv = TRANSFORM_TEX(v.texcoord, _MainTex);
                o.color = v.color * _Color;
                // recorte del RectMask2D con su borde suave (igual que UI/Default)
                float2 pixelSize = pos.w;
                pixelSize /= abs(mul((float2x2)UNITY_MATRIX_P, _ScreenParams.xy));
                float4 clampedRect = clamp(_ClipRect, -2e10, 2e10);
                o.mask = float4(v.vertex.xy * 2 - clampedRect.xy - clampedRect.zw, 0.25 / (0.25 * half2(_UIMaskSoftnessX, _UIMaskSoftnessY) + abs(pixelSize.xy)));
                return o;
            }

            fixed4 frag(v2f i) : SV_Target
            {
                float2 uv = i.uv;
                half3 sheet = (tex2D(_MainTex, uv) + _TextureSampleAdd).rgb;

                // _MistTex cubre la lámina una vez: las kasumi (B) se leen así, cada banda en su lugar; la fibra, las
                // nubes y la deformación, a las escalas _MistK (no se alinean entre sí: no se ve que se repiten).
                // Todo se corre despacio a 0.58 m/s, las nubes gruesas al revés
                float2 drift = float2(_T * 0.58 / _SheetM.x, 0);
                half4 m1 = tex2D(_MistTex, uv * _MistK.x + drift * _MistK.x);
                half4 m1l = tex2D(_MistTex, uv * _MistK.x + drift * _MistK.x + float2(-1.15, 1.15) * _MistK.x / _SheetM.xy);   // hacia la luna
                half4 m2 = tex2D(_MistTex, uv * _MistK.y - drift * _MistK.y + float2(0, 0.37));
                half4 m3 = tex2D(_MistTex, uv + drift);

                // dónde hay niebla: la grilla deformada y con el borde que se abre a manchas al descubrir
                float2 fuv = uv + (float2(m1.a, m2.a) - 0.5) * (6.0 / _SheetM.xy);
                float fogNow = tex2D(_FogTex, fuv).a;
                float fogPrev = tex2D(_FogPrev, fuv).a;
                float wipe = smoothstep(m2.g - 0.18, m2.g + 0.18, _Reveal * 1.36 - 0.18);
                float fog = lerp(fogPrev, fogNow, wipe);
                float F = smoothstep(0.22, 0.78, fog + (m1.r - 0.5) * 0.12 + (m1.g - 0.5) * 0.30);

                // la niebla: nubes de tinta con el lomo de la luna, más cargada contra el borde del papel, y las kasumi
                float bill = saturate(m1.g * 0.6 + m2.g * 0.5 - 0.1);
                half3 fogCol = lerp(_FogLight.rgb, _FogDark.rgb, bill);
                float ey = min(uv.y, 1.0 - uv.y) * _SheetM.y;      // metros al borde de arriba o de abajo
                fogCol *= (0.94 + 0.12 * m1.r) * (0.86 + 0.14 * smoothstep(0.0, 36.0, ey));
                float lit = (m1.g - m1l.g) * 5.0;
                fogCol += saturate(lit) * 0.07 - saturate(-lit) * 0.035;
                float kas = m3.b * _Kasumi.a * (0.35 + 0.65 * smoothstep(0.2, 0.6, m2.g));
                fogCol = lerp(fogCol, _Kasumi.rgb, kas);

                // línea de marea: el pigmento que se junta donde la aguada se seca, cortada por la fibra
                float tide = smoothstep(0.02, 0.32, F) * (1.0 - smoothstep(0.32, 0.85, F));
                tide *= saturate(0.35 + m1.r * 0.8 + (m2.a - 0.5) * 0.8);

                half3 col = lerp(sheet, fogCol, F);
                col = lerp(col, _Tide.rgb, tide * _Tide.a);

                // borde rasgado de arriba y abajo
                float dk = 3.2 + (m3.a - 0.5) * 2.6 + (m1.r - 0.5) * 0.5;
                float aa = max(fwidth(ey) * 1.2, 1e-4);
                half alpha = smoothstep(dk - aa, dk + aa, ey) * i.color.a;

                half4 o;
                o.rgb = col * i.color.rgb * alpha;
                o.a = alpha;
                #ifdef UNITY_UI_CLIP_RECT
                half2 m = saturate((_ClipRect.zw - _ClipRect.xy - abs(i.mask.xy)) * i.mask.zw);
                o *= m.x * m.y;
                #endif
                #ifdef UNITY_UI_ALPHACLIP
                clip(o.a - 0.001);
                #endif
                return o;
            }
        ENDCG
        }
    }
}
