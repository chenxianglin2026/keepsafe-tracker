"""
KeepSafe Enclosure - Blender Python Script
Generates a 78x48x12mm rounded rectangle enclosure with all features.
Run in Blender: Scripting workspace -> Open this file -> Run Script
Or: blender --python keepsafe_enclosure.py
"""

import bpy
import math

# Clear all existing objects
bpy.ops.object.select_all(action='SELECT')
bpy.ops.object.delete(use_global=False)

# ── Parameters ──
W = 78.0       # total width (mm)
D = 48.0       # total depth (mm)
H = 12.0       # total height (mm)
CORNER_R = 8.0 # corner radius
WALL = 1.6     # wall thickness
TOP_H = 5.0    # top shell height
BOT_H = 7.0    # bottom shell height

# Ear (loop) - top-left corner
EAR_W = 10.0
EAR_H = 14.0
EAR_HOLE_D = 8.0
EAR_OFFSET_X = -W/2 + CORNER_R / 2
EAR_OFFSET_Y = D/2 + 2

# SOS button
SOS_D = 22.0
SOS_FROM_BOTTOM = 8.0

# Speaker area
SPK_W = 20.0
SPK_H = 14.0
SPK_Y = D/2 - 18

# LEDs
LED_D = 3.0
LED_SPACING = 6.0
LED_Y = SPK_Y - 10

# Type-C
TYPEC_W = 8.5
TYPEC_H = 2.8
TYPEC_Y = 15.0

# Internal - battery 503040
BAT_W = 30.0
BAT_D = 50.0
BAT_H = 4.0
BAT_Y = -D/4

# Internal - PCB
PCB_W = 30.0
PCB_D = 35.0
PCB_H = 1.6
PCB_Y = D/6

# Internal - motor
MOTOR_D = 8.0
MOTOR_H = 3.0
MOTOR_Y = -D/2 + 12

# Resolution
SEGMENTS = 48

def clear_scene():
    bpy.ops.object.select_all(action='SELECT')
    bpy.ops.object.delete(use_global=False)
    
    # Remove all materials
    for mat in bpy.data.materials:
        mat.user_clear()
        bpy.data.materials.remove(mat)

def make_rounded_rect_profile(w, d, r, seg=SEGMENTS):
    """Create a 2D rounded rectangle (list of (x,y) vertices)."""
    verts = []
    r = min(r, w/2, d/2)
    
    # Top-right corner
    for i in range(seg // 4 + 1):
        angle = math.radians(90 * i / (seg // 4))
        x = w/2 - r + r * math.cos(angle)
        y = d/2 - r + r * math.sin(angle)
        verts.append((x, y))
    
    # Top-left corner
    for i in range(seg // 4 + 1):
        angle = math.radians(90 + 90 * i / (seg // 4))
        x = -w/2 + r + r * math.cos(angle)
        y = d/2 - r + r * math.sin(angle)
        verts.append((x, y))
    
    # Bottom-left corner
    for i in range(seg // 4 + 1):
        angle = math.radians(180 + 90 * i / (seg // 4))
        x = -w/2 + r + r * math.cos(angle)
        y = -d/2 + r + r * math.sin(angle)
        verts.append((x, y))
    
    # Bottom-right corner
    for i in range(seg // 4 + 1):
        angle = math.radians(270 + 90 * i / (seg // 4))
        x = w/2 - r + r * math.cos(angle)
        y = -d/2 + r + r * math.sin(angle)
        verts.append((x, y))
    
    return verts

def create_mesh_from_profile(name, verts_2d, height, offset_z=0):
    """Extrude a 2D profile into a 3D mesh."""
    n = len(verts_2d)
    vertices = []
    faces = []
    
    # Bottom ring
    for x, y in verts_2d:
        vertices.append((x, y, -height/2 + offset_z))
    # Top ring
    for x, y in verts_2d:
        vertices.append((x, y, height/2 + offset_z))
    
    # Side faces
    for i in range(n):
        next_i = (i + 1) % n
        faces.append([i, next_i, next_i + n, i + n])
    
    # Bottom face
    faces.append(list(range(n)))
    # Top face
    faces.append(list(range(n, 2 * n)))
    
    mesh = bpy.data.meshes.new(name)
    obj = bpy.data.objects.new(name, mesh)
    bpy.context.collection.objects.link(obj)
    mesh.from_pydata(vertices, [], faces)
    mesh.update()
    
    # Auto-smooth
    for poly in mesh.polygons:
        poly.use_smooth = True
    
    return obj

def add_cylinder(name, x, y, z, diameter, height, seg=32):
    """Add a cylinder at position."""
    bpy.ops.mesh.primitive_cylinder_add(
        vertices=seg,
        radius=diameter/2,
        depth=height,
        location=(x, y, z)
    )
    obj = bpy.context.active_object
    obj.name = name
    return obj

def add_cube(name, x, y, z, w, d, h):
    """Add a box at position."""
    bpy.ops.mesh.primitive_cube_add(
        size=1.0,
        location=(x, y, z)
    )
    obj = bpy.context.active_object
    obj.name = name
    obj.scale = (w/2, d/2, h/2)
    bpy.ops.object.transform_apply(scale=True)
    return obj

def slot_op(target_obj, tool_objs):
    """Boolean difference: cut tool_objs from target_obj."""
   # Use a fresh copy for each cut
    current = target_obj
    for tool in tool_objs:
        bpy.context.view_layer.objects.active = current
        bpy.ops.object.modifier_add(type='BOOLEAN')
        mod = current.modifiers[-1]
        mod.operation = 'DIFFERENCE'
        mod.object = tool
        bpy.ops.object.modifier_apply(modifier=mod.name)
        # Remove the tool object
        bpy.data.objects.remove(tool, do_unlink=True)
    return current

# ── Build the enclosure ──

# Shell profile
profile = make_rounded_rect_profile(W - WALL*2, D - WALL*2, CORNER_R - WALL)

# Top shell (outer)
top_outer = create_mesh_from_profile("Top_Outer", make_rounded_rect_profile(W, D, CORNER_R), TOP_H, BOT_H)

# Top shell (inner cavity)
# Cut inner from top shell
top_inner = create_mesh_from_profile("Top_Inner", profile, TOP_H - WALL, BOT_H + WALL)

# Subtract inner from outer
bpy.context.view_layer.objects.active = top_outer
bpy.ops.object.modifier_add(type='BOOLEAN')
mod = top_outer.modifiers[-1]
mod.operation = 'DIFFERENCE'
mod.object = top_inner
bpy.ops.object.modifier_apply(modifier=mod.name)
bpy.data.objects.remove(top_inner, do_unlink=True)
top_shell = top_outer

# Bottom shell (outer)
bot_outer = create_mesh_from_profile("Bottom_Outer", make_rounded_rect_profile(W, D, CORNER_R), BOT_H, -BOT_H/2)

# Bottom shell (inner cavity)
bot_inner = create_mesh_from_profile("Bottom_Inner", profile, BOT_H - WALL, -BOT_H/2 + WALL)

bpy.context.view_layer.objects.active = bot_outer
bpy.ops.object.modifier_add(type='BOOLEAN')
mod = bot_outer.modifiers[-1]
mod.operation = 'DIFFERENCE'
mod.object = bot_inner
bpy.ops.object.modifier_apply(modifier=mod.name)
bpy.data.objects.remove(bot_inner, do_unlink=True)
bot_shell = bot_outer

# ── Add Ear (loop) to top shell ──
bpy.ops.mesh.primitive_cylinder_add(
    vertices=SEGMENTS,
    radius=EAR_W/2,
    depth=EAR_H,
    location=(EAR_OFFSET_X, EAR_OFFSET_Y + EAR_H/2 - 2, BOT_H + TOP_H/2)
)
ear_outer = bpy.context.active_object
ear_outer.name = "Ear"

# Cut ear hole
bpy.ops.mesh.primitive_cylinder_add(
    vertices=SEGMENTS,
    radius=EAR_HOLE_D/2,
    depth=EAR_H - 4,
    location=(EAR_OFFSET_X, EAR_OFFSET_Y + EAR_H/2 - 2, BOT_H + TOP_H/2)
)
ear_hole = bpy.context.active_object
ear_hole.name = "Ear_Hole"

bpy.context.view_layer.objects.active = ear_outer
bpy.ops.object.modifier_add(type='BOOLEAN')
mod = ear_outer.modifiers[-1]
mod.operation = 'DIFFERENCE'
mod.object = ear_hole
bpy.ops.object.modifier_apply(modifier=mod.name)
bpy.data.objects.remove(ear_hole, do_unlink=True)

# Join ear to top shell
bpy.context.view_layer.objects.active = top_shell
bpy.ops.object.modifier_add(type='BOOLEAN')
mod = top_shell.modifiers[-1]
mod.operation = 'UNION'
mod.object = ear_outer
bpy.ops.object.modifier_apply(modifier=mod.name)
bpy.data.objects.remove(ear_outer, do_unlink=True)

# ── Cut holes in top shell ──

# SOS hole
sos = add_cylinder("SOS_Hole", 0, -D/2 + SOS_FROM_BOTTOM + SOS_D/2, BOT_H + TOP_H/2, SOS_D, TOP_H + 2)
cut_tools = [sos]

# Speaker holes
for x in [-6, -3, 0, 3, 6]:
    for y_off in [-3, 0, 3]:
        spk = add_cylinder("Speaker_Hole", x, D/2 - 18 + y_off, BOT_H + TOP_H/2, 1.5, TOP_H + 2)
        cut_tools.append(spk)

# LED holes
for x_off in [-LED_SPACING/2, LED_SPACING/2]:
    led = add_cylinder("LED_Hole", x_off, LED_Y, BOT_H + TOP_H/2, LED_D, TOP_H + 2)
    cut_tools.append(led)

# Type-C hole
typec = add_cube("TypeC_Hole", W/2, TYPEC_Y, BOT_H/2, WALL + 2, TYPEC_W, TYPEC_H + 1)
cut_tools.append(typec)

# Apply all cuts
bpy.context.view_layer.objects.active = top_shell
for tool in cut_tools:
    bpy.ops.object.modifier_add(type='BOOLEAN')
    mod = top_shell.modifiers[-1]
    mod.operation = 'DIFFERENCE'
    mod.object = tool
    bpy.ops.object.modifier_apply(modifier=mod.name)
    bpy.data.objects.remove(tool, do_unlink=True)

# ── Add internal structures to bottom shell ──

# Battery holder
bat = add_cube("Battery_Holder", 0, BAT_Y, -BOT_H/2 + WALL, BAT_W + WALL*2, BAT_D + WALL*2, BAT_H + WALL)
bat_inner = add_cube("Battery_Cavity", 0, BAT_Y, -BOT_H/2 + WALL + WALL/2, BAT_W, BAT_D, BAT_H + 0.1)

bpy.context.view_layer.objects.active = bat
bpy.ops.object.modifier_add(type='BOOLEAN')
mod = bat.modifiers[-1]
mod.operation = 'DIFFERENCE'
mod.object = bat_inner
bpy.ops.object.modifier_apply(modifier=mod.name)
bpy.data.objects.remove(bat_inner, do_unlink=True)

# Join battery holder to bottom shell
bpy.context.view_layer.objects.active = bot_shell
bpy.ops.object.modifier_add(type='BOOLEAN')
mod = bot_shell.modifiers[-1]
mod.operation = 'UNION'
mod.object = bat
bpy.ops.object.modifier_apply(modifier=mod.name)
bpy.data.objects.remove(bat, do_unlink=True)

# PCB slot
pcb = add_cube("PCB_Slot", 0, PCB_Y, -BOT_H/2 + WALL, PCB_W + WALL*2, PCB_D + WALL*2, PCB_H + WALL)
pcb_inner = add_cube("PCB_Cavity", 0, PCB_Y, -BOT_H/2 + WALL + WALL/2, PCB_W, PCB_D, PCB_H + 0.1)

bpy.context.view_layer.objects.active = pcb
bpy.ops.object.modifier_add(type='BOOLEAN')
mod = pcb.modifiers[-1]
mod.operation = 'DIFFERENCE'
mod.object = pcb_inner
bpy.ops.object.modifier_apply(modifier=mod.name)
bpy.data.objects.remove(pcb_inner, do_unlink=True)

bpy.context.view_layer.objects.active = bot_shell
bpy.ops.object.modifier_add(type='BOOLEAN')
mod = bot_shell.modifiers[-1]
mod.operation = 'UNION'
mod.object = pcb
bpy.ops.object.modifier_apply(modifier=mod.name)
bpy.data.objects.remove(pcb, do_unlink=True)

# Motor holder
motor = add_cube("Motor_Holder", 0, MOTOR_Y, -BOT_H/2 + WALL, MOTOR_D + WALL*2, MOTOR_D + WALL*2, MOTOR_H + WALL)
bpy.context.view_layer.objects.active = bot_shell
bpy.ops.object.modifier_add(type='BOOLEAN')
mod = bot_shell.modifiers[-1]
mod.operation = 'UNION'
mod.object = motor
bpy.ops.object.modifier_apply(modifier=mod.name)
bpy.data.objects.remove(motor, do_unlink=True)

# ── Materials ──

def make_material(name, color, roughness=0.5, metallic=0.0):
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    nodes = mat.node_tree.nodes
    bsdf = nodes.get("Principled BSDF")
    if bsdf:
        bsdf.inputs[0].default_value = color  # Base Color
        bsdf.inputs[7].default_value = roughness  # Roughness
        bsdf.inputs[6].default_value = metallic   # Metallic
    return mat

top_mat = make_material("Top_Material", (0.15, 0.45, 0.75, 1.0), 0.3, 0.1)  # Blue-ish
bot_mat = make_material("Bottom_Material", (0.5, 0.5, 0.5, 1.0), 0.5, 0.2)  # Gray

if top_shell.data.materials:
    top_shell.data.materials[0] = top_mat
else:
    top_shell.data.materials.append(top_mat)

if bot_shell.data.materials:
    bot_shell.data.materials[0] = bot_mat
else:
    bot_shell.data.materials.append(bot_mat)

# ── Scene setup ──

# Camera
bpy.ops.object.select_all(action='DESELECT')
bpy.ops.object.camera_add(location=(120, -80, 60))
cam = bpy.context.active_object
cam.rotation_euler = (math.radians(60), 0, math.radians(45))
bpy.context.scene.camera = cam

# Light
bpy.ops.object.light_add(type='AREA', location=(100, -60, 80))
light = bpy.context.active_object
light.data.energy = 500

# Background
bpy.context.scene.world.use_nodes = True
bg = bpy.context.scene.world.node_tree.nodes.get("Background")
if bg:
    bg.inputs[0].default_value = (0.9, 0.9, 0.95, 1.0)

# Render settings
bpy.context.scene.render.engine = 'CYCLES'
bpy.context.scene.render.resolution_x = 1920
bpy.context.scene.render.resolution_y = 1080
bpy.context.scene.render.film_transparent = False

# Set viewport to material preview
for area in bpy.context.screen.areas:
    if area.type == 'VIEW_3D':
        for space in area.spaces:
            if space.type == 'VIEW_3D':
                space.shading.type = 'MATERIAL'

print("=" * 50)
print("KeepSafe enclosure generated successfully!")
print(f"Top shell: {W}x{D}x{TOP_H}mm, Bottom shell: {W}x{D}x{BOT_H}mm")
print(f"Total height: {H}mm")
print("=" * 50)
print("\nTo export STL:")
print("  Select object -> File -> Export -> STL (.stl)")
print("  Or use: bpy.ops.export_mesh.stl(filepath='keepsafe.stl')")
