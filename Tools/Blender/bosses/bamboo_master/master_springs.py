"""Resortes horneados de Chikuō: nindo_anim.run_springs con el giro final corregido.

En nindo_anim.run_springs la orientación que se graba es el giro de la punta simulada respecto del objetivo YA corregido
(colgar con 'hang', subir sobre el piso) aplicado a la orientación RÍGIDA del hueso: cuando 'hang' o el piso mueven el
objetivo, el hueso sale apuntando como el rígido más el desvío dinámico, no a la punta simulada. En una postura baja
(la barrida, el caballo hondo) la cola de la faja rígida queda 20 cm bajo el piso aunque la simulación la tenga arriba.
Acá el giro va de la dirección rígida a la simulada. Se deja nindo_anim como está porque Kokuyō hornea con él (cambiar
el módulo compartido le movería la faja y la cinta al próximo export de otro frente).
"""
import math
from mathutils import Vector, Matrix
import nindo_anim as NA
from nindo_anim import FPS, compose, rot3, slerp_dir, V, Pose


def run_springs(rig, frames, springs, root_offsets, loop=False, preroll=1.0, substeps=4, floor_offsets=None):
    """Igual que nindo_anim.run_springs (mismos parámetros y simulación) salvo el giro que se graba: ver el docstring."""
    n = len(frames)
    if n == 0 or not springs:
        return
    order = []
    for s in springs:
        order += s.bones
    spring_of = {b: s for s in springs for b in s.bones}
    riders = []
    for b in order:
        for c in rig.subtree(b)[1:]:
            if c not in spring_of and c not in riders:
                riders.append(c)
    prim = [dict(W) for W in frames]

    def base_of(W, b):
        p = rig.parent[b]
        return (W[p] @ rig.rel[b]).inverted() @ W[b] if p else rig.rest_inv[b] @ W[b]

    state = {}
    dt = 1.0 / FPS / substeps
    cyc = n - 1 if loop and n > 1 else n
    seq = ([i % cyc for i in range(cyc * 2)] + list(range(cyc))) if loop else ([0] * int(preroll * FPS) + list(range(n)))
    record_from = len(seq) - cyc
    shift = (root_offsets[cyc] - root_offsets[0]) if loop and n > 1 else Vector()

    def solve_frame(fi, lap=0):
        P = prim[fi]
        fo = floor_offsets[fi] if floor_offsets else 0.0
        Wc = dict(P)
        off = Matrix.Translation(root_offsets[fi] + shift * lap)
        offi = off.inverted()
        spheres = {}
        for b in order:
            s = spring_of[b]
            sph = []
            for cb, cl, cr in s.colliders:
                key = (cb, tuple(cl))
                if key not in spheres:
                    spheres[key] = off @ (P[cb] @ V(cl))
                sph.append((spheres[key], cr))
            p = rig.parent[b]
            Fp = (off @ Wc[p]) if p else off
            F = Fp @ rig.rel[b] @ base_of(P, b)
            if s.follow and b == s.bones[0]:
                Rf = rot3(off @ P[s.follow]) @ rot3(rig.rest_inv[s.follow] @ rig.rest[b])
                F = compose(F.translation, Rf)
            if s.push:
                q = s.push(P, b)
                if q is not None:
                    F = compose(F.translation, q.to_matrix() @ rot3(F))
            h = F.translation
            L = rig.length[b]
            t = F @ Vector((0.0, L, 0.0))
            f_dir = (t - h).normalized()
            if s.hang > 0.0:
                hd = slerp_dir(f_dir, Vector((0.0, 0.0, -1.0)), s.hang)
                t = h + hd * L
            fl = None if s.floor is None else s.floor + fo
            if fl is not None and t.z < fl:
                t.z = fl
                dv = t - h
                t = h + dv.normalized() * L if dv.length > 1e-6 else t
            st = state.get(b)
            if st is None:
                st = state[b] = [t.copy(), t.copy(), t.copy()]
            x, xp, tp = st
            vt = (t - tp) / substeps
            for _ in range(substeps):
                acc = (t - x) * s.k + Vector((0.0, 0.0, -s.grav))
                xn = x + (x - xp) * (1.0 - s.damp) + vt * s.damp + acc * dt * dt
                dirn = xn - h
                if dirn.length < 1e-6:
                    dirn = t - h
                xn = h + dirn.normalized() * L
                for cc, cr in sph:
                    dv = xn - cc
                    if dv.length < cr:
                        xn = cc + dv.normalized() * cr
                        dirn = xn - h
                        if dirn.length > 1e-6:
                            xn = h + dirn.normalized() * L
                if fl is not None and xn.z < fl:
                    xn.z = fl
                    dirn = xn - h
                    if dirn.length > 1e-6:
                        xn = h + dirn.normalized() * L
                xp, x = x, xn
            a = (x - h).normalized()
            b0 = (t - h).normalized()
            ang = math.degrees(a.angle(b0)) if a.length > 0 and b0.length > 0 else 0.0
            if ang > s.max_deg:
                x = h + slerp_dir(b0, a, s.max_deg / ang) * L
                # el tope no puede devolverla bajo el piso
                if fl is not None and x.z < fl:
                    x.z = fl
                    x = h + (x - h).normalized() * L
            st[0], st[1], st[2] = x, xp, t.copy()
            # el giro va de la dirección RÍGIDA del hueso a la punta simulada (ver el docstring)
            q = f_dir.rotation_difference((x - h).normalized())
            Wc[b] = offi @ compose(h, q.to_matrix() @ rot3(F))
        for c in riders:
            Wc[c] = Wc[rig.parent[c]] @ rig.rel[c] @ base_of(P, c)
        return Wc

    for i, fi in enumerate(seq):
        Wc = solve_frame(fi, i // cyc if loop else 0)
        if i >= record_from:
            frames[fi] = Wc
    if loop and n > 1:
        frames[n - 1] = dict(frames[0])


def bake_clip(rig, clip, solve, springs=(), preroll=1.0):
    """nindo_anim.bake_clip con estos resortes."""
    frames, ctrls, roots = [], [], []
    if getattr(clip, "prepare", None):
        clip.prepare(clip, rig, solve)
    for f in range(clip.frames + 1):
        c = clip.controls(f)
        pose = Pose(rig)
        solve(pose, c)
        for nme in rig.names:
            pose.get(nme)
        frames.append(pose.W)
        ctrls.append(c)
        roots.append(Vector((0.0, -(c.get("travel") or 0.0), 0.0)) + clip.root_vel * (f / FPS))
    lifts = [min(0.0, c.get("lift") or 0.0) for c in ctrls]
    run_springs(rig, frames, list(springs), roots, loop=clip.loop, preroll=preroll, floor_offsets=lifts)
    if clip.loop:
        frames[-1] = {nme: m.copy() for nme, m in frames[0].items()}
    return frames, ctrls, roots
