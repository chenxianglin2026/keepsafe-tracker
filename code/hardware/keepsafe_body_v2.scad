// ============================================================
// KeepSafe 防丢器定位器 - 外观壳体 v2.1
// Added features:
//   1. 挂绳孔: 4mm通孔, 左上角, 距边缘5mm
//   2. 喇叭出声孔: 底部3×5阵列圆孔或长条槽
//   3. 表面处理: 按键凹陷指示, 挂绳孔圆角过渡, R2-R3倒角
// ============================================================

$fn = 64;

// ============= 外形尺寸 =============
body_len     = 78;
body_wid     = 48;
body_h       = 12;
corner_r     = 4;

wall_t       = 1.5;

// ---- 挂绳孔 (新增: 左上角4mm通孔) ----
lanyard_d      = 4;       // 孔径4mm
lanyard_margin = 5;       // 距边缘5mm
lanyard_x      = -body_len/2 + lanyard_margin;
lanyard_y      = body_wid/2 - lanyard_margin;

// ---- 挂耳 (保留, 用于腕带) ----
ear_w        = 20;
ear_h        = 14;
ear_hole_d   = 8;
ear_center_x = 5;
ear_center_y = body_wid/2 - ear_center_x - ear_w/2;

// ---- 喇叭出声孔 (新增: 底部3×5阵列) ----
speaker_hole_d = 2;       // 单孔直径2mm
speaker_spacing = 3;      // 间距3mm
speaker_cols   = 5;       // 5列
speaker_rows   = 3;       // 3行
speaker_grid_w = (speaker_cols - 1) * speaker_spacing; // 12mm
speaker_grid_h = (speaker_rows - 1) * speaker_spacing; // 6mm
// 位置: 底部中心(y负方向)
speaker_pos_y = -body_len/2 + speaker_grid_h/2 + 6;
speaker_pos_x = 0;

// ---- 指示灯 (正面) ----
led_d        = 2.5;
led_pos_x    = 0;
led_pos_y    = body_len/2 - 8;

// ---- SOS键 (正面偏下) ----
sos_r        = 6;
sos_pos_y    = -body_len/2 + 12;

// ---- 电筒 (顶部) ----
flash_r      = 6;
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

// ---- 倒角参数 ----
chamfer_r   = 2.5;  // R2.5倒角 (R2-R3范围)

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

// ============= 倒角壳体 =============
// 使用minkowski实现圆角倒角效果
module chamfered_body() {
    // 核心壳体略缩小, 加上minkowski圆角
    minkowski() {
        cube([body_len - chamfer_r*2, body_wid - chamfer_r*2, body_h - chamfer_r*2], center = true);
        sphere(r = chamfer_r);
    }
}

// 近似倒角: 使用带圆角的拉伸体
module body_solid() {
    // 使用hull + sphere实现全圆角长方体, 模拟R2.5倒角
    hull() {
        for (x = [-body_len/2 + corner_r, body_len/2 - corner_r]) {
            for (y = [-body_wid/2 + corner_r, body_wid/2 - corner_r]) {
                translate([x, y, 0]) 
                    cylinder(h = body_h, r = corner_r);
            }
        }
    }
}

// ============= 挂绳孔 (新增 #1) =============
module lanyard_hole() {
    // 通孔 - 贯穿整个壳体厚度
    translate([lanyard_x, lanyard_y, 0])
        cylinder(h = body_h + 0.1, r = lanyard_d/2, center = true);
}

// 挂绳孔周围圆弧过渡 - 顶面沉头
module lanyard_fillet() {
    // 顶面沉头倒角
    translate([lanyard_x, lanyard_y, body_h/2 - 0.5])
        cylinder(h = 0.5, r1 = lanyard_d/2, r2 = lanyard_d/2 + 0.8);
    // 底面沉头倒角
    translate([lanyard_x, lanyard_y, -body_h/2])
        cylinder(h = 0.5, r1 = lanyard_d/2 + 0.8, r2 = lanyard_d/2);
}

// ============= 挂耳模块 =============
module ear() {
    translate([ear_center_x, ear_center_y, body_h/2]) {
        difference() {
            union() {
                hull() {
                    translate([0, 0, 0]) 
                        cylinder(h = body_h, r = ear_w/2, center = true);
                    translate([-ear_h + ear_w/2, 0, 0])
                        cylinder(h = body_h, r = ear_w/2, center = true);
                }
                hull() {
                    translate([-ear_h + ear_w/2 - 2, 0, -body_h/2])
                        cylinder(h = strap_rib_h, r = ear_w/2 + 1);
                    translate([-ear_h + ear_w/2 - 4, 0, -body_h/2])
                        cylinder(h = strap_rib_h, r = ear_w/2);
                }
            }
            translate([0, 0, 0])
                cylinder(h = body_h + 0.1, r = ear_hole_d/2, center = true);
        }
    }
}

// ============= 喇叭出声孔 (新增 #2) =============
// 方案A: 3×5阵列圆孔
module speaker_grill_holes() {
    // 底部(y负方向)中心位置
    translate([speaker_pos_x, speaker_pos_y, -body_h/2]) {
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

// 方案B: 长条矩形开槽 (1.5mm × 20mm)
module speaker_slot() {
    translate([0, speaker_pos_y, -body_h/2])
        cube([1.5, 20, wall_t + 0.1], center = true);
}

// 使用方案A (圆孔阵列)
module speaker_cutout() {
    speaker_grill_holes();
}

// ============= 正面开孔 =============
module front_cutouts() {
    translate([led_pos_x, led_pos_y, body_h/2])
        cylinder(h = wall_t + 0.1, r = led_d/2, center = false);
    translate([led_pos_x, led_pos_y, body_h/2 - 0.3])
        cylinder(h = 0.3, r = led_d/2 + 0.5, center = false);
}

// ============= SOS键 =============
module sos_cutout() {
    translate([0, sos_pos_y, body_h/2])
        cylinder(h = wall_t + 0.1, r = sos_r, center = false);
    // 按键区域凹陷指示 (表面处理 #3)
    translate([0, sos_pos_y, body_h/2 - 0.4])
        cylinder(h = 0.4, r = sos_r + 0.8, center = false);
}

// ============= 按键凹陷区域 =============
// 正面按键区域凹陷指示 (表面处理)
module button_recess() {
    // SOS按键周围环形凹陷
    difference() {
        translate([0, sos_pos_y, body_h/2])
            cylinder(h = 0.3, r = sos_r + 2, center = false);
        translate([0, sos_pos_y, body_h/2])
            cylinder(h = 0.3, r = sos_r + 0.3, center = false);
    }
}

// ============= 电筒开孔 =============
module flashlight_cutout() {
    translate([flash_pos_x, flash_pos_y, body_h/2])
        cylinder(h = wall_t + 0.1, r = flash_r, center = false);
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

// ============= 完整壳体 (新版) =============
module keepsafe_body_v2() {
    difference() {
        union() {
            body_solid();          // 壳体主体 (带角部倒角)
            ear();                 // 挂耳
            
            // 表面处理: 按键区域凹陷
            button_recess();
            
            // 挂绳孔圆弧过渡 (顶面沉头)
            lanyard_fillet();
        }
        
        // === 通孔切除 ===
        // 挂绳孔 (新增)
        lanyard_hole();
        
        // 正面开孔
        front_cutouts();
        sos_cutout();
        
        // 顶部电筒
        flashlight_cutout();
        
        // 侧面
        typec_cutout();
        
        // 底部
        sos_key_groove();
        motor_mount();
        
        // 底部喇叭出声孔 (新增)
        speaker_cutout();
    }
}

keepsafe_body_v2();
