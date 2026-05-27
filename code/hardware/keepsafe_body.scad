// ============================================================
// KeepSafe 防丢器定位器 - 外观壳体参数化模型 v2.0
// Updated based on boss's corrected design spec: 78×48×12mm
// Changes: R8→R4, SOS 22mm→12mm, Ear 10×14→20×14, Added flashlight
// ============================================================

$fn = 64;

// ============= 外形尺寸 =============
body_len     = 78;
body_wid     = 48;
body_h       = 12;
corner_r     = 4;     // 四角圆角半径（修正：R8→R4）

wall_t       = 1.5;

// ---- 挂耳 (偏心) ----
ear_w        = 20;    // 挂耳总宽（修正：10→20mm）
ear_h        = 14;    // 挂耳总高
ear_hole_d   = 8;     // 挂耳内孔直径
ear_center_x = 5;
ear_center_y = body_wid/2 - ear_center_x - ear_w/2;

// ---- 喇叭区 (背面) ----
speaker_w    = 20;
speaker_h    = 14;
speaker_d    = 0.8;

// ---- 指示灯 (正面) ----
led_d        = 2.5;
led_pos_x    = 0;
led_pos_y    = body_len/2 - 8;

// ---- SOS键 (正面偏下, 直径12mm) ----
sos_r        = 6;     // 半径（修正：11→6mm, 直径12mm）
sos_pos_y    = -body_len/2 + 12;

// ---- 电筒 (顶部, 直径12mm) ----
flash_r      = 6;     // 电筒开孔半径 (12mm直径)
flash_pos_x  = 0;
flash_pos_y  = body_len/2 - 6;

// ---- Type-C (右侧) ----
typec_w      = 10;
typec_h      = 4;

// ---- 挂耳跑道防套结构 ----
strap_rib_w  = 2;
strap_rib_h  = 3;

// ---- 振动马达位 ----
motor_x     = body_wid/2 - 8;
motor_y     = -body_len/2 + 10;
motor_r     = 4;

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

// ============= 挂耳模块（20×14mm偏心） =============
module ear() {
    translate([ear_center_x, ear_center_y, body_h/2]) {
        difference() {
            union() {
                // 挂耳主体 (偏心跑道形)
                hull() {
                    translate([0, 0, 0]) 
                        cylinder(h = body_h, r = ear_w/2, center = true);
                    translate([-ear_h + ear_w/2, 0, 0])
                        cylinder(h = body_h, r = ear_w/2, center = true);
                }
                // 加强筋
                hull() {
                    translate([-ear_h + ear_w/2 - 2, 0, -body_h/2])
                        cylinder(h = strap_rib_h, r = ear_w/2 + 1);
                    translate([-ear_h + ear_w/2 - 4, 0, -body_h/2])
                        cylinder(h = strap_rib_h, r = ear_w/2);
                }
            }
            // 挂绳孔
            translate([0, 0, 0])
                cylinder(h = body_h + 0.1, r = ear_hole_d/2, center = true);
        }
    }
}

// ============= 壳体外形 =============
module body_solid() {
    rounded_box(body_len, body_wid, body_h, corner_r);
}

// ============= 正面开孔 =============
module front_cutouts() {
    // 指示灯 (SOS上方, 直径2.5mm)
    translate([led_pos_x, led_pos_y, body_h/2])
        cylinder(h = wall_t + 0.1, r = led_d/2, center = false);
    
    // 指示灯装饰圈
    translate([led_pos_x, led_pos_y, body_h/2 - 0.3])
        cylinder(h = 0.3, r = led_d/2 + 0.5, center = false);
}

// ============= SOS键 (12mm直径) =============
module sos_cutout() {
    // SOS键孔
    translate([0, sos_pos_y, body_h/2])
        cylinder(h = wall_t + 0.1, r = sos_r, center = false);
    // 触感凹槽
    translate([0, sos_pos_y, body_h/2 - 0.5])
        cylinder(h = 0.5, r = sos_r + 0.5, center = false);
}

// ============= 电筒开孔 (顶部12mm) =============
module flashlight_cutout() {
    // 顶部LED电筒开孔
    translate([flash_pos_x, flash_pos_y, body_h/2])
        cylinder(h = wall_t + 0.1, r = flash_r, center = false);
    // 聚光透镜台阶
    translate([flash_pos_x, flash_pos_y, body_h/2 - 0.8])
        cylinder(h = 0.8, r = flash_r - 0.5, center = false);
}

// ============= Type-C =============
module typec_cutout() {
    translate([body_len/2, 0, 0]) {
        cube([wall_t + 0.1, typec_w, typec_h], center = true);
        translate([0, 0, 0])
            cube([wall_t + 0.5, typec_w + 1.5, typec_h + 1.5], center = true);
    }
}

// ============= 底部按键触点 =============
module sos_key_groove() {
    translate([0, sos_pos_y, -body_h/2]) {
        cylinder(h = 2, r = sos_r - 0.5);
    }
    translate([0, sos_pos_y, -body_h/2 + 2]) {
        cylinder(h = 1.5, r = 2);
    }
}

// ============= 振动马达位 =============
module motor_mount() {
    translate([motor_x, motor_y, -body_h/2 + 2]) {
        cylinder(h = 6, r = motor_r);
    }
}

// ============= 背面喇叭出声孔 =============
module rear_speaker_grill() {
    translate([0, -body_len/4, -body_h/2]) {
        for (ix = [0:4]) {
            for (iy = [0:3]) {
                translate([-speaker_w/2 + 2 + ix*4, -speaker_h/2 + 2 + iy*3.5, 0])
                    cylinder(h = wall_t + 0.1, r = speaker_d/2);
            }
        }
    }
}

// ============= 完整壳体 =============
module keepsafe_body() {
    difference() {
        union() {
            body_solid();
            ear();
        }
        // 正面
        front_cutouts();
        sos_cutout();
        // 顶部电筒
        flashlight_cutout();
        // 侧面
        typec_cutout();
        // 底部
        sos_key_groove();
        motor_mount();
        // 背面喇叭
        rear_speaker_grill();
    }
}

keepsafe_body();
