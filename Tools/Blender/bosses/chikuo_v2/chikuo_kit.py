"""Herramientas de malla del Chikuō ermitaño: un MeshBuilder por pieza (un hueso, o varios con pesos) con primitivas
facetadas para un personaje de tela, piel, pelo y hojas.

Parte del kit del Chikuō anterior (bosses/bamboo_master/master_kit.py: tubos de sección propia, cintas con espesor,
cajas orientadas, pesos repartidos en las articulaciones) y suma lo que pide el ermitaño:
  * hojas de bambú cerradas (una pirámide baja arriba y una cara plana abajo: CharacterLit descarta las caras de atrás,
    así que una hoja de una sola cara desaparecía al mirarla desde abajo o de canto);
  * púas (las cejas salvajes, los mechones de las sienes, el moño facetado);
  * anillos con radio por ángulo (la cabeza, el pantalón que se infla más afuera que adentro).
Las piezas viejas no se importan: ese pipeline se reemplaza entero y este no tiene que depender de él.
"""
import math
import bmesh
from mathutils import Vector, Matrix
import nindo_lib as L


class Kit(L.MeshBuilder):
    def __init__(self, name, bone, seed=1, weights=None):
        super().__init__(name, seed)
        self.bone = bone
        self.weights = weights      # función(co) -> {hueso: peso} para piezas que doblan
        self.anchor = None          # capa 'anchor': el punto donde se miden los pesos de una pieza rígida (las hojas)

    def use_anchors(self):
        """Las hojas que se agreguen desde acá se pesan enteras en un punto (no se estiran entre dos paños de la capa: se
        mueven como tejas duras). Los demás vértices se pesan donde están (anchor en (0, 0, 0))."""
        self.anchor = self.bm.verts.layers.float_vector.new("anchor")

    def tag(self, faces, color, slot=None):
        """Pinta caras con un color de la paleta (y su slot) o con un material propio ('slot'). Siempre fija el slot: una
        cara de una pieza que brilla repintada con un color de la paleta vuelve a la paleta (si no, el vendado de la
        flauta y los nudos de los cascabeles quedaban del material del caño)."""
        self._tag(faces, color, slot, None)
        idx = slot if slot is not None else (L.SLOT_EMISSIVE if color.startswith("glow_") else L.SLOT_PALETTE)
        for f in faces:
            f.material_index = idx

    # ------------------------------------------------------------------ primitivas
    def rings_loft(self, rings, color, cap0=True, cap1=True, ring_colors=None, slot=None, closed=True):
        """Une anillos (listas de puntos con la misma cantidad); ring_colors[i] pinta el tramo i -> i+1 (un nombre de la
        paleta, o (nombre, slot) para un material propio)."""
        part = self.loft(rings, color, cap_start=cap0, cap_end=cap1, closed=closed)
        if slot is not None:
            self.tag(part.faces, color, slot)
        if ring_colors:
            vr = part.verts
            n = len(rings[0])
            idx_of = {v: i // n for i, v in enumerate(vr)}
            for f in part.faces:
                idx = sorted(idx_of[v] for v in f.verts if v in idx_of)
                if not idx:
                    continue
                col = ring_colors[min(idx[0], len(ring_colors) - 1)]
                if col:
                    if isinstance(col, tuple):
                        self.tag([f], col[0], col[1])
                    else:
                        self.tag([f], col)
        return part

    def tube(self, pts, radii, sides, color, ups=None, phase=0.0, cap0=True, cap1=True, ring_colors=None, power=2.0, slot=None):
        """Tubo facetado por una polilínea; radii[i] = r o (rx, ry) (ry según 'ups'). power > 2 da secciones
        más cuadradas, < 2 más en rombo."""
        pts = [Vector(p) for p in pts]
        rings = []
        for i, p in enumerate(pts):
            t = (pts[min(i + 1, len(pts) - 1)] - pts[max(i - 1, 0)]).normalized()
            up = Vector(ups[i]) if ups else (Vector((0, -1, 0)) if abs(t.y) < 0.9 else Vector((0, 0, 1)))
            yv = (up - t * up.dot(t)).normalized()
            xv = yv.cross(t).normalized()
            r = radii[i]
            rx, ry = (r, r) if not isinstance(r, (tuple, list)) else r
            ring = []
            for k in range(sides):
                a = phase + 2.0 * math.pi * k / sides
                ca, sa = math.cos(a), math.sin(a)
                e = 2.0 / power
                cx = math.copysign(abs(ca) ** e, ca)
                cy = math.copysign(abs(sa) ** e, sa)
                ring.append(p + xv * (rx * cx) + yv * (ry * cy))
            rings.append(ring)
        return self.rings_loft(rings, color, cap0, cap1, ring_colors, slot)

    def obox(self, center, size, x_axis, y_axis, color, bevel=0.0, up_color=None, up_thresh=0.45, slot=None):
        """Caja orientada (ejes x, y; z = x × y) con chaflán opcional."""
        X = Vector(x_axis).normalized()
        Y = Vector(y_axis)
        Y = (Y - X * Y.dot(X)).normalized()
        Z = X.cross(Y)
        R = Matrix((X, Y, Z)).transposed().to_4x4()
        M = Matrix.Translation(Vector(center)) @ R @ Matrix.Diagonal((size[0], size[1], size[2], 1.0))
        r = bmesh.ops.create_cube(self.bm, size=1.0, matrix=M)
        part = self._new(r["verts"], color, None, None)
        if bevel > 0.0:
            faces0 = part.faces
            edges = list({e for f in faces0 for e in f.edges})
            res = bmesh.ops.bevel(self.bm, geom=edges + part.verts, offset=bevel, segments=1, affect='EDGES',
                                  offset_type='OFFSET', profile=0.5, clamp_overlap=True)
            fs = [f for f in faces0 if f.is_valid] + list(res.get("faces", []))
            part = L.Part(self, list({v for f in fs for v in f.verts}))
            self.tag(part.faces, color)
        if slot is not None:
            self.tag(part.faces, color, slot)
        if up_color:
            self.up_shade(part, up_color, up_thresh)
        return part

    def up_shade(self, part, color, thresh=0.45, slot=None):
        for f in part.faces:
            f.normal_update()
            if f.normal.z > thresh:
                self.tag([f], color, slot)
        return part

    def strip(self, pts, widths, normal_hint, color, thick=0.03, slot=None, ring_colors=None):
        """Cinta con espesor a lo largo de una polilínea (ribetes, colas de tela). La cara ancha mira a 'normal_hint'."""
        pts = [Vector(p) for p in pts]
        rings = []
        for i, p in enumerate(pts):
            t = (pts[min(i + 1, len(pts) - 1)] - pts[max(i - 1, 0)]).normalized()
            nh = Vector(normal_hint[i] if isinstance(normal_hint, list) else normal_hint)
            nv = (nh - t * nh.dot(t)).normalized()
            wv = t.cross(nv).normalized()
            w = widths[i] * 0.5
            th = (thick[i] if isinstance(thick, (list, tuple)) else thick) * 0.5
            rings.append([p + wv * w + nv * th, p - wv * w + nv * th, p - wv * w - nv * th, p + wv * w - nv * th])
        return self.rings_loft(rings, color, True, True, ring_colors, slot)

    def gem(self, center, r, color, sides=6, height=None, axis=(0, 0, 1), slot=None):
        """Bolita facetada: bipirámide de 'sides' lados."""
        c = Vector(center)
        ax = Vector(axis).normalized()
        h = r if height is None else height
        xv = ax.orthogonal().normalized()
        yv = ax.cross(xv)
        ring = [c + (xv * math.cos(2 * math.pi * k / sides) + yv * math.sin(2 * math.pi * k / sides)) * r for k in range(sides)]
        vt = self.bm.verts.new(c + ax * h)
        vb = self.bm.verts.new(c - ax * h)
        vr = [self.bm.verts.new(p) for p in ring]
        for k in range(sides):
            j = (k + 1) % sides
            self.bm.faces.new((vr[k], vr[j], vt))
            self.bm.faces.new((vr[j], vr[k], vb))
        return self._new(vr + [vt, vb], color, slot, None)

    def spike(self, base, tip, r, color, sides=4, side_hint=(0, 0, 1), flat=1.0, phase=0.0, slot=None):
        """Púa facetada (pirámide cerrada: la base queda adentro de la cabeza o del pelo, pero cerrada el cálculo de
        normales no la da vuelta). 'flat' < 1 la aplasta en el eje de 'side_hint' (las plumas de las cejas son más anchas
        que gruesas)."""
        b, t = Vector(base), Vector(tip)
        ax = (t - b).normalized()
        h = Vector(side_hint)
        yv = (h - ax * h.dot(ax))
        if yv.length < 1e-6:
            yv = ax.orthogonal()
        yv.normalize()
        xv = yv.cross(ax).normalized()
        ring = []
        for k in range(sides):
            a = phase + 2 * math.pi * k / sides
            ring.append(self.bm.verts.new(b + xv * (math.cos(a) * r) + yv * (math.sin(a) * r * flat)))
        vt = self.bm.verts.new(t)
        for k in range(sides):
            self.bm.faces.new((ring[k], ring[(k + 1) % sides], vt))
        self.bm.faces.new(list(reversed(ring)))
        return self._new(ring + [vt], color, slot, None)

    def leaf(self, base, tip, normal, width, color, ridge=0.35, under=None, slot=None, bend=0.0, wide=0.40):
        """Hoja de bambú cerrada: borde de 4 puntos (base, los costados a 'wide' del largo, punta), lomo levantado
        'ridge' x ancho hacia 'normal' (dos pares de caras facetadas arriba) y una cara plana abajo. 'bend' arquea la
        punta hacia afuera (m). 6 triángulos."""
        b, t = Vector(base), Vector(tip)
        d = t - b
        Ln = d.length
        ax = d / Ln
        n = Vector(normal)
        n = (n - ax * n.dot(ax)).normalized()
        sv = ax.cross(n).normalized()
        t = t + n * bend
        m = b + d * wide
        w = width * 0.5
        vb = self.bm.verts.new(b)
        vt = self.bm.verts.new(t)
        vl = self.bm.verts.new(m + sv * w)
        vr = self.bm.verts.new(m - sv * w)
        vc = self.bm.verts.new(b + d * 0.45 + n * (width * ridge))
        f = self.bm.faces.new
        f((vb, vl, vc)); f((vl, vt, vc)); f((vt, vr, vc)); f((vr, vb, vc))
        f((vb, vr, vt)); f((vb, vt, vl))
        if self.anchor is not None:
            a = b + d * 0.4
            for v in (vb, vt, vl, vr, vc):
                v[self.anchor] = a
        p = self._new([vb, vt, vl, vr, vc], color, slot, None)
        if under:
            for fc in p.faces:
                fc.normal_update()
                if fc.normal.dot(n) < 0.0:
                    self.tag([fc], under, slot)
        return p


def mirror_kit(src, name, bone, weights=None):
    """Copia espejada (x -> -x) de una pieza derecha para el lado izquierdo, con su propio hueso."""
    k = Kit(name, bone, weights=weights)
    k.bm.free()
    k.bm = src.bm.copy()
    k.uv = k.bm.loops.layers.uv.get("UVMap")
    k.col = k.bm.loops.layers.color.get("Col")
    for v in k.bm.verts:
        v.co.x = -v.co.x
    bmesh.ops.reverse_faces(k.bm, faces=k.bm.faces)
    return k


def side_name(n):
    """'Hand_R' -> 'Hand_L', 'Index_R_2' -> 'Index_L_2'; lo que no es de un lado queda igual."""
    if n.endswith("_R"):
        return n[:-2] + "_L"
    if "_R_" in n:
        return n.replace("_R_", "_L_", 1)
    return n


def mirror_weights(fr, name_map=side_name):
    if fr is None:
        return None

    def wf(co):
        w = fr(Vector((-co.x, co.y, co.z)))
        out = {}
        for n, v in w.items():
            ln = name_map(n)
            out[ln] = out.get(ln, 0.0) + v
        return out
    return wf


def tri_count(obj):
    return sum(len(p.vertices) - 2 for p in obj.data.polygons)


def smooth01(t):
    t = max(0.0, min(1.0, t))
    return t * t * (3.0 - 2.0 * t)


def along_bone(co, head, tail):
    """Parámetro de 'co' a lo largo del segmento head -> tail (0 en la cabeza, 1 en la cola)."""
    d = tail - head
    return (co - head).dot(d) / max(1e-6, d.length_squared)


def chain_samples(joints, span):
    """Puntos de una pieza continua que recorre una cadena de huesos (la barba, las colas de la faja): la mitad de
    cada tramo y un anillo de más a 'span' metros a cada lado de cada articulación interior, para que doble en una curva
    y no en un escalón. Devuelve (puntos, tramo de cada segmento entre puntos)."""
    J = [Vector(p) for p in joints]
    pts, seg = [J[0]], []
    n = len(J) - 2
    for i in range(len(J) - 1):
        a, b = J[i], J[i + 1]
        Ln = (b - a).length
        u = (b - a) / Ln
        s = min(span, Ln * 0.3)
        stops = ([s] if i > 0 else []) + [Ln * 0.5] + ([Ln - s] if i < n else []) + [Ln]
        for d in stops:
            pts.append(a + u * d)
            seg.append(i)
    return pts, seg


def chain_weights(joints, bones, before=None, after=None, span=0.06):
    """Pesos de un tubo continuo que recorre varios huesos seguidos (hombro -> codo -> muñeca): cada vértice va al
    tramo más cercano y en cada articulación interior se reparte 50/50 con una rampa de 'span' metros a cada lado (el
    anillo del codo dobla limpio, sin quebrarse ni aplastarse). 'before'/'after' mezclan las puntas con el hueso de
    antes y el de después (clavícula, mano)."""
    J = [Vector(p) for p in joints]

    def wf(co):
        best = None
        for i in range(len(bones)):
            a, b = J[i], J[i + 1]
            t = along_bone(co, a, b)
            tc = min(1.0, max(0.0, t))
            d = (co - (a + (b - a) * tc)).length
            if best is None or d < best[0]:
                best = (d, i, t)
        _, i, t = best
        Ln = (J[i + 1] - J[i]).length
        x0 = t * Ln
        x1 = (1.0 - t) * Ln
        prev = bones[i - 1] if i > 0 else before
        nxt = bones[i + 1] if i + 1 < len(bones) else after
        if prev and x0 < span:
            a = 0.5 * smooth01((span - x0) / span)
            return {bones[i]: 1.0 - a, prev: a}
        if nxt and x1 < span:
            a = 0.5 * smooth01((span - x1) / span)
            return {bones[i]: 1.0 - a, nxt: a}
        return {bones[i]: 1.0}
    return wf


def blend(*pairs):
    """Suma pesos {hueso: peso} * factor: blend((w1, 0.3), (w2, 0.7))."""
    out = {}
    for w, k in pairs:
        if k <= 0.0:
            continue
        for n, v in w.items():
            out[n] = out.get(n, 0.0) + v * k
    return out
