# KeepSafe 防丢器 — 部署手册

## 后端
- 本地开发: localhost:8000 (dev_mode=True, SQLite)
- VPS: Docker 容器 keepsafe-app :8000
- 测试账号: test@keepsafe.com / test123456

## 固件
- 平台: ESP32-S3 + EC618 4G
- 编译: VPS Docker espressif/idf:v5.4
- 烧录: esptool --chip esp32s3 -p /dev/cu.usbmodem101 write_flash 0x0 bootloader.bin 0x8000 partition-table.bin 0x10000 firmware.bin
- 关键: 必须用 USB-OTG 口 (usbmodem101), 不能用 UART 口

## 小程序
- AppID: wxebce4c590760c9e3
- API: http://43.163.5.90:8000/api/v1
- 5 页面: login, index, alerts, sos-detail, profile

## VPS 容器
```
keepsafe-app      :8000  FastAPI
keepsafe-emqx     :1883  MQTT Broker
keepsafe-postgres :5432  数据库
keepsafe-redis    :6379  缓存
```

## BOM
- 主控: EC618 (¥28)
- PCB: ¥6 + SMT ¥8
- 单板总成本: ¥44
- 文件: code/hardware/pcb/BOM-DETAIL-V2.csv
