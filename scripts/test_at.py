#!/usr/bin/env python3
"""
test_at.py — KeepSafe Air780EG AT 指令快速验证脚本

功能:
  1. 自动检测 Air780EG (EC618) 模组串口
  2. 执行基础 AT 指令测试序列: AT → AT+CSQ → AT+CGPSINFO
  3. 支持扩展测试: 网络注册/SIM卡/固件版本/MQTT状态
  4. 输出测试报告

依赖: pyserial (pip3 install pyserial)
用法:
  python3 test_at.py                    # 自动检测串口并运行基础测试
  python3 test_at.py --port /dev/cu.xxx # 指定串口
  python3 test_at.py --full             # 运行完整测试套件
  python3 test_at.py --list             # 仅列出可用串口
"""

import serial
import serial.tools.list_ports
import sys
import time
import argparse
import re
from typing import Optional, List, Tuple


# ============================================================
# 配置
# ============================================================

DEFAULT_BAUD = 115200
DEFAULT_TIMEOUT = 3.0          # 串口读取超时(秒)
AT_CMD_TIMEOUT = 5.0           # AT 指令响应超时(秒)
AIR780EG_VID_PID = [
    # Air780EG 常见 USB-Serial 芯片
    ("1A86", "7523"),  # CH340
    ("1A86", "55D4"),  # CH343
    ("10C4", "EA60"),  # CP210x
    ("0403", "6001"),  # FT232
]

# ============================================================
# 串口检测
# ============================================================

def list_serial_ports():
    """列出所有可用串口"""
    ports = serial.tools.list_ports.comports()
    return sorted(ports, key=lambda p: p.device)


def detect_air780eg() -> Optional[str]:
    """
    自动检测 Air780EG 模组串口。
    策略:
      1. 按 VID/PID 匹配已知 USB-Serial 芯片
      2. 按描述关键词匹配 ("USB Serial", "CH340", "CP210", "Air780")
      3. 对候选串口发送 AT 指令验证响应
    """
    ports = list_serial_ports()
    candidates = []

    for port in ports:
        # 策略1: VID/PID 匹配
        if port.vid and port.pid:
            vid_pid = f"{port.vid:04X}:{port.pid:04X}"
            for known_vid, known_pid in AIR780EG_VID_PID:
                if port.vid == int(known_vid, 16) and port.pid == int(known_pid, 16):
                    candidates.append(port.device)
                    break
        # 策略2: 描述符匹配
        description = f"{port.description or ''} {port.manufacturer or ''}".lower()
        if any(kw in description for kw in ["usb serial", "ch340", "cp210", "air780", "usb-serial"]):
            if port.device not in candidates:
                candidates.append(port.device)

    if not candidates:
        # 回退: 尝试所有 /dev/cu.usb* 设备
        candidates = [p.device for p in ports if "usb" in p.device.lower()]

    # 策略3: AT 响应验证
    for device in candidates:
        try:
            with serial.Serial(device, DEFAULT_BAUD, timeout=1.0) as ser:
                ser.write(b"AT\r\n")
                time.sleep(0.3)
                response = ser.read(ser.in_waiting or 256)
                if b"OK" in response:
                    return device
        except (serial.SerialException, OSError):
            continue

    return None


# ============================================================
# AT 指令引擎
# ============================================================

class ATModem:
    """AT 指令串口通信封装"""

    def __init__(self, port: str, baud: int = DEFAULT_BAUD, timeout: float = DEFAULT_TIMEOUT):
        self.port = port
        self.baud = baud
        self.timeout = timeout
        self.ser: Optional[serial.Serial] = None

    def connect(self) -> bool:
        """打开串口连接"""
        try:
            self.ser = serial.Serial(
                port=self.port,
                baudrate=self.baud,
                bytesize=serial.EIGHTBITS,
                parity=serial.PARITY_NONE,
                stopbits=serial.STOPBITS_ONE,
                timeout=self.timeout,
                rtscts=False,
                dsrdtr=False,
            )
            return True
        except (serial.SerialException, OSError) as e:
            print(f"  [错误] 无法打开串口 {self.port}: {e}")
            return False

    def disconnect(self):
        """关闭串口连接"""
        if self.ser and self.ser.is_open:
            self.ser.close()

    def send_at(self, cmd: str, wait_ms: int = 500) -> Tuple[bool, str]:
        """
        发送 AT 指令并读取响应。
        返回: (success, response_raw)
        """
        if not self.ser or not self.ser.is_open:
            return False, "串口未打开"

        try:
            # 清空缓冲区
            self.ser.reset_input_buffer()
            # 发送指令
            full_cmd = f"{cmd}\r\n"
            self.ser.write(full_cmd.encode("ascii"))
            # 等待响应
            time.sleep(wait_ms / 1000.0)
            # 读取所有可用数据
            raw = self.ser.read(self.ser.in_waiting or 1024)
            response = raw.decode("ascii", errors="replace").strip()

            # 判断是否成功 (通常包含 OK 或 数据行)
            success = "OK" in response or "ERROR" not in response.upper()
            return success, response
        except (serial.SerialException, OSError) as e:
            return False, str(e)


# ============================================================
# 测试用例
# ============================================================

def run_test(modem: ATModem, name: str, cmd: str, wait_ms: int = 500,
             expected_contains: Optional[str] = None) -> bool:
    """执行单个 AT 测试并打印结果"""
    print(f"  [{name}] {cmd} ... ", end="", flush=True)
    ok, resp = modem.send_at(cmd, wait_ms)
    
    if ok:
        # 提取有效数据行 (去掉 echo 和 OK)
        lines = [l.strip() for l in resp.split("\r\n") if l.strip() and l.strip() != "OK"]
        data_lines = [l for l in lines if l != cmd]  # 排除 echo
        if data_lines:
            print("PASS")
            for line in data_lines:
                print(f"    → {line}")
        else:
            print("PASS (OK)")
    else:
        print("FAIL")
        if resp:
            print(f"    响应: {resp[:200]}")

    if expected_contains and expected_contains not in resp:
        print(f"    [警告] 未检测到预期内容: {expected_contains}")
        return False

    return ok


def test_basic(modem: ATModem):
    """基础测试: AT → AT+CSQ → AT+CGPSINFO"""
    print("\n" + "=" * 60)
    print(" 基础 AT 指令测试")
    print("=" * 60)

    results = []
    # 1. AT 基本响应
    results.append(run_test(modem, "AT 基本响应", "AT", wait_ms=300))

    # 2. 信号强度
    results.append(run_test(modem, "信号强度", "AT+CSQ", wait_ms=500))

    # 3. GNSS 定位信息 (Air780EG AT 指令)
    results.append(run_test(modem, "GNSS 定位", "AT+CGPSINFO", wait_ms=800))

    return all(results)


def test_extended(modem: ATModem):
    """扩展测试: SIM卡/网络/固件/网络注册"""
    print("\n" + "=" * 60)
    print(" 扩展测试")
    print("=" * 60)

    results = []
    # SIM 卡
    results.append(run_test(modem, "SIM 卡状态", "AT+CPIN?", wait_ms=500,
                            expected_contains="READY"))

    # 网络注册
    results.append(run_test(modem, "网络注册", "AT+CEREG?", wait_ms=500))

    # 运营商
    results.append(run_test(modem, "运营商", "AT+COPS?", wait_ms=2000))

    # 固件版本
    results.append(run_test(modem, "固件版本", "AT+CGMR", wait_ms=500))

    # IMEI
    results.append(run_test(modem, "IMEI", "AT+CGSN", wait_ms=500))

    return all(results)


def test_full(modem: ATModem):
    """完整测试套件"""
    print("\n" + "#" * 60)
    print(f" Air780EG AT 指令完整测试")
    print(f" 串口: {modem.port}  波特率: {modem.baud}")
    print("#" * 60)

    all_pass = True
    all_pass &= test_basic(modem)
    all_pass &= test_extended(modem)

    print("\n" + "-" * 60)
    if all_pass:
        print(" 结果: 全部测试通过 ✓")
    else:
        print(" 结果: 部分测试失败 ✗ (查看上方 FAIL 行)")
    print("-" * 60)

    return all_pass


# ============================================================
# 主入口
# ============================================================

def main():
    parser = argparse.ArgumentParser(
        description="KeepSafe Air780EG (EC618) AT 指令验证脚本",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python3 test_at.py                 # 自动检测并运行基础测试
  python3 test_at.py --full          # 完整测试套件
  python3 test_at.py --port /dev/cu.usbserial-110  # 指定串口
  python3 test_at.py --list          # 仅列出可用串口
        """
    )
    parser.add_argument("--port", "-p", help="指定串口设备路径")
    parser.add_argument("--baud", "-b", type=int, default=DEFAULT_BAUD,
                        help=f"波特率 (默认: {DEFAULT_BAUD})")
    parser.add_argument("--full", "-f", action="store_true",
                        help="运行完整测试套件")
    parser.add_argument("--list", "-l", action="store_true",
                        help="仅列出可用串口")
    args = parser.parse_args()

    # --list 模式
    if args.list:
        ports = list_serial_ports()
        if not ports:
            print("未检测到任何串口设备")
            return
        print(f"检测到 {len(ports)} 个串口设备:\n")
        for p in ports:
            vid_pid = f"{p.vid:04X}:{p.pid:04X}" if p.vid and p.pid else "N/A"
            print(f"  {p.device}")
            print(f"    描述: {p.description or 'N/A'}")
            print(f"    厂商: {p.manufacturer or 'N/A'}")
            print(f"    VID:PID: {vid_pid}")
            print()
        return

    # 确定串口
    port = args.port
    if not port:
        print("正在自动检测 Air780EG 模组...")
        port = detect_air780eg()
        if not port:
            print("\n[错误] 未检测到 Air780EG 模组。")
            print("请手动指定端口: python3 test_at.py --port /dev/cu.xxx")
            print("或运行: python3 test_at.py --list  查看所有可用串口")
            sys.exit(1)
        print(f"  检测到候选设备: {port}")

    # 连接并测试
    modem = ATModem(port, args.baud)
    if not modem.connect():
        sys.exit(1)

    try:
        if args.full:
            success = test_full(modem)
        else:
            success = test_basic(modem)

        sys.exit(0 if success else 1)
    finally:
        modem.disconnect()


if __name__ == "__main__":
    main()
