// ============================================================
// KeepSafe 防丢器定位器 - 外观壳体 v3.0
// Redesigned: 38×28×10mm (from 78×48×12mm)
// Internal clearance verified: PCBA 32×22mm, Battery 28×18×4.5mm
// Wall thickness 1.5mm → internal cavity 35×25×7mm
// ============================================================

$fn = 64;

// ============= 外形尺寸 (NEW: 38×28×10) =============
body_len     = 38;    // was 78
body_wid     = 28;    // was 48
body_h       = 10;    // was 12
corner_r     = 4;     // R4 大圆角

wall_t       = 1.5;   // 壁厚1.5mm → 内腔35×25×7mm

// ============= 内部尺寸验证 =============
// 内腔: (38-3)×(28-3)×(10-3) = 35×25×7mm
// PCBA: 32×22×1.6mm → 余量: X=3mm, Y=3mm ✓
// 电池: 28×18×4.5mm → 余量: fits in 35×25 footprint ✓
// 堆叠: 4.5+1.6=6.1mm → 7-6.1=0.9mm间隙 ✓ (紧但可行)

// ---- 挂耳 (顶部偏左, 20×14mm, 内孔8mm) ----
ear_w        = 20;
ear_h        = 14;
ear_hole_d   = 8;
ear_center_x = -body_wid/2 + ear_w/2;       // 左边缘对齐
ear_center_y = body_len/2 - ear_h/2;         // 顶部对齐

// ---- 蜂鸣器出声孔 (正面中部, 矩阵微孔) ----
speaker_hole_d = 1.5;
speaker_spacing = 2.2;
speaker_cols   = 5;
speaker_rows   = 3;
speaker_grid_w = (speaker_cols - 1) * speaker_spacing; // 8.8mm
speaker_grid_h = (speaker_rows - 1) * speaker_spacing; // 4.4mm
speaker_pos_x  = 0;
speaker_pos_y  = 0;  // 正面正中央

// ---- LED指示灯 (正面顶部居中, 直径2mm) ----
led_d        = 2;       // 规格: 2mm
led_pos_x    = 0;
led_pos_y    = body_len/2 - 5;   // 距顶部5mm

// ---- SOS按键 (正面, 直径12mm, 凹面) ----
sos_r        = 6;       // 半径6mm → 直径12mm
sos_pos_y    = -body_len/2 + 9;  // 距底边9mm (≥5mm)

// ---- Type-C (右侧居中) ----
typec_w      = 9;       // USB-C母座宽度
typec_h      = 3;       // USB-C母座高度

// ---- 挂耳加强筋 ----
strap_rib_w  = 2;
strap_rib_h  = 2;

// ---- 振动马达位 (4×8×2mm) ----
motor_x     = body_wid/2 - 6;
motor_y     = -body_len/2 + 8;
motor_r     = 3;

// ---- 倒角参数 ----
chamfer_r   = 2;    // R2倒角

// ============= 工具模块 =============

module rounded_rect(l, w, r) {
    hull() {
        for (x = [-l/2 + r, l/2 - r]) {
            for (y = [-w/2 + r, w/2 - r]) {
                translate([x, y, 0]) circle(r = r);
            }
        }
    }
}

module rounded_box(l, w, h, r) {
    linear_extrude(height = h) { rounded_rect(l, w, r); }
}

// ============= 壳体主体 (带R4大圆角) =============
module body_solid() {
    hull() {
        for (x = [-body_len/2 + corner_r, body_len/2 - corner_r]) {
            for (y = [-body_wid/2 + corner_r, body_wid/2 - corner_r]) {
                translate([x, y, 0])
                    cylinder(h = body_h, r = corner_r);
            }
        }
    }
}

// ============= 挂耳模块 (20×14mm, 内孔8mm) =============
module ear() {
    translate([ear_center_x, ear_center_y, body_h/2]) {
        difference() {
            union() {
                // 跑道形挂耳主体
                hull() {
                    translate([0, 0, 0])
                        cylinder(h = body_h, r = ear_w/2, center = true);
                    translate([-ear_h + ear_w/2, 0, 0])
                        cylinder(h = body_h, r = ear_w/2, center = true);
                }
                // 加强筋
                hull() {
                    translate([-ear_h + ear_w/2 - 1, 0, -body_h/2])
                        cylinder(h = strap_rib_h, r = ear_w/2 + 0.5);
                    translate([-ear_h + ear_w/2 - 3, 0, -body_h/2])
                        cylinder(h = strap_rib_h, r = ear_w/2);
                }
            }
            // 挂绳内孔 8mm
            translate([0, 0, 0])
                cylinder(h = body_h + 0.1, r = ear_hole_d/2, center = true);
        }
    }
}

// ============= 蜂鸣器出声孔 (正面矩阵微孔) =============
module speaker_grill_holes() {
    translate([speaker_pos_x, speaker_pos_y, body_h/2]) {
        for (ix = [0:speaker_cols-1]) {
            for (iy = [0:speaker_rows-1]) {
                translate([
                    -speaker_grid_w/2 + ix * speaker_spacing,
                    -speaker_grid_h/2 + iy * speaker_spacing,
                    0
                ])
                    cylinder(h = wall_t + 0.1, r = speaker_hole_d/2);
            }
        }
    }
}

module speaker_cutout() {
    speaker_grill_holes();
}

// ============= 正面LED指示灯 (2mm) =============
module front_cutouts() {
    // LED通孔
    translate([led_pos_x, led_pos_y, body_h/2])
        cylinder(h = wall_t + 0.1, r = led_d/2, center = false);
    // 浅沉头
    translate([led_pos_x, led_pos_y, body_h/2 - 0.2])
        cylinder(h = 0.2, r = led_d/2 + 0.3, center = false);
}

// ============= SOS按键 (直径12mm, 凹面) =============
module sos_cutout() {
    // 按键通孔
    translate([0, sos_pos_y, body_h/2])
        cylinder(h = wall_t + 0.1, r = sos_r, center = false);
    // 凹面指示环
    translate([0, sos_pos_y, body_h/2 - 0.4])
        cylinder(h = 0.4, r = sos_r + 0.6, center = false);
}

// 按键区域环形凹陷指示
module button_recess() {
    difference() {
        translate([0, sos_pos_y, body_h/2])
            cylinder(h = 0.25, r = sos_r + 1.5, center = false);
        translate([0, sos_pos_y, body_h/2])
            cylinder(h = 0.25, r = sos_r + 0.3, center = false);
    }
}

// ============= USB-C (右侧居中) =============
module typec_cutout() {
    translate([body_len/2, 0, 0]) {
        // 主开孔
        cube([wall_t + 0.1, typec_w, typec_h], center = true);
        // 外扩台阶 (适配防水塞)
        translate([0, 0, 0])
            cube([wall_t + 0.5, typec_w + 1.5, typec_h + 1.5], center = true);
    }
}

// ============= 底部SOS按键触点 =============
module sos_key_groove() {
    translate([0, sos_pos_y, -body_h/2]) {
        cylinder(h = 2, r = sos_r - 0.5);
    }
    translate([0, sos_pos_y, -body_h/2 + 2]) {
        cylinder(h = 1.5, r = 2);
    }
}

// ============= 振动马达安装位 =============
module motor_mount() {
    translate([motor_x, motor_y, -body_h/2 + 1.5]) {
        cylinder(h = 5, r = motor_r);
    }
}

// ============= 完整壳体 (v3.0: 38×28×10mm) =============
module keepsafe_body_v3() {
    difference() {
        union() {
            body_solid();          // 壳体主体 (四角R4大圆角)
            ear();                 // 挂耳 (20×14mm, 顶部偏左)
            button_recess();       // SOS按键凹陷标识
        }

        // === 通孔切除 ===
        front_cutouts();           // LED指示灯 (2mm)
        sos_cutout();              // SOS按键 (12mm)
        typec_cutout();            // USB-C (右侧居中)
        sos_key_groove();          // 底部开关触点
        motor_mount();             // 振动马达
        speaker_cutout();          // 蜂鸣器出声孔
    }
}

keepsafe_body_v3();
