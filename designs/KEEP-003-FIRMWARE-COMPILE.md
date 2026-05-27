# Dev Plan: KEEP-003 — 固件编译与验证

## 1. 需求概述
编译 `code/firmware/` 下 18 个 C 文件的 ESP32-S3 固件，验证编译完整性。

## 2. 技术方案
- 工具链：`~/.espressif/xtensa-esp-elf/bin/xtensa-esp-elf-gcc`（已装，14.2.0）
- 烧录工具：`esptool.py`（已装，5.2.0）
- 编译方式：通过 CMake + ESP-IDF build system

## 3. 任务分解
| # | 任务 | 角色 | 说明 |
|---|------|------|------|
| 1 | 编译固件 | Emb-Dev | 编译 code/firmware/ 全部源码，产生 .bin/.elf |
| 2 | 编译验证 | QA | 验证编译产物完整性 |

## 4. 验收标准
1. ✅ 编译无报错退出
2. ✅ 生成 `.bin` 烧录文件
3. ✅ 生成 `.elf` 调试文件
4. ✅ ELF 中包含预期的分区表
5. ✅ `esptool.py` 能识别编译产物
