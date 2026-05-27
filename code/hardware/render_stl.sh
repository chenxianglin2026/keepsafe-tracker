#!/bin/bash
# Render STL files from OpenSCAD source
# Requires: OpenSCAD installed (https://openscad.org/)
#
# macOS:   brew install openscad
# Ubuntu:  sudo apt install openscad
# Windows: download from openscad.org

# Set paths
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
BODY_SCAD="$SCRIPT_DIR/keepsafe_body.scad"
BODY_V2_SCAD="$SCRIPT_DIR/keepsafe_body_v2.scad"
LAYOUT_SCAD="$SCRIPT_DIR/keepsafe_internal_layout.scad"

echo "=== KeepSafe OpenSCAD STL Renderer ==="

# Check if openscad is available
if ! command -v openscad &> /dev/null; then
    echo "ERROR: openscad not found. Please install:"
    echo "  macOS: brew install openscad"
    echo "  Linux: sudo apt install openscad"
    echo "  Or download from https://openscad.org/"
    exit 1
fi

echo "Rendering body model (v1)..."
openscad -o "$SCRIPT_DIR/keepsafe_body.stl" "$BODY_SCAD"
echo "  -> keepsafe_body.stl"

echo "Rendering body model (v2 - with lanyard hole, speaker grille, surface features)..."
openscad -o "$SCRIPT_DIR/keepsafe_body_v2.stl" "$BODY_V2_SCAD"
echo "  -> keepsafe_body_v2.stl"

echo "Rendering internal layout model..."
openscad -o "$SCRIPT_DIR/keepsafe_internal_layout.stl" "$LAYOUT_SCAD"
echo "  -> keepsafe_internal_layout.stl"

echo ""
echo "Done! Both STL files have been generated."
echo "  - keepsafe_body.stl            (original appearance shell)"
echo "  - keepsafe_body_v2.stl          (v2 with lanyard hole, speaker grille, surface features)"
echo "  - keepsafe_internal_layout.stl  (internal stackup)"
