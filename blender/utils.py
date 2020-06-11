import bpy
from contextlib import contextmanager


@contextmanager
def no_interfere_ctx(ctx):
    """ allows us to perform operations without affecting our selected or active
    objects """
    old_selected_objects = ctx.selected_objects.copy()
    active_object = ctx.active_object

    # TODO ugly shim for a bug where deleting an object *from a script*
    # causes the object to be in a weird state where the name is a bunch
    # of invalid characters like:
    # <bpy_struct, Object("������������������������������������������")>
    def bad_object(ob):
        bad = False
        try:
            str(ob.name)
        except UnicodeDecodeError:
            bad = True
        return bad

    try:
        yield
    finally:
        for obj in ctx.selected_objects:
            obj.select = False

        for obj in old_selected_objects:
            if bad_object(obj):
                continue

            if obj.name in bpy.data.objects:
                obj.select = True

        if (
                active_object 
                and not bad_object(active_object)
                and active_object.name in bpy.data.objects):

            ctx.scene.objects.active = active_object
    

def deselect(ctx):
    for obj in ctx.selected_objects:
        obj.select = False


@contextmanager
def selected(ctx, obs):
    obs = list_wrap(obs)
    with no_interfere_ctx(ctx):
        deselect(ctx)
        for ob in obs:
            ob.select = True
        yield


def delete(ob):
    with selected(ob):
        bpy.ops.object.delete()


def list_wrap(obs):
    if not isinstance(obs, (list, tuple)):
        obs = [obs]
    return obs


@contextmanager
def visible(obs):
    obs = list_wrap(obs)
    old_vis = {ob: ob.hide for ob in obs}

    for ob in obs:
        ob.hide = False

    try:
        yield
        return
    finally:
        for ob in obs:
            ob.hide = old_vis[ob]


@contextmanager
def active(ob):
    obs = bpy.context.scene.objects

    old_active = obs.active
    obs.active = ob
    try:
        yield
    finally:
        obs.active = old_active

    
@contextmanager
def active_and_selected(ob):
    with selected(ob), active(ob):
        yield


def duplicate(scene, ob):
    """ duplicates an object within a scene """
    copy = ob.copy()

    # some ops will fail (like triangle mesh) if the object we're operating on
    # is hidden.  i think its safe to unhide it
    copy.hide = False

    copy.data = ob.data.copy()
    scene.objects.link(copy)
    return copy


@contextmanager
def a_copy(ctx, scene, ob):
    """ allows us to operate on a copy of an object, which will be cleaned up
    afterwards """
    copy = duplicate(scene, ob)
    try:
        yield copy
    finally:
        scene.objects.unlink(copy)


