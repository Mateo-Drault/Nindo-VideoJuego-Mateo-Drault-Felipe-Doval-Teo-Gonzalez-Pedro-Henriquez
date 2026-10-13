"""Herramientas de malla de Chikuō: un MeshBuilder por pieza (un hueso, o varios con pesos) con primitivas
facetadas para un personaje de tela y piel (tubos de sección propia, cintas con espesor, cajas orientadas).

Son las mismas ideas que el kit de Kokuyō (bosses/kokuyo/kokuyo_model.Kit) sin las lamas de armadura: acá las
formas se ahusan y se biselan con anillos (nada de ladrillos) y las articulaciones llevan un anillo de más
para que doblen limpio (los pesos los reparte la función 'weights' de cada pieza).
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

    def tag(self, faces, color, slot=None):
        self._tag(faces, color, slot, None)
        if slot is not None:
            for f in faces:
                f.material_index = slot

    # ------------------------------------------------------------------ primitivas
    def rings_loft(self, rings, color, cap0=True, cap1=True, ring_colors=None, slot=None):
        """Une anillos (listas de puntos con la misma cantidad); ring_colors[i] pinta el tramo i -> i+1."""
        part = self.loft(rings, color, cap_start=cap0, cap_end=cap1)
        if slot is not None:
            self.tag(part.faces, color, slot)
        if ring_colors:
            vr = part.verts
            n = len(rings[0])
            for f in part.faces:
                idx = sorted(vr.index(v) // n for v in f.verts if v in vr)
                if not idx:
                    continue
                seg = min(idx[0], len(ring_colors) - 1)
                col = ring_colors[seg]
                if col:
                    if isinstance(col, tuple):
                        self.tag([f], col[0], col[1])
                    else:
                        self.tag([f], col, slot)
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

    def strip(self, pts, widths, normal_hint, color, thick=0.03, slot=None):
        """Cinta con espesor a lo largo de una polilínea (cejas, colas de tela). La cara ancha mira a 'normal_hint'."""
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
        return self.rings_loft(rings, color, True, True, None, slot)

    def gem(self, center, r, color, sides=6, height=None, axis=(0, 0, 1), slot=None):
        """Bolita facetada (botones, el rodete): bipirámide de 'sides' lados."""
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


def mirror_weights(fr):
    if fr is None:
        return None

    def wf(co):
        w = fr(Vector((-co.x, co.y, co.z)))
        out = {}
        for n, v in w.items():
            ln = n
            if n.endswith("_R"):
                ln = n[:-2] + "_L"
            elif "_R_" in n:
                ln = n.replace("_R_", "_L_", 1)
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
    """Puntos de una pieza continua que recorre una cadena de huesos (colas de la faja, bigotes): la mitad de
    cada tramo y un anillo de más a 'span' metros a cada lado de cada articulación interior, para que doble en una curva
    y no en un escalón. Devuelve (puntos, tramo de cada segmento entre puntos)."""
    J = [Vector(p) for p in joints]
    pts, seg = [J[0]], []
    n = len(J) - 2
    for i in range(len(J) - 1):
        a, b = J[i], J[i + 1]
        L = (b - a).length
        u = (b - a) / L
        s = min(span, L * 0.3)
        stops = ([s] if i > 0 else []) + [L * 0.5] + ([L - s] if i < n else []) + [L]
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
        L = (J[i + 1] - J[i]).length
        x0 = t * L                     # metros desde la cabeza del tramo
        x1 = (1.0 - t) * L             # metros hasta la cola
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
