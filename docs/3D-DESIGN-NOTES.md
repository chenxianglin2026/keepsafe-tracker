# KeepSafe 3D Design Notes

Date: 2026-05-27
Version: v3.0 (Redesign from 78×48×12mm to 38×28×10mm)

---

## 1. Dimension Change Summary

| Parameter | Old (v2) | New (v3) | Notes |
|-----------|----------|----------|-------|
| Body Length | 78mm | 38mm | 51% reduction |
| Body Width | 48mm | 28mm | 42% reduction |
| Body Height | 12mm | 10mm | 17% reduction |
| Corner Radius | R4 | R4 | Unchanged (kept per spec) |
| Wall Thickness | 1.5mm | 1.5mm | Kept for structural integrity |
| Ear | 20×14mm | 20×14mm | Unchanged per spec |
| Ear Hole | 8mm | 8mm | Unchanged |
| SOS Button | 12mm | 12mm | Already correct in v2 |
| LED | 2.5mm | 2.0mm | Matching spec exactly |
| Buzzer Hole Size | 2.0mm | 1.5mm | Scaled down proportionally |
| Buzzer Grid | 5×3 | 5×3 | Same grid density |

## 2. Internal Clearance Analysis

Internal cavity after wall thickness (1.5mm per side):
**35 × 25 × 7 mm**

### Component fit verification

| Component | Dimensions | Fit Check |
|-----------|-----------|-----------|
| PCBA | 32 × 22 × 1.6mm | OK — 1.5mm clearance each side in X/Y |
| Battery | 28 × 18 × 4.5mm | OK — fits within 35×25 footprint |
| Buzzer | 8 × 8 × 3mm | OK — fits above PCBA |
| Motor | 4 × 8 × 2mm | OK — fits in bottom cavity |
| Stack: Battery + PCBA | 4.5 + 1.6 = 6.1mm | OK — 7mm cavity, 0.9mm clearance |

**WARNING: Tight vertical clearance**
The 0.9mm gap between component stack (6.1mm) and cavity height (7mm) is very tight.
Recommendations:
- Consider reducing wall thickness to 1.2mm (cavity = 35.6×25.6×7.6mm, 1.5mm clearance)
- Ensure PCBA sits directly on battery with no additional spacer
- Use thin flexible PCB (0.8mm) instead of standard 1.6mm if needed

## 3. Removed Features

| Feature | Reason |
|---------|--------|
| Flashlight cutout (12mm) | Not in 38×28mm spec |
| Standalone lanyard hole (4mm) | Replaced by ear (20×14mm) |
| Bottom speaker position | Moved to front face per spec |

## 4. Feature Positioning (Front View)

```
 ┌──────────────────────────────────┐
 │   ● LED (2mm, top center)        │ ← y = body_len/2 - 5 = 14mm
 │                                  │
 │   ∷∷∷∷∷  Buzzer Grille          │ ← y = 0 (center)
 │   ∷∷∷∷∷  (5×3 micro-holes)      │
 │   ∷∷∷∷∷                         │
 │                                  │
 │      ⊚ SOS Button (Φ12mm)       │ ← y = -10mm from center
 │      凹面防误触                   │    = 9mm from bottom edge
 └──────────────────────────────────┘
```

## 5. Ear Position

- Location: Top-left corner, extending from body
- Shape: Race-track profile (20×14mm)
- Inner hole: 8mm diameter
- Protrudes ~4mm from left edge, ~3mm from top edge
- Reinforcement rib on bottom side

## 6. USB-C Position

- Right side (body_len/2 = +19mm in X)
- Vertically centered (Y=0)
- Height centered on 10mm body (Z=0)
- Stepped cutout for waterproof plug receptacle

## 7. Files Modified

| File | Change |
|------|--------|
| `code/hardware/keepsafe_body_v2.scad` | Complete rewrite with 38×28×10 params |
| `code/hardware/blender/keepsafe_enclosure.py` | Updated W/H/D/CORNER_R and all internal component sizes |

## 8. OpenSCAD STL Generation

OpenSCAD was not available on this system. To generate STL:
```
openscad -o keepsafe_v3_38x28x10.stl code/hardware/keepsafe_body_v2.scad
```

## 9. Known Risks

1. **Wall thickness vs durability**: 1.5mm PC+ABS at 38×28mm is structurally fine, but drop-testing needed
2. **Ear strength**: 20mm wide ear on 28mm body has large leverage — reinforcement rib present but pull-test recommended
3. **Thermal**: Tiny internal volume may cause heat buildup during 4G transmission — ventilation openings limited due to IP65
4. **Assembly**: Snap-fit clips may be hard to mold at this scale — consider ultrasonic welding as alternative
5. **Antenna**: 4G+GPS antenna at 10×3×2mm needs non-metallic zone on shell; confirm material choice does not attenuate signal
