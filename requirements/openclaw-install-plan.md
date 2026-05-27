# OpenClaw 安装方案

## 概述

在 macOS 上安装 [OpenClaw](https://github.com/openclaw/openclaw) v2026.5.7 — 开源个人 AI 助理框架，37 万 star 的 TypeScript 项目。

## 环境要求

| 项目 | 要求 | 实际 |
|------|------|------|
| Node.js | >=22.16.0 | v22.16.0 |
| npm | >=10 | 10.9.2 |
| OS | macOS / Linux / Windows(WSL2) | macOS ARM64 |
| npm registry | 官方源 | https://registry.npmjs.org/ |

> **注意**：该环境无法直连 github.com，但可以访问 npmjs.org 和 githubfast.com。所有安装依赖 npm 官方 registry 完成，不从 GitHub 源码构建。

## 安装步骤

### 1. 安装 Node.js v22

系统自带 Node.js v20.18.0，不满足 OpenClaw 要求的 v22.12+。

使用 `n`（Node.js 版本管理器）安装 v22.16.0：

```bash
# 安装 n
npm install -g n

# 安装 Node v22.16.0 到用户目录
N_PREFIX=$HOME/.n n 22.16

# 添加 PATH（已写入 .zshrc）
export N_PREFIX="$HOME/.n"
export PATH="$N_PREFIX/bin:$HOME/.npm-global/bin:/usr/local/bin:$PATH"
```

安装位置：`~/.n/bin/node`

### 2. 修正 npm registry

原 registry 设置为 USTC 镜像（npm.mirrors.ustc.edu.cn），该镜像已不可用。切回官方源：

```bash
npm config set registry https://registry.npmjs.org/
```

### 3. 安装 OpenClaw

```bash
npm install -g openclaw@latest
```

安装位置：`~/.npm-global/lib/node_modules/openclaw/`

### 4. 验证

```bash
openclaw --version
# 输出：OpenClaw 2026.5.7 (eeef486)
```

## 踩坑记录

| 问题 | 原因 | 解决 |
|------|------|------|
| 装了 PyPI 的 openclaw | 同名不同项目，是 CMDOP 编排插件 | 用 npm 安装 |
| npm 装了 0.0.1 假包 | USTC 镜像内容不完整 | 切回官方 registry |
| Node.js 版本不够 | 系统自带 v20，需要 v22 | 用 `n` 装 v22.16.0 |
| 源码构建失败 | rolldown 原生绑定编译崩溃 | 直接用 npm 预构建包 |
| `openclaw` 命令找不到 | PATH 顺序问题，/usr/local/bin 优先于 ~/.n/bin | 修改 .zshrc 第1行 |

## 最终配置

**.zshrc** 第1行已改为：
```bash
export PATH="$HOME/.n/bin:$HOME/.npm-global/bin:/usr/local/bin:$PATH"
```

确保新终端可以直接使用 `openclaw` 命令。

## 后续使用

```bash
openclaw onboard         # 首次引导配置（网关、工作区、频道、技能）
openclaw --help          # 查看全部命令
openclaw agent           # 运行一次 agent
openclaw agents          # 管理 agent 工作区
```

## 磁盘占用

- Node.js v22: ~430M (`~/.n/`)
- OpenClaw: ~150M (`~/.npm-global/lib/node_modules/openclaw/`)

临时文件 `/tmp/openclaw-src/` 和 `/tmp/openclaw-env/` 已清理。
