// ============================================================
// KeepSafe 防丢器定位器 - 内部堆叠布局
// Internal Stackup Layout v1.0 | Mech-Dev
// ============================================================

// ============= 全局参数 =============
$fn = 64;

// ---- 外形尺寸 (参考壳体) ----
body_len     = 78;
body_wid     = 48;
body_h       = 12;
wall_t       = 1.5;
corner_r     = 8;

// ---- 内腔尺寸 (减壁厚) ----
inner_len    = body_len - 2*wall_t;   // 75
inner_wid    = body_wid - 2*wall_t;   // 45
inner_h      = body_h - 2*wall_t;     // 9
inner_z_bot  = -body_h/2 + wall_t;    // 内腔底部 Z = -4.5
inner_z_top  = body_h/2 - wall_t;     // 内腔顶部 Z = +4.5

// ---- 电池 703048 ---- (下半大区, 靠底部)
bat_thick    = 7;     // 厚度 (Z)
bat_w        = 30;    // 宽 (X)
bat_len      = 48;    // 长 (Y)
bat_pos_y    = -body_len/2 + wall_t + bat_len/2 + 2; // Y中心 (靠底部)
// 电池贴在下壳内壁，电池底部 Z = inner_z_bot = -4.5
bat_pos_z    = inner_z_bot + bat_thick/2; // 电池中心 Z

// ---- 备选电池 603048 ----
bat_alt_thick = 6;

// ---- PCB主板 ---- (中间主体区)
pcb_len       = 42;   // X
pcb_w         = 32;   // Y
pcb_thick     = 1.6;  // Z (标准PCB厚度)
pcb_pos_y     = 2;    // Y中心 (中间区)
// PCB放在电池上方: PCB底面 = 电池顶面 + 1mm间隙
pcb_z_bot     = bat_pos_z + bat_thick/2 + 1.0; // PCB底面 Z
pcb_pos_z     = pcb_z_bot + pcb_thick/2;

// ---- SIM卡槽 (PCB上) ----
sim_len       = 15;   // X
sim_w         = 12;   // Y
sim_thick     = 1.5;  // Z (含卡座)

// ---- 4G+GPS双模陶瓷天线 (左上区, 远离挂耳金属) ----
ant_d         = 14;    // 天线直径 (圆形陶瓷)
ant_thick     = 3;     // 天线厚度
ant_pos_x     = -inner_wid/2 + ant_d/2 + 3;  // X: 左边缘
ant_pos_y     = body_len/2 - wall_t - ant_d/2 - 3; // Y: 顶部
ant_pos_z     = inner_z_bot + 1.5; // 贴底

// ---- 喇叭 (MK 20x14mm腔体, 上中区) ----
speaker_len   = 20;    // X
speaker_w     = 14;    // Y
speaker_h     = 5;     // Z (腔体高度)
speaker_pos_y = body_len/2 - wall_t - speaker_w/2 - 4; // 上中区
speaker_pos_z = inner_z_bot + speaker_h/2 + 1;

// ---- SOS硅胶按键 (底部) ----
sos_r         = 11;    // 按键半径
sos_thick     = 2;     // 硅胶厚度
sos_pos_y     = -body_len/2 + wall_t + sos_r + 2;

// ---- 振动马达 (底部) ----
motor_d       = 8;     // 直径
motor_h       = 3;     // 高度
motor_pos_x   = inner_wid/2 - motor_d/2 - 3;
motor_pos_y   = -body_len/2 + wall_t + 8;
motor_pos_z   = inner_z_bot + motor_h/2;

// ---- 加速度计 LIS3DH (3x3mm LGA, PCB顶面) ----
lis3dh_len    = 3;
lis3dh_w      = 3;
lis3dh_thick  = 0.85;
lis3dh_pos_x  = 10;
lis3dh_pos_y  = pcb_pos_y - 10;
lis3dh_pos_z  = pcb_pos_z + pcb_thick/2 + lis3dh_thick/2;

// ---- Type-C 连接器 (右侧) ----
typec_body_w  = 8;
typec_body_h  = 3.5;
typec_body_d  = 5.5;
typec_pos_y   = 0; // 右侧居中

// ============= 工具模块 =============
module rounded_rect(l, w, r) {
    hull() {
        for (x = [-l/2 + r, l/2 - r])
            for (y = [-w/2 + r, w/2 - r])
                translate([x, y, 0]) circle(r = r);
    }
}

module rounded_box(l, w, h, r) {
    linear_extrude(height = h) rounded_rect(l, w, r);
}

// ============= 壳体参考 (透明线框) =============
module body_reference() {
    %translate([0, 0, 0])
        rounded_box(body_len, body_wid, body_h, corner_r);
}

// ============= 内腔边界 (半透参考) =============
module cavity_reference() {
    %translate([0, 0, 0])
        rounded_box(inner_len, inner_wid, inner_h, corner_r);
}

// ============= 电池 703048 =============
module battery_703048() {
    color("Coral", 0.85) {
        translate([0, bat_pos_y, bat_pos_z])
            cube([bat_w, bat_len, bat_thick], center = true);
    }
    // 标识
    translate([0, bat_pos_y, bat_pos_z + bat_thick/2 + 0.5])
        color("Red") linear_extrude(0.2)
            text("703048 800mAh", size=3.5, halign="center", valign="center");
}

// ============= 备选电池 603048 (偏移显示) =============
module battery_603048() {
    color("Orange", 0.5) {
        translate([0, -body_len/2 + wall_t + bat_alt_len/2 + 2, inner_z_bot + bat_alt_thick/2])
            cube([bat_w, bat_alt_len, bat_alt_thick], center = true);
    }
}

// ============= PCB主板 =============
module pcb_main() {
    color("DarkGreen", 0.85) {
        translate([0, pcb_pos_y, pcb_pos_z])
            cube([pcb_len, pcb_w, pcb_thick], center = true);
    }
    // 主控标记
    translate([-8, pcb_pos_y + 6, pcb_pos_z + pcb_thick/2 + 0.2])
        color("White") linear_extrude(0.2)
            text("ESP32-S3", size=2.5, halign="center");
    // 4G模组标记
    translate([8, pcb_pos_y + 6, pcb_pos_z + pcb_thick/2 + 0.2])
        color("White") linear_extrude(0.2)
            text("Air780E", size=2.5, halign="center");
    // SIM卡槽
    translate([5, pcb_pos_y - 6, pcb_pos_z + pcb_thick/2 + sim_thick/2])
        color("Gold", 0.7)
            cube([sim_len, sim_w, sim_thick], center = true);
}

// ============= 4G+GPS天线 (左上区) =============
module antenna() {
    color("Gold", 0.85) {
        translate([ant_pos_x, ant_pos_y, ant_pos_z])
            cylinder(h = ant_thick, r = ant_d/2);
    }
    translate([ant_pos_x, ant_pos_y - ant_d/2 - 2, ant_pos_z + ant_thick + 0.2])
        color("Yellow") linear_extrude(0.2)
            text("4G+GPS", size=2, halign="center");
}

// ============= 喇叭 =============
module speaker() {
    color("Gray", 0.85) {
        translate([0, speaker_pos_y, speaker_pos_z])
            cube([speaker_len, speaker_w, speaker_h], center = true);
    }
    translate([0, speaker_pos_y - speaker_w/2 - 2, speaker_pos_z + speaker_h/2 + 0.2])
        color("White") linear_extrude(0.2)
            text("MK 20x14mm", size=2.5, halign="center");
}

// ============= SOS硅胶按键 =============
module sos_key() {
    color("DimGray", 0.7) {
        translate([0, sos_pos_y, inner_z_bot])
            cylinder(h = sos_thick, r = sos_r);
    }
    translate([0, sos_pos_y, inner_z_bot + sos_thick + 0.2])
        color("White") linear_extrude(0.2)
            text("SOS", size=3, halign="center");
}

// ============= 振动马达 =============
module motor() {
    color("Silver", 0.85) {
        translate([motor_pos_x, motor_pos_y, motor_pos_z])
            cylinder(h = motor_h, r = motor_d/2);
    }
}

// ============= LIS3DH 加速度计 =============
module lis3dh() {
    color("Blue", 0.85) {
        translate([lis3dh_pos_x, lis3dh_pos_y, lis3dh_pos_z])
            cube([lis3dh_len, lis3dh_w, lis3dh_thick], center = true);
    }
}

// ============= Type-C 连接器 =============
module typec_connector() {
    color("Silver", 0.75) {
        translate([inner_wid/2 - typec_body_d/2, typec_pos_y, inner_z_bot + typec_body_h/2 + 0.5])
            cube([typec_body_d, typec_body_w, typec_body_h], center = true);
    }
}

// ============= 完整的内部堆叠布局 =============
module keepsafe_internal_layout() {
    // 壳体参考线框
    body_reference();
    cavity_reference();
    
    // Z向堆叠顺序 (从下到上):
    // Layer 0: 下壳壁 (wall_t=1.5mm)
    
    // Layer 1: SOS硅胶按键 + 振动马达 (贴底)
    sos_key();
    motor();
    
    // Layer 2: 天线 (贴底, 左上区)
    antenna();
    
    // Layer 3: Type-C连接器 (右侧)
    typec_connector();
    
    // Layer 4: 电池 703048 (下半大区, 贴底, Z占7mm)
    battery_703048();
    
    // Layer 5: 喇叭 (上中区)
    speaker();
    
    // Layer 6: PCB主板 (电池上方, 中间主体区)
    pcb_main();
    
    // Layer 7: LIS3DH 加速度计 (PCB顶面)
    lis3dh();
    
    // 备选电池 (603048, 半透显示在壳体外部右侧用于对比)
    translate([body_wid/2 + 10, 0, 0]) 
        battery_603048();
}

// ============= 渲染 =============
keepsafe_internal_layout();
