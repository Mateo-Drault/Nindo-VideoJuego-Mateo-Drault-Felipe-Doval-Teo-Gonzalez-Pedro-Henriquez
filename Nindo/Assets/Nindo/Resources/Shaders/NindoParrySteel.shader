// Parry de Kaito: lenguaje de ACERO (recto, filoso, instantáneo, en el plano de la cámara), distinto del aviso ensō
// de los enemigos (redondo, de pincel, en el piso, lento) pero con el mismo dorado. Antes la ventana era una media
// luna del mismo trazo que el ensō y el desvío sumaba un anillo dorado en el piso: se leían como otro aviso.
//  _Mode 0  línea de la guardia (FX/ParryCrescent): cinta a lo largo de la guardia que mira a la cámara; x = metros a lo
//           largo, y = metros a lo ancho (+y hacia arriba en pantalla). Aguja dorada mientras la ventana es perfecta,
//           acero azul frío después, con una línea de tinta debajo (se lee sobre nieve). Al aire se parte al medio y
//           se cae. Una segunda pasada la deja a media opacidad donde la tapa un cuerpo (Kaito mirando al norte).
//  _Mode 1  destello del desvío (FX/ParrySteel): quad en el plano de la cámara centrado en el choque, x = derecha de
//           la cámara. Aguja de luz horizontal con orla dorada, líneas de impacto rectas que salen (la onda corta) y,
//           en el perfecto, estrella de cuatro puntas, destellos diagonales y un abanico de púas de tinta hacia el
//           atacante. _T en segundos reales desde el choque: todos los tiempos viven acá. Corto a propósito (normal
//           0.10 s, perfecto 0.09 s de pico y apagado a los 0.15): en los dúos de Kokuyō el anillo del golpe siguiente
//           arranca 0.05 s después del que se desvía, y con 0.30 s y 3.6 m de aguja el destello le tapaba el primer
//           tercio. Con _Calm (otro aviso a la vista cerca) todo baja al 40 % y el perfecto no hace la estrella.
// Alfa premultiplicado: la tinta tapa, la luz suma (HDR, el bloom la hace brillar). Sin texto ni kanji.
// Prototipo con las mismas cuentas: scratch c2/combat-kokuyo/fix/parry2/final_proto2.py.
Shader "Nindo/ParrySteel"
{
    Properties
    {
        _Mode ("0 guardia, 1 destello", Float) = 1
        _Extent ("Medio tamaño del quad (m)", Vector) = (1.8, 1.35, 0, 0)
        _Gold ("Dorado", Color) = (1, 0.72, 0.24, 1)
        _GoldHot ("Dorado claro", Color) = (1, 0.84, 0.4, 1)
        _Steel ("Acero", Color) = (0.82, 0.9, 1, 1)
        _Ink ("Tinta", Color) = (0.07, 0.04, 0.047, 1)
        // destello
        _T ("Segundos desde el choque", Float) = 0
        _Perfect ("Perfecto", Range(0, 1)) = 0
        _Seed ("Semilla", Float) = 0
        _Aim ("Hacia el atacante (plano de la cámara)", Vector) = (1, 0, 0, 0)
        _Calm ("Otro aviso cerca (atenúa)", Range(0, 1)) = 0
        // guardia
        _Color ("Color de la línea", Color) = (1, 0.72, 0.24, 1)
        _Glow ("Intensidad", Float) = 0.95
        _Len ("Medio largo actual (m)", Float) = 0.62
        _Width ("Medio ancho (m)", Float) = 0.038
        _Occluded ("Opacidad donde la tapa un cuerpo", Range(0, 1)) = 0
        _Fade ("Opacidad", Range(0, 1)) = 1
        _Hot ("Filo blanco al medio", Range(0, 1)) = 1
        _Break ("Quiebre al aire (0..1)", Range(0, 1)) = 0
        [Enum(UnityEngine.Rendering.CompareFunction)] _ZTest ("ZTest", Float) = 8
    }

    SubShader
    {
        Tags { "RenderType" = "Transparent" "Queue" = "Transparent+40" "RenderPipeline" = "UniversalPipeline" "IgnoreProjector" = "True" }
        Blend One OneMinusSrcAlpha
        ZWrite Off
        Cull Off

        HLSLINCLUDE
        #include "Packages/com.unity.render-pipelines.universal/ShaderLibrary/Core.hlsl"

        CBUFFER_START(UnityPerMaterial)
            float4 _Extent, _Aim;
            half4 _Gold, _GoldHot, _Steel, _Ink, _Color;
            float _Mode, _T, _Perfect, _Seed, _Calm, _Glow, _Len, _Width, _Occluded, _Fade, _Hot, _Break, _ZTest;
        CBUFFER_END

        struct A { float4 pos : POSITION; float2 uv : TEXCOORD0; };
        struct V { float4 pos : SV_POSITION; float2 p : TEXCOORD0; };

        V vert(A i)
        {
            V o;
            o.pos = TransformObjectToHClip(i.pos.xyz);
            o.p = (i.uv * 2 - 1) * _Extent.xy;      // metros en el plano del quad
            return o;
        }

        float band(float d, float w, float px) { return 1 - smoothstep(w - px, w + px, d); }
        float hash1(float n) { return frac(sin(n * 12.9898 + 78.233) * 43758.5453); }

        // aguja de luz con forma de lente: hw en el centro, cero en las dos puntas
        float needle(float x, float y, float halfLen, float hw, float px)
        {
            float u = x / max(halfLen, 1e-4);
            float along = saturate(1 - u * u);
            float w = hw * pow(along, 0.75);
            return band(abs(y), w, px * 0.7) * step(1e-4, along);
        }

        float segDist(float2 p, float2 a, float2 b, out float t)
        {
            float2 ab = b - a;
            t = saturate(dot(p - a, ab) / max(dot(ab, ab), 1e-8));
            return length(p - (a + ab * t));
        }

        // La línea de la guardia. Dorado a ~1 (con más, después del tonemapping salía crema, igual que el #FFD678 de
        // StepTimeline) y un filo caliente fino del mismo color para el bloom; el acero es azul frío para que perfecto
        // y normal no se confundan; la tinta de abajo la recorta en la nieve.
        half4 Guard(float2 p, float px)
        {
            float halfLen = max(_Len, 1e-3);
            float hw = max(_Width, 1.6 * px);
            // al aire: se abre al medio y las dos mitades se caen
            float gap = _Break > 0 ? smoothstep(0.06 + 0.22 * _Break, 0.1 + 0.22 * _Break, abs(p.x) / halfLen) : 1;
            float y = p.y + 0.35 * _Break * abs(p.x) + 0.12 * _Break;
            float core = needle(p.x, y, halfLen, hw, px) * gap;
            float ink = needle(p.x, y, halfLen * 1.04, hw * 2.6 + 1.5 * px, px) * gap;
            float hot = needle(p.x, y, halfLen * 0.9, hw * 0.35, px) * gap * _Hot;
            float under = ink * (1 - core) * 0.6;
            half3 rgb = _Ink.rgb * under + _Color.rgb * _Glow * core * 0.95 + (_Color.rgb * 0.45 + 0.05) * hot;
            return half4(rgb, saturate(under + core * 0.95)) * _Fade;
        }

        half4 Flash(float2 p, float px)
        {
            float P = _Perfect, t = _T;
            float L = lerp(0.9, 1.1, P), W = lerp(0.045, 0.06, P);
            float hold = 0.09 * P, life = lerp(0.10, 0.15, P), hdr = lerp(2.6, 3.8, P);
            float kg = saturate(t / 0.035), grow = 1 - pow(1 - kg, 3);   // sale disparada y frena
            float kt = saturate((t - hold) / (life - hold));             // el perfecto aguanta lo que dura el hit-stop
            float halfLen = L * grow, hw = W * pow(1 - kt, 1.5), fade = 1 - kt;
            bool star = P > 0.5 && _Calm < 0.5;

            // 1) perfecto: abanico de púas de tinta hacia el atacante, nítidas, que se retraen hacia la punta
            float ink = 0;
            if (P > 0.5)
            {
                float baseA = atan2(_Aim.y, _Aim.x);
                float ei = 1 - pow(1 - saturate(t / life), 2);
                float out3 = 1 - pow(1 - saturate(t / 0.04), 3);
                [unroll] for (int i = 0; i < 5; i++)
                {
                    float th = baseA + (i / 4.0 - 0.5) * 2.1 + (hash1(_Seed + i) - 0.5) * 0.25;
                    float2 d = float2(cos(th), sin(th));
                    float reach = lerp(0.6, 0.9, hash1(_Seed + i * 3.1)) * out3;
                    float rIn = 0.15 + (reach - 0.15) * ei;
                    float hl = (reach - rIn) * 0.5;
                    float u = dot(p, d) - (rIn + reach) * 0.5;
                    float v = dot(p, float2(-d.y, d.x));
                    ink = max(ink, needle(u, v, hl, lerp(0.045, 0.065, hash1(_Seed + i * 7.3)), px) * step(0.01, hl));
                }
                ink *= 0.9;
            }

            // 2) aguja de acero horizontal con su orla dorada (acero tibio en el normal, blanco en el perfecto) y una
            //    lente de tinta debajo: sin ella el desvío normal (el más común) casi desaparecía sobre la nieve
            float core = needle(p.x, p.y, halfLen, max(hw, 0.6 * px * fade), px) * fade;
            float under = needle(p.x, p.y, halfLen * 1.05, hw * 2.2 + 1.5 * px, px) * fade * 0.5;
            ink = max(ink, under * (1 - core));
            half3 rgb = _Ink.rgb * ink;
            float a = ink;
            float fringe = needle(p.x, p.y, halfLen * 0.82, hw * 2.8 + px, px) * fade;
            rgb += _Gold.rgb * 2.2 * fringe * fade;
            float light = core * hdr * (1 - 0.6 * kt);
            // 3) perfecto: estrella de cuatro puntas y dos destellos diagonales (no con otro aviso cerca)
            if (star)
            {
                float st = needle(p.y, p.x, 0.5 * grow, max(hw * 0.75, 0.6 * px * fade), px) * fade;
                light = max(light, st * hdr * (1 - 0.6 * kt));
                float2 q = p * 0.70710678;
                float dg = needle(q.x + q.y, q.x - q.y, 0.22 * fade, max(hw * 0.4, px), px)
                         + needle(q.x - q.y, q.x + q.y, 0.22 * fade, max(hw * 0.4, px), px);
                rgb += _GoldHot.rgb * 2.0 * fade * dg;
            }
            rgb += light * lerp(half3(1.0, 0.92, 0.74), half3(1.0, 0.97, 0.92), P);
            a = saturate(a + core * 0.6);

            // 4) la onda corta: líneas de impacto rectas que salen del choque, más largas a lo largo de la aguja
            float ll = lerp(0.09, 0.12, P);
            if (t < ll)
            {
                float k = t / ll, e = 1 - (1 - k) * (1 - k);
                float n = lerp(8, 12, P);
                float r0 = 0.2, r1 = lerp(0.6, 0.75, P), lnBase = lerp(0.25, 0.32, P);
                float lines = 0;
                [unroll] for (int j = 0; j < 12; j++)
                {
                    float on = step(j + 0.5, n);
                    float th = (j + (hash1(_Seed * 3 + j) - 0.5) * 0.35) / n * 6.2831853;
                    float2 d = float2(cos(th), sin(th));
                    float ra = r0 + (r1 - r0) * e;
                    float rb = ra + lnBase * (0.6 + 0.8 * abs(d.x)) * (1 - k);
                    float tt;
                    float dd = segDist(p, d * ra, d * rb, tt);
                    lines = max(lines, band(dd, 1.3 * px * (1 - tt * 0.7) * (1 - k * 0.5), px * 0.7) * on);
                }
                rgb += lerp(_Steel.rgb, _GoldHot.rgb, P) * 1.8 * (1 - k) * lines;
            }
            return half4(rgb, a) * (1 - 0.6 * _Calm);
        }

        half4 Shade(V i)
        {
            // tamaño del píxel en metros (las derivadas fuera de los if). En la cinta de la guardia vale el de lo
            // ancho: a lo largo puede estar escorzada y el antialias de los anchos quedaría borroso
            float pxx = fwidth(i.p.x), pxy = max(fwidth(i.p.y), 1e-5);
            if (_Mode < 0.5) return Guard(i.p, pxy);
            return Flash(i.p, max(pxx, pxy));
        }
        ENDHLSL

        Pass
        {
            Name "ParrySteel"
            Tags { "LightMode" = "UniversalForward" }
            ZTest [_ZTest]
            HLSLPROGRAM
            #pragma vertex vert
            #pragma fragment frag
            half4 frag(V i) : SV_Target { return Shade(i); }
            ENDHLSL
        }

        // La guardia detrás del cuerpo de Kaito (mirando hacia el norte, donde suelen estar los jefes) o de quien se
        // le cruce: a media opacidad en vez de desaparecer. Solo donde la primera pasada falló la prueba de
        // profundidad, así nunca se dibuja dos veces; el destello (ZTest Always) la apaga con _Occluded = 0.
        Pass
        {
            Name "ParrySteelOccluded"
            Tags { "LightMode" = "SRPDefaultUnlit" }
            ZTest Greater
            HLSLPROGRAM
            #pragma vertex vert
            #pragma fragment frag
            half4 frag(V i) : SV_Target
            {
                if (_Occluded <= 0) discard;
                return Shade(i) * _Occluded;
            }
            ENDHLSL
        }
    }
}
