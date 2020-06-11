import os
import sys
from os.path import join, basename, expanduser, exists
from collections import defaultdict as dd
import argparse
from uuid import uuid4
import json
from math import radians, pi, sqrt, inf, ceil
import random
from random import uniform, triangular
import tempfile
from scipy.spatial import KDTree
from PIL import Image

import bpy
from bpy_extras.object_utils import world_to_camera_view
from mathutils import Vector



THIS_DIR = bpy.path.abspath("//")
if THIS_DIR not in sys.path:
    sys.path.insert(0, THIS_DIR)

import text_gen
import utils


C = bpy.context
D = bpy.data

TABLE_DIR = "//tables"
FONT_DIR = "//fonts/ttfs"
FLASH_BRIGHTNESS = 1000


# max offsets for translated sub-windows of a letter's bounding boxes, in
# percentages of the bounding boxes corresponding dimension.  for example,
# (0.25, 0.5) means that we can shift a quarter of the letter's width to the
# left and right, and half of the letter's height up or down
MAX_WINDOW_OFFSET = (0.5, 0.5)
NUM_WINDOWS = 5


# some main components of the scene that we'll be adjusting randomly
scene = D.scenes[0]
receipt_handle = D.objects["receipt handle"]
receipt = D.objects["receipt"]
flash = D.objects["flash"]
table = D.objects["table"]
table_mat = D.materials["table"]
world_mat = D.worlds["World"]
camera = D.objects["Camera"]
cam_target = D.objects["cam target"]
crumpler = D.objects["crumple mapper"]
receipt_mat = D.materials["receipt paper"]
primary_light = D.objects["Lamp"]



def z_to_floor(ob):
    """ takes an object and gives a z position that puts its bounding box at 0
    """ 
    bb = ob.bound_box
    lower_pos = (ob.matrix_world * Vector(bb[0])).z
    diff = ob.matrix_world.translation.z - lower_pos
    return diff

def load_image(path):
    """ load a texture """
    im = D.images.load(path, True)
    return im

def load_table(name):
    """ load a table texture """
    path = join(TABLE_DIR, name)
    return load_image(path)

def load_random_table():
    """ pick a random table texture and load it"""
    name = random.choice(os.listdir(bpy.path.abspath(TABLE_DIR)))
    return load_table(name)

def shuffle():
    """ perform the randomization of scene attributes """

    # curvature of receipt
    receipt.modifiers["SimpleDeform"].angle = radians(uniform(-90, 90))
    # wrinkliness
    receipt.modifiers["Displace"].strength = triangular(0.6, 0.9, 1.4)
    
    # wrinkliness frequency and orientation of wrinkles
    cscale = triangular(0.8, 3, 1.620747)
    crumpler.scale = Vector((cscale, cscale, cscale))
    crumpler.rotation_euler = Vector((uniform(0, pi/2), uniform(0, pi/2),
        uniform(0, pi/2)))
    
    # rotation about the z (up) axis
    receipt.rotation_euler.z = radians(triangular(-10, 10, 0))
    
    # we must call scene update so we have correct bounding box values from
    # displacement and wrinkles, in order to align the receipt to the table
    C.scene.update()

    # align receipt to floor
    receipt_handle.location.z = z_to_floor(receipt)
    
    # is our camera flash on?
    flash.data.node_tree.nodes["Emission"].inputs[1].default_value =\
        round(uniform(0, 1)) * FLASH_BRIGHTNESS
        
    # load a random table texture
    table_mat.node_tree.nodes["Texture"].image = load_random_table()

    # adjust the ambient brightness of our HDRI world
    world_mat.node_tree.nodes["Background"].inputs[1].default_value = uniform(0, 1)
    
    # adjust the camera position
    camera.location = Vector((
        uniform(-1, 1),
        uniform(-1, 1),
        triangular(3, 10, 4.7)
    ))

    # adjust the camera target location, because our focal distance is based on
    # the target
    cam_target.location.z = triangular(-1, 1, 0.15)

    # bigger aperature = blurrier outside of focal distance
    camera.data.cycles.aperture_size = uniform(0, 0.05)
    
    scene.cycles.film_exposure = triangular(0.2, 2, 0)

    
    # some basic receipt texture parameters, controlling glossiness and ink
    # fadedness
    nodes = receipt_mat.node_tree.nodes
    nodes["Glossy BSDF"].inputs[1].default_value = uniform(.15, .5)
    nodes["Layer Weight"].inputs[0].default_value = uniform(0, .75)
    #nodes["Math"].inputs[1].default_value = triangular(0, .2, 0)
    nodes["Math"].inputs[1].default_value = 0
    
    # adjust the position of the primary lamp
    loc = Vector((
        uniform(-10, 10),
        uniform(-10, 10),
        uniform(1.5, 10)
    ))
    primary_light.location = loc


def parse_render_size(s):
    w, h = s.split("x")
    return int(w), int(h)


def get_unmodified_size(ob):
    def flip_off(mod):
        old = mod.show_viewport
        mod.show_viewport = False
        def restore():
            mod.show_viewport = old
        return restore

    restore_fns = [flip_off(mod) for mod in ob.modifiers]

    try:
        scene.update()
        dims = ob.dimensions
    finally:
        [restore() for restore in restore_fns]

    return dims


def get_texture_size_from_ob(ob, px_width):
    vec = get_unmodified_size(ob)
    px_height = int(round(px_width * (vec.y / vec.x)))
    return (px_width, px_height)


def to_mesh(ctx, scene, ob):
    with utils.a_copy(ctx, scene, ob) as copy:
        with utils.selected(ctx, copy):

            # this seems weird, but it's the fastest way to triangulate a bunch of
            # meshes.  typically, you'd do it one at a time, but this is slow.
            # adding one triangulate modifier, then linking to all applicable
            # meshes, is the fastest
            copy.select = True
            ctx.scene.objects.active = copy
            bpy.ops.object.modifier_add(type="TRIANGULATE")
            bpy.ops.object.make_links_data(type="MODIFIERS")

            mesh = copy.to_mesh(scene, True, "PREVIEW")
            mesh.update(calc_tessface=True)
            return mesh



def generate_receipt_texture(receipt, width, font_dir, line_spacing, kerning):
    tex_width, tex_height = get_texture_size_from_ob(receipt, width)
    receipt_im, bbs, font_used = text_gen.gen_receipt(font_dir, (tex_width,
        tex_height), 45, 0.04, line_spacing, kerning)
    receipt_file = tempfile.NamedTemporaryFile(suffix=".png", delete=False)
    receipt_im.save(receipt_file)
    return receipt_file, bbs, font_used


def triangle_area(verts):
    """ computes triangle area.  it is possible to have a negative area, and is
    in fact required for barycentric coordinates to work correctly """
    a, b, c = verts[0], verts[1], verts[2]
    return (a.x*(b.y-c.y) + b.x*(c.y-a.y) + c.x*(a.y-b.y)) / 2.0


def barycentric_coords(verts, point):
    area = triangle_area(verts)
    sub_area1 = triangle_area((point, verts[0], verts[1]))
    sub_area2 = triangle_area((point, verts[1], verts[2]))
    sub_area3 = triangle_area((point, verts[2], verts[0]))

    x = sub_area1/area
    y = sub_area2/area
    z = sub_area3/area
    coord = Vector((x, y, z))
    return coord


def bary_interpolate(coords, verts):
    interp = verts[2]*coords.x + verts[0]*coords.y + verts[1]*coords.z
    return interp


def contains_vert(face, vert):
    bcoord = barycentric_coords(face, vert)
    return (bcoord[0] <= 1.0 and bcoord[0] > 0) \
            and (bcoord[1] <= 1.0 and bcoord[1] >= 0) \
            and (bcoord[2] <= 1.0 and bcoord[2] >= 0)

def get_containing_face(mesh, vert_to_coords, vert_to_faces, verts_and_coords,
        kdtree, point):

    # get our match index of the closest uv coordinate
    _, midx = kdtree.query((point.x, point.y))

    # from our match index, get the vertex associated with our closest match
    vidx, coord = verts_and_coords[midx]

    # find all the faces using that vertex
    faces = vert_to_faces[vidx]

    # test each face individually for containing coord
    for fidx in faces:
        face = mesh.tessfaces[fidx]
        coords = [vert_to_coords[vidx] for vidx in face.vertices]
        if contains_vert(coords, point):
            return fidx


def norm_img_to_render_space(render_size, coord):
    coord = (
        coord[0] * render_size[0],
        (1.0-coord[1]) * render_size[1]
    )
    return coord


def map_coord(scene, camera, local_world_mat, uv_coord, mesh,
        vert_to_coords, vert_to_faces, verts_and_coords, kdtree):
    """ converts a uv coord to a *NORMALIZED* image-space position """

    fidx = get_containing_face(mesh, vert_to_coords, vert_to_faces,
            verts_and_coords, kdtree, uv_coord)
    face = mesh.tessfaces[fidx]

    face_uv_coords = [vert_to_coords[vidx] for vidx in face.vertices]
    face_coords = [mesh.vertices[vidx].co for vidx in face.vertices]

    bary = barycentric_coords(face_uv_coords, uv_coord)
    uv_local_coord = bary_interpolate(bary, face_coords)

    wpos = local_world_mat * uv_local_coord
    img_pos = world_to_camera_view(scene, camera, wpos)
    return img_pos


def bounding_box_for_points(points):
    """ for some transformed bounding box points (non right angles), get a
    bounding box with right angles """

    min_x = inf
    min_y = inf
    max_x = 0
    max_y = 0
    for point in points:
        if point[0] < min_x:
            min_x = point[0]

        if point[1] < min_y:
            min_y = point[1]

        if point[0] > max_x:
            max_x = point[0]

        if point[1] > max_y:
            max_y = point[1]

    return ((min_x, max_y), (max_x, min_y))



def set_receipt_image(receipt_mat, filename):
    img = bpy.data.images.load(filename)
    receipt_image = D.images[basename(filename)]
    nodes = receipt_mat.node_tree.nodes
    nodes["Image Texture"].image = receipt_image


def random_float(start, end):
    return (random.random() * (end - start)) + start


def generate_bbs(render_size):
    font_dir = bpy.path.abspath(FONT_DIR)

    line_spacing = random_float(0.9, 1.1)
    kerning = random_float(0.95, 1.05)
    receipt_file, letter_bbs, font_used = generate_receipt_texture(receipt,
            render_size[0], font_dir, line_spacing, kerning)

    receipt_name = receipt_file.name

    set_receipt_image(receipt_mat, receipt_name)

    shuffle()
    mesh = to_mesh(C, C.scene, receipt)


    # do some preprocessing and create some data structures that will aid in our
    # get_containing_face function
    vert_to_coords = {}
    vert_to_faces = dd(list)
    verts_and_coords = []
    uv_map = mesh.tessface_uv_textures[0]
    for faceidx, face in enumerate(uv_map.data):
        verts = mesh.tessfaces[faceidx].vertices
        for vidx, uv_data in zip(verts, face.uv):
            vert = mesh.vertices[vidx]
            coord = Vector((uv_data[0], uv_data[1]))
            vert_to_coords[vidx] = coord

            verts_and_coords.append((vidx, coord))
            vert_to_faces[vidx].append(faceidx)
    data = [(coord.x, coord.y) for _, coord in verts_and_coords]
    kdtree = KDTree(data)

    # loop through our letters and bounding boxes and put the bounding box into
    # image space
    image_bbs = []
    for letter, bbs in letter_bbs.items():
        for top_left, bottom_right in bbs:

            # these are the four corners of a glyph.  these are in texture-space
            # and we want their coordinates in rendered-image space
            top_left = Vector((top_left[0], top_left[1]))
            top_right = Vector((bottom_right[0], top_left[1]))
            bottom_right = Vector((bottom_right[0], bottom_right[1]))
            bottom_left = Vector((top_left[0], bottom_right[1]))
            # we want our winding order to be counter clockwise
            coords = [top_left, top_right, bottom_right, bottom_left]

            # for each corner, map it to distorted image space
            raw_bbs = []
            for coord in coords:
                img_pos = map_coord(scene, camera, receipt.matrix_world, coord,
                        mesh, vert_to_coords, vert_to_faces, verts_and_coords,
                        kdtree)
                img_pos = (img_pos.x, img_pos.y)
                raw_bbs.append(img_pos)

            # now that we have all the corners in image space, find the bounding
            # box that contains those warped corners, and we'll use that
            ul, br = bounding_box_for_points(raw_bbs)

            # convert our texture-space coordinates (0,0 in bottom right) to
            # image-space (0,0 in upper left)
            ul = norm_img_to_render_space(render_size, ul)
            br = norm_img_to_render_space(render_size, br)
            ul, br = (list(ul), list(br))


            width = abs(ul[0] - br[0])
            height = abs(ul[1] - br[1])
            ratio = width / height

            if ratio > 3 or ratio < 1/15.0:
                continue

            raw_bbs = [norm_img_to_render_space(render_size, bb) for bb in
                    raw_bbs]

            tl, tr, br, bl = raw_bbs
            upper = vec_sub(tr, tl)
            lower = vec_sub(br, bl)
            avg_vec = vec_add(upper, lower)
            norm_vec = vec_normalize(avg_vec)

            data = (letter, (ul, br), (width, height), raw_bbs, norm_vec)
            image_bbs.append(data)

    return image_bbs, receipt_name


def render(size):
    width, height = size

    rs = scene.render
    rs.resolution_x = width
    rs.resolution_y = height

    image_bbs, texture_file = generate_bbs(size)

    output_path = tempfile.NamedTemporaryFile(suffix=".png", delete=False).name
    rs.filepath = output_path

    bpy.ops.render.render(write_still=True)
    im = Image.open(rs.filepath).convert("L")

    os.unlink(texture_file)
    os.unlink(output_path)

    return image_bbs, im


def vec_sub(a, b):
    return (a[0]-b[0], a[1]-b[1])

def vec_add(a, b):
    return (a[0]+b[0], a[1]+b[1])

def vec_normalize(v):
    norm = sqrt(v[0]*v[0] + v[1]*v[1])
    return (v[0]/norm, v[1]/norm)




def get_arg_str():
    sentinel = "--"
    arg_list = sys.argv[:]
    sidx = -1
    try:
        sidx = arg_list.index(sentinel)
    except ValueError:
        arg_list = []

    arg_str = arg_list[sidx+1:]
    return arg_str


def progress_run(fn, num):
    for i in range(num):
        print(100*i/num)
        fn()




if __name__ == "__main__":
    parser = argparse.ArgumentParser(prog="generate_receipts.sh")
    parser.add_argument("-f", "--frames", metavar="NUM", default=1, type=int,
            action="store", help="The number of frames to render")
    parser.add_argument("--seed", type=int, default=None)
    parser.add_argument("-s", "--size", metavar="WxH", default="1440x2560",
            action="store", help="Size of the rendered output",
            type=parse_render_size)
    parser.add_argument("--output", required=True)


    ns = parser.parse_args(get_arg_str())
    if ns.seed:
        random.seed(ns.seed)

    num_frames = ns.frames
    render_size = ns.size

    def fn():
        image_bbs, im = render(ns.size)
        filename = uuid4().hex
        image_output = join(ns.output, filename + ".png")
        json_output = join(ns.output, filename + ".json")

        im.save(image_output, "png")
        with open(json_output, "w") as h:
            json.dump(image_bbs, h, indent=2)

    progress_run(fn, num_frames)
