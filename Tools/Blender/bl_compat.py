"""
Compatibilidad del pipeline con Blender 5 (las herramientas se escribieron para 4.4).

Blender 5.0 sacó la API vieja de acciones: Action.fcurves / Action.groups ya no existen y las curvas viven en una
"channelbag" por slot (acciones con capas). Este módulo vuelve a poner Action.fcurves y Action.groups como vistas de
la channelbag del primer slot (lo crea si hace falta), con fcurves.new(data_path, index, action_group) como antes.
Además Blender 5 no asigna solo el slot al hacer "animation_data.action = acción" (queda action_slot None y la
animación no se aplica): un handler de cambio de cuadro y de depsgraph le pone el primer slot compatible a todo
objeto que tenga acción sin slot. Así los scripts de 4.4 corren igual y en 4.4 este módulo no toca nada. Importarlo una vez basta (nindo_anim,
charlib y kitlib lo importan).
"""
import bpy

_LEGACY = hasattr(bpy.types.Action, "fcurves") and not getattr(bpy.types.Action, "_nindo_compat", False)


def channelbag(act, id_type="OBJECT"):
    """La channelbag del primer slot de la acción (la crea, con su slot, si no hay)."""
    from bpy_extras import anim_utils
    slot = act.slots[0] if len(act.slots) else act.slots.new(id_type=id_type, name="Nindo")
    return anim_utils.action_ensure_channelbag_for_slot(act, slot)


class _FCurves:
    """Lo que devolvía Action.fcurves en 4.4, sobre la channelbag de Blender 5."""
    __slots__ = ("_cb",)

    def __init__(self, cb):
        self._cb = cb

    def new(self, data_path, index=0, action_group=""):
        return self._cb.fcurves.new(data_path, index=index, group_name=action_group) if action_group \
            else self._cb.fcurves.new(data_path, index=index)

    def find(self, data_path, index=0):
        return self._cb.fcurves.find(data_path, index=index)

    def remove(self, fc):
        self._cb.fcurves.remove(fc)

    def clear(self):
        self._cb.fcurves.clear()

    def __iter__(self):
        return iter(list(self._cb.fcurves))

    def __len__(self):
        return len(self._cb.fcurves)

    def __getitem__(self, i):
        return self._cb.fcurves[i]


def ensure_slot(ob):
    """Le asigna a 'ob' el primer slot compatible de su acción si Blender no lo hizo."""
    ad = getattr(ob, "animation_data", None)
    if ad is None or ad.action is None or getattr(ad, "action_slot", True) is not None:
        return
    slots = ad.action_suitable_slots
    if len(slots):
        ad.action_slot = slots[0]


def _fix_slots(*_):
    for ob in bpy.data.objects:
        ensure_slot(ob)


def _install():
    if _LEGACY:
        return
    bpy.types.Action.fcurves = property(lambda self: _FCurves(channelbag(self)))
    bpy.types.Action.groups = property(lambda self: channelbag(self).groups)
    bpy.types.Action._nindo_compat = True
    for h in (bpy.app.handlers.frame_change_pre, bpy.app.handlers.depsgraph_update_pre):
        if _fix_slots not in h:
            h.append(_fix_slots)


_install()
