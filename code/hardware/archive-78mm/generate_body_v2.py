#!/usr/bin/env python3
"""
KeepSafe Body v2 - Direct Generator
Generates the 3D model with:
  1. Lanyard hole (4mm, top-left)
  2. Speaker grille (3x5 array at bottom)
  3. Surface features (button recess, fillet)

Applies each cutout one at a time to minimize mesh complexity issues.

Usage: /usr/bin/python3 generate_body_v2.py
"""

import os, sys, math

def make_cyl(radius, height, sections=32):
    """Create a cylinder mesh at origin."""
    import trimesh
    return trimesh.creation.cylinder(radius=radius, height=height, sections=sections)

def make_box(extents):
    """Create a box mesh at origin."""
    import trimesh
    return trimesh.creation.box(extents=extents)

def apply_cutout(body, name, cutter):
    """Apply a single cutout (cutter) to body via boolean difference."""
    try:
        result = body.difference(cutter)
        vol_drop = (1 - result.volume/body.volume) * 100 if body.volume > 0 else 0
        print(f"  {name}: vol -{vol_drop:.2f}% -> {len(result.vertices)} verts")
        return result
    except Exception as e:
        print(f"  {name}: FAILED - {e}")
        return body

def main():
    print("=" * 60)
    print("KeepSafe Body v2 Generator")
    print("=" * 60)

    try:
        import trimesh
        print(f"trimesh: {trimesh.__version__}")
    except ImportError:
        print("ERROR: trimesh not found.")
        sys.exit(1)

    SEGS = 32

    # ===== DIMENSIONS =====
    # Box dimensions: 78mm (long axis = Y) x 48mm (short axis = X) to match feature positions
    body_len = 78.0  # long axis, maps to Y
    body_wid = 48.0  # short axis, maps to X
    body_h = 12.0
    wall_t = 1.5

    # Lanyard hole: 4mm through-hole, top-left corner, 5mm from edges
    # Top-left = positive Y, negative X
    ld = 4.0
    lm = 5.0
    lx = -body_wid/2 + lm      # X: -24 + 5 = -19
    ly = body_len/2 - lm        # Y: 39 - 5 = 34

    # Speaker grille: 5x3 array, 2mm holes, 3mm spacing, at bottom (negative Y)
    sd = 2.0
    ss = 3.0
    sc, sr = 5, 3
    sg_w = (sc-1)*ss      # 12mm wide in X
    sg_h = (sr-1)*ss      # 6mm tall in Y
    # Place on the bottom side (negative Y), centered in X (short axis = 48mm)
    # Bottom edge is at Y=-body_len/2 = -39. Add margin of 4mm.
    # Grid center Y: -body_len/2 + sg_h/2 + 4 = -39 + 3 + 4 = -32
    spy = -body_len/2 + sg_h/2 + 4
    spx = 0.0  # centered in X

    # SOS button
    sos_r = 6.0
    sos_y = -body_len/2 + 12

    # LED
    led_d = 2.5
    led_y = body_len/2 - 8

    # Flashlight
    flash_r = 6.0
    flash_y = body_len/2 - 6

    # Type-C
    tw, th = 10.0, 4.0

    # Motor mount
    mr = 4.0
    mx = body_wid/2 - 8
    my = -body_len/2 + 10

    # ===== CREATE BODY =====
    print("\n[1] Creating base body (78x48x12 mm)...")
    body = make_box([body_wid, body_len, body_h])  # X=48, Y=78, Z=12
    print(f"  Base: {len(body.vertices)} verts, vol={body.volume:.1f}")

    # ===== Lanyard Hole =====
    print("\n[2] Lanyard hole (4mm, top-left corner)...")
    c = make_cyl(ld/2, body_h + 2, SEGS)
    c.apply_translation([lx, ly, 0])
    body = apply_cutout(body, "Lanyard", c)

    # ===== Speaker Grille =====
    print(f"\n[3] Speaker grille ({sc}x{sr} = {sc*sr} holes at bottom)...")
    for ix in range(sc):
        for iy in range(sr):
            hx = -sg_w/2 + ix*ss
            hy = -sg_h/2 + iy*ss
            c = make_cyl(sd/2, wall_t + 2, 16)
            c.apply_translation([spx+hx, spy+hy, -body_h/2])
            body = apply_cutout(body, f"Hole({ix},{iy})", c)

    # ===== Top Face Cutouts =====
    print("\n[4] Top face openings...")
    
    # SOS button through-hole
    c = make_cyl(sos_r, wall_t + 2, SEGS)
    c.apply_translation([0, sos_y, body_h/2])
    body = apply_cutout(body, "SOS through-hole", c)
    
    # SOS recess (shallow ring around button)
    c = make_cyl(sos_r + 2.0, 0.5, SEGS)
    c.apply_translation([0, sos_y, body_h/2 - 0.25])
    body = apply_cutout(body, "SOS recess ring", c)
    
    # Inner part of ring should be shallower/not cut-through,
    # but since the through-hole already removed center material,
    # the recess just extends outward. This is fine.
    
    # LED
    c = make_cyl(led_d/2, wall_t + 2, 24)
    c.apply_translation([0, led_y, body_h/2])
    body = apply_cutout(body, "LED", c)
    
    # Flashlight
    c = make_cyl(flash_r, wall_t + 2, SEGS)
    c.apply_translation([0, flash_y, body_h/2])
    body = apply_cutout(body, "Flashlight", c)

    # ===== Side/Bottom Cutouts =====
    print("\n[5] Side and bottom features...")
    
    # Type-C
    c = make_box([wall_t + 2, tw, th])
    c.apply_translation([body_len/2, 0, 0])
    body = apply_cutout(body, "Type-C", c)
    
    # Motor mount pocket
    c = make_cyl(mr, 6, 24)
    c.apply_translation([mx, my, -body_h/2 + 3])
    body = apply_cutout(body, "Motor pocket", c)

    # ===== CLEAN =====
    print("\n[6] Cleaning mesh...")
    try:
        body.remove_unreferenced_vertices()
    except Exception:
        pass
    try:
        body.process(validate=True)
    except Exception:
        pass

    # ===== REPORT =====
    expected_body = body_len * body_wid * body_h
    ratio = body.volume / expected_body * 100

    print(f"\n=== Final Mesh ===")
    print(f"  Vertices: {len(body.vertices)}")
    print(f"  Faces: {len(body.faces)}")
    print(f"  Watertight: {body.is_watertight}")
    print(f"  Volume: {body.volume:.1f} mm^3 ({ratio:.1f}% of full solid)")

    # ===== EXPORT =====
    output_dir = os.path.dirname(os.path.abspath(__file__))
    stl_path = os.path.join(output_dir, 'keepsafe_body_v2.stl')
    obj_path = os.path.join(output_dir, 'keepsafe_body_v2.obj')
    
    print(f"\nExporting...")
    body.export(stl_path, file_type='stl')
    body.export(obj_path, file_type='obj')
    
    stl_size = os.path.getsize(stl_path) / 1024
    obj_size = os.path.getsize(obj_path) / 1024
    print(f"  STL: {stl_path} ({stl_size:.1f} KB)")
    print(f"  OBJ: {obj_path} ({obj_size:.1f} KB)")
    print("\nDone!")

if __name__ == '__main__':
    main()
