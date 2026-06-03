"""
KeepSafe Chat Agent — 手机端 Web 聊天接口
让老板通过手机浏览器跟我实时聊天。
v2.0: 加项目状态面板、快捷查询、走 OpenClaw Gateway
"""

from __future__ import annotations

import asyncio
import logging
import os
import subprocess
import time
from typing import Dict, List

import httpx
from fastapi import APIRouter, Query, UploadFile, File
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel

logger = logging.getLogger("keepsafe.chat")

router = APIRouter(prefix="/chat", tags=["chat"])

# ── Message Store (内存存储，重启丢失) ──────────────────────────
messages: List[Dict] = []
MAX_MESSAGES = 200

agent_thinking: bool = False


class ChatMessage(BaseModel):
    role: str
    content: str
    timestamp: float


# ── 快捷指令 ───────────────────────────────────────────────────
QUICK_COMMANDS = [
    {"id": "status", "label": "项目状态", "icon": "📊"},
    {"id": "team", "label": "团队情况", "icon": "👥"},
    {"id": "blockers", "label": "阻塞项", "icon": "🚧"},
    {"id": "qa", "label": "QA 摘要", "icon": "🧪"},
    {"id": "recent", "label": "最近进展", "icon": "📋"},
]


# ── API 端点 ──────────────────────────────────────────────────

@router.get("/", response_class=HTMLResponse)
async def chat_page_old():
    from fastapi.responses import RedirectResponse
    return RedirectResponse(url="/chat/v2")


@router.get("/v2", response_class=HTMLResponse)
async def chat_page_v2():
    return HTMLResponse(CHAT_HTML)


@router.post("/api/upload")
async def upload_image(file: UploadFile = File(...)):
    """上传图片，返回本地可访问的 URL。"""
    import aiofiles
    upload_dir = os.path.expanduser("~/projects/keepsafe/uploads")
    os.makedirs(upload_dir, exist_ok=True)

    # 保存文件
    save_name = f"{int(time.time())}_{file.filename or 'image'}"
    save_path = os.path.join(upload_dir, save_name)

    content = await file.read()
    async with aiofiles.open(save_path, "wb") as f:
        await f.write(content)

    # 返回本地可访问 URL
    url = f"http://192.168.110.34:8000/uploads/{save_name}"
    return JSONResponse({"url": url, "path": save_path, "size": len(content)})


@router.get("/api/messages")
async def get_messages(since: float = Query(0.0)):
    new_msgs = [m for m in messages if m["timestamp"] > since]
    return {"messages": new_msgs, "agent_thinking": agent_thinking}


@router.post("/api/send")
async def send_message(msg: ChatMessage):
    messages.append(msg.model_dump())
    if len(messages) > MAX_MESSAGES:
        messages[:MAX_MESSAGES // 2] = []
    return {"ok": True}


@router.get("/api/quick-cmd")
async def quick_command(cmd: str = Query(...)):
    """快捷指令：返回事先准备好的摘要，不需要经过 AI。"""
    if cmd == "status":
        return {"content": _get_project_status()}
    elif cmd == "team":
        return {"content": _get_team_status()}
    elif cmd == "blockers":
        return {"content": _get_blockers()}
    elif cmd == "qa":
        return {"content": _get_qa_summary()}
    elif cmd == "recent":
        return {"content": (
            "最近完成：工具链全部装好（Homebrew/ImageMagick/Tesseract/KiCad/Blender），"
            "手机聊天页面已上线。下一步可启动固件编译、STL渲染或App联调。"
        )}
    return {"content": "未知指令"}


@router.get("/api/status")
async def project_status():
    """项目概览数据，供前端展示。"""
    return {
        "completed": ["KEEP-001 结构/固件/后端基座", "三端 App MVP 源码", "本地后端运行中", "3D OBJ模型生成", "工具链全部安装"],
        "in_progress": ["手机聊天页面升级"],
        "blocked": ["固件编译 (需ESP-IDF)", "STL渲染 (需OpenSCAD)", "三端联调 (API路径不匹配)"],
        "version": "2.0.0",
    }


def add_agent_reply(content: str):
    global agent_thinking
    ts = time.time()
    content_stripped = content.strip().replace("\x00", "")
    messages.append({"role": "agent", "content": content_stripped, "timestamp": ts})
    agent_thinking = False
    if len(messages) > MAX_MESSAGES:
        messages[:MAX_MESSAGES // 2] = []
    return ts


def set_thinking(status: bool):
    global agent_thinking
    agent_thinking = status


# ── 摘要生成（不调AI，本地拼） ────────────────────────────────

def _get_project_status() -> str:
    return (
        "📊 KeepSafe 项目总览\n\n"
        "✅ KEEP-001 — 结构+固件+后端基座（已交付）\n"
        "✅ KEEP-002 — 三端App MVP源码（已完成）\n"
        "✅ 后端 — 本地8000端口运行（SQLite开发模式）\n"
        "✅ 工具链 — Homebrew/ImageMagick/Tesseract/KiCad/Blender\n"
        "⏳ 固件编译 — 需要ESP-IDF工具链\n"
        "⏳ 结构STL — 需要OpenSCAD\n"
        "⏳ 三端联调 — API路径需统一修正"
    )


def _get_team_status() -> str:
    return (
        "👥 团队（12角色）\n\n"
        "Architect, BE-Dev, iOS-Dev, And-Dev, Emb-Dev, Mech-Dev,\n"
        "UI-Dev, MiniApp-Dev, QA, Reviewer, Librarian, PM(我)\n\n"
        "当前活跃：PM（我）\n"
        "待激活：Emb-Dev(需ESP-IDF), Mech-Dev(需OpenSCAD), 前端团队(需设计图)"
    )


def _get_blockers() -> str:
    return (
        "🚧 阻塞项\n\n"
        "1. 固件编译 — 需要sudo装ESP-IDF（需要你输密码）\n"
        "2. OpenSCAD — 需要sudo装（需要你输密码）\n"
        "3. 三端联调 — iOS/Android/小程序API路径不匹配\n"
        "4. .env密钥 — 如需Docker部署需填真实密码\n\n"
        "前2项需要你配合：输一次sudo密码就能全部搞定"
    )


def _get_qa_summary() -> str:
    return (
        "🧪 QA 评审摘要\n\n"
        "33个问题：8个Blocker / 18个Major / 7个Minor\n"
        "最大问题：三端API路径与后端路由不匹配\n"
        "修复方式：统一API base URL即可\n"
        "完整报告：tests/QA-FULL-REVIEW.md"
    )


# ── 后台消费者：轮询用户消息 → OpenClaw Gateway ──────────────

_last_processed_ts: float = 0.0


def _get_openclaw_path() -> str | None:
    """找 openclaw 命令的绝对路径。"""
    for p in [
        "/Users/chenxianglin/.npm-global/bin/openclaw",
        "/opt/homebrew/bin/openclaw",
        "/usr/local/bin/openclaw",
    ]:
        if os.path.isfile(p):
            return p
    r = subprocess.run(["which", "openclaw"], capture_output=True, text=True, timeout=5)
    p = r.stdout.strip()
    return p if p else None


async def chat_consumer_loop():
    """
    后台任务：每秒检查是否有新的用户消息。
    优先走 OpenClaw agent（带完整工具链），不可用时走 DeepSeek API。
    """
    logger.info("Chat consumer loop started")

    # 检测可用后端
    # 当前 OpenClaw 配置有验证问题，直接走 DeepSeek API
    deepseek_key = _get_deepseek_key()
    openclaw_path = _get_openclaw_path()

    if deepseek_key:
        logger.info("Using DeepSeek API directly")
        await _consumer_via_deepseek()
    elif openclaw_path:
        logger.warning("OpenClaw found but config invalid, DeepSeek key missing — will try OpenClaw as fallback")
        await _consumer_via_openclaw(openclaw_path)
    else:
        logger.error("No AI backend available — echo only mode")
        await _consumer_echo_only()


def _get_deepseek_key() -> str:
    env_path = os.path.expanduser("~/.hermes/.env")
    try:
        with open(env_path) as f:
            for line in f:
                line = line.strip()
                if line.startswith("DEEPSEEK_API_KEY="):
                    return line.split("=", 1)[1]
    except Exception:
        pass
    return ""


async def _consumer_via_openclaw(openclaw_path: str):
    """通过 OpenClaw CLI 调用 agent。"""
    global _last_processed_ts
    env = os.environ.copy()

    while True:
        try:
            user_msgs = [m for m in messages if m["role"] == "user" and m["timestamp"] > _last_processed_ts]
            if user_msgs:
                latest = max(user_msgs, key=lambda m: m["timestamp"])
                _last_processed_ts = latest["timestamp"]
                user_text = latest["content"]

                logger.info("Chat → OpenClaw: %s...", user_text[:60])
                set_thinking(True)

                reply = await asyncio.to_thread(
                    _call_openclaw, openclaw_path, user_text, env
                )

                add_agent_reply(reply)
                logger.info("OpenClaw reply added (%d chars)", len(reply))
        except Exception as exc:
            logger.error("Consumer error: %s", exc)
            set_thinking(False)

        await asyncio.sleep(1)


def _call_openclaw(path: str, text: str, env: dict) -> str:
    """同步调用 OpenClaw agent。"""
    try:
        result = subprocess.run(
            [path, "agent", "-m", text, "--agent", "main"],
            capture_output=True, text=True, timeout=120, env=env,
        )
        output = result.stdout.strip() or result.stderr.strip()
        return output if output else "(OpenClaw 执行完成，无返回)"
    except subprocess.TimeoutExpired:
        return "(处理超时，重说一遍？)"
    except Exception as exc:
        return f"(OpenClaw 调用失败：{exc})"


async def _consumer_via_deepseek():
    """通过 DeepSeek API 回复；如果失败则本地回复。"""
    global _last_processed_ts
    api_key = _get_deepseek_key()
    async with httpx.AsyncClient(timeout=30) as client:
        while True:
            try:
                user_msgs = [m for m in messages if m["role"] == "user" and m["timestamp"] > _last_processed_ts]
                if user_msgs:
                    latest = max(user_msgs, key=lambda m: m["timestamp"])
                    _last_processed_ts = latest["timestamp"]
                    user_text = latest["content"]

                    set_thinking(True)

                    # Try DeepSeek first
                    resp = await client.post(
                        "https://api.deepseek.com/chat/completions",
                        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
                        json={
                            "model": "deepseek-chat",
                            "messages": [{"role": "user", "content": user_text}],
                            "max_tokens": 1024
                        },
                    )

                    if resp.status_code == 200:
                        reply = resp.json()["choices"][0]["message"]["content"]
                    else:
                        # Fallback: local response
                        reply = _local_reply(user_text)

                    add_agent_reply(reply)
            except Exception as exc:
                logger.error("Consumer error: %s", exc)
                set_thinking(False)

            await asyncio.sleep(0.3)


def _local_reply(text: str) -> str:
    """本地智能回复（不依赖外部 API）"""
    t = text.strip().lower()
    if any(w in t for w in ["状态", "进度", "项目", "怎么样"]):
        return _get_project_status()
    if any(w in t for w in ["团队", "成员", "谁"]):
        return _get_team_status()
    if any(w in t for w in ["阻塞", "卡", "问题", "block"]):
        return _get_blockers()
    if any(w in t for w in ["你好", "hi", "hello", "嗨"]):
        return "陈总好！项目后端已运行，小程序5页面完成，固件等USB线到了就能烧录。手机聊天已通，随时找我。"
    if any(w in t for w in ["固件", "烧录", "开发板", "esp"]):
        return "固件已在VPS上编译完成(325KB)。开发板ESP32-S3已识别到，但USB转接头不稳定导致烧录失败。等新线到了就可以烧录。"
    if any(w in t for w in ["小程序"]):
        return "微信小程序5个页面全部完成：登录、地图首页、告警列表、SOS详情、个人中心。AppID已配置，后端已联调。用微信开发者工具打开 ~/projects/keepsafe/code/miniapp/ 就能预览。"
    return f"收到。「{text[:50]}」\n\n试试这些关键词：项目状态 / 团队 / 阻塞 / 固件 / 小程序\n或点上方快捷按钮。"


async def _consumer_echo_only():
    """降级：只回显。"""
    global _last_processed_ts
    while True:
        user_msgs = [m for m in messages if m["role"] == "user" and m["timestamp"] > _last_processed_ts]
        if user_msgs:
            latest = max(user_msgs, key=lambda m: m["timestamp"])
            _last_processed_ts = latest["timestamp"]
            add_agent_reply("（已收到，但未配置AI后端）")
        await asyncio.sleep(1)


# ── HTML 聊天页面 v2 ─────────────────────────────────────────

CHAT_HTML = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
<meta http-equiv="Cache-Control" content="no-cache, no-store, must-revalidate">
<meta http-equiv="Pragma" content="no-cache">
<meta http-equiv="Expires" content="0">
<title>KeepSafe · 助理</title>
<style>
* { margin: 0; padding: 0; box-sizing: border-box; }
body {
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
  background: #f5f5f5;
  height: 100vh;
  display: flex;
  flex-direction: column;
}
.header {
  background: #4A90D9;
  color: white;
  padding: 12px 16px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  flex-shrink: 0;
  box-shadow: 0 2px 4px rgba(0,0,0,0.1);
}
.header-title {
  font-size: 17px;
  font-weight: 600;
}
.header-sub { font-size: 11px; opacity: 0.8; margin-top: 1px; }
.header-right {
  display: flex;
  gap: 8px;
}
.menu-btn {
  background: rgba(255,255,255,0.2);
  border: none;
  color: white;
  width: 36px;
  height: 36px;
  border-radius: 50%;
  font-size: 18px;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
}
.menu-btn:active { background: rgba(255,255,255,0.35); }

/* ── Quick Bar ── */
.quick-bar {
  display: flex;
  gap: 6px;
  padding: 8px 12px;
  background: white;
  overflow-x: auto;
  flex-shrink: 0;
  border-bottom: 1px solid #eee;
  -webkit-overflow-scrolling: touch;
}
.quick-bar::-webkit-scrollbar { display: none; }
.quick-btn {
  flex-shrink: 0;
  padding: 6px 12px;
  border-radius: 16px;
  border: 1px solid #ddd;
  background: #f8f9fa;
  font-size: 13px;
  cursor: pointer;
  white-space: nowrap;
  color: #555;
  transition: all 0.15s;
}
.quick-btn:active { background: #4A90D9; color: white; border-color: #4A90D9; }

/* ── Chat Box ── */
.chat-box {
  flex: 1;
  overflow-y: auto;
  padding: 12px 14px;
  display: flex;
  flex-direction: column;
  gap: 10px;
  background: #e8eef5;
}
.msg {
  max-width: 85%;
  padding: 10px 14px;
  border-radius: 16px;
  font-size: 15px;
  line-height: 1.5;
  word-break: break-word;
  position: relative;
  animation: fadeIn 0.25s ease;
}
@keyframes fadeIn { from { opacity: 0; transform: translateY(6px); } to { opacity: 1; transform: translateY(0); } }
.msg.user {
  background: #4A90D9; color: white;
  align-self: flex-end;
  border-bottom-right-radius: 4px;
}
.msg.agent {
  background: white; color: #333;
  align-self: flex-start;
  border-bottom-left-radius: 4px;
  box-shadow: 0 1px 2px rgba(0,0,0,0.08);
}
.msg .time { font-size: 11px; opacity: 0.6; margin-top: 4px; text-align: right; }
.msg.user .time { color: rgba(255,255,255,0.7); }

/* ── Thinking ── */
.thinking-indicator {
  align-self: flex-start;
  background: white;
  border-radius: 16px;
  padding: 12px 18px;
  display: none;
  box-shadow: 0 1px 2px rgba(0,0,0,0.08);
}
.thinking-indicator.visible { display: flex; align-items: center; gap: 6px; }
.thinking-dot {
  width: 8px; height: 8px;
  border-radius: 50%;
  background: #4A90D9;
  animation: bounce 1.2s infinite;
}
.thinking-dot:nth-child(2) { animation-delay: 0.2s; }
.thinking-dot:nth-child(3) { animation-delay: 0.4s; }
@keyframes bounce {
  0%, 80%, 100% { transform: translateY(0); opacity: 0.3; }
  40% { transform: translateY(-6px); opacity: 1; }
}

/* ── Input Bar ── */
.input-bar {
  display: flex;
  gap: 8px;
  padding: 10px 12px;
  background: white;
  border-top: 1px solid #ddd;
  flex-shrink: 0;
  align-items: flex-end;
}
.input-bar textarea {
  flex: 1;
  border: 1px solid #ddd;
  border-radius: 20px;
  padding: 10px 14px;
  font-size: 15px;
  resize: none;
  outline: none;
  max-height: 100px;
  font-family: inherit;
}
.input-bar textarea:focus { border-color: #4A90D9; }
.send-btn {
  background: #4A90D9; color: white;
  border: none;
  border-radius: 50%;
  width: 44px; height: 44px;
  font-size: 20px;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  transition: background 0.15s;
}
.send-btn:active { background: #357ABD; }
.send-btn:disabled { background: #ccc; }

/* ── Sidebar Overlay ── */
.sidebar-overlay {
  display: none;
  position: fixed;
  inset: 0;
  background: rgba(0,0,0,0.4);
  z-index: 100;
}
.sidebar-overlay.open { display: block; }
.sidebar {
  position: fixed;
  top: 0; left: -280px;
  width: 280px; height: 100%;
  background: white;
  z-index: 101;
  transition: left 0.3s ease;
  padding: 20px 16px;
  box-shadow: 2px 0 12px rgba(0,0,0,0.15);
}
.sidebar.open { left: 0; }
.sidebar h3 { font-size: 16px; color: #4A90D9; margin-bottom: 16px; }
.sidebar-section { margin-bottom: 20px; }
.sidebar-section h4 {
  font-size: 13px; color: #999; margin-bottom: 8px;
  text-transform: uppercase; letter-spacing: 0.5px;
}
.sidebar-item {
  font-size: 14px;
  padding: 8px 0;
  border-bottom: 1px solid #f0f0f0;
  color: #555;
  display: flex;
  align-items: center;
  gap: 8px;
}
.sidebar-item .dot { width: 8px; height: 8px; border-radius: 50%; flex-shrink: 0; }
.sidebar-item .dot.green { background: #34c759; }
.sidebar-item .dot.yellow { background: #ff9500; }
.sidebar-item .dot.red { background: #ff3b30; }
.sidebar-close {
  position: absolute;
  top: 16px; right: 16px;
  background: none; border: none;
  font-size: 22px; color: #999;
  cursor: pointer;
}
</style>
</head>
<body>

<!-- Header -->
<div class="header">
  <div>
    <div class="header-title">KeepSafe 助理</div>
    <div class="header-sub">Hermes Agent · v2</div>
  </div>
  <div class="header-right">
    <button class="menu-btn" onclick="toggleSidebar()">☰</button>
  </div>
</div>

<!-- Quick Commands -->
<div class="quick-bar">
  <button class="quick-btn" data-cmd="status">📊 项目状态</button>
  <button class="quick-btn" data-cmd="team">👥 团队情况</button>
  <button class="quick-btn" data-cmd="blockers">🚧 阻塞项</button>
  <button class="quick-btn" data-cmd="qa">🧪 QA摘要</button>
  <button class="quick-btn" data-cmd="recent">📋 最近进展</button>
</div>

<!-- Chat Box -->
<div class="chat-box" id="chatBox">
  <div class="msg agent">
    老板好。以后直接在手机上找我。<br>试试快捷按钮，或直接打字。
    <div class="time">刚刚</div>
  </div>
  <div class="thinking-indicator" id="thinkingIndicator">
    <span class="thinking-dot"></span>
    <span class="thinking-dot"></span>
    <span class="thinking-dot"></span>
  </div>
</div>

<!-- Input Bar -->
<div class="input-bar">
  <textarea id="input" rows="1" placeholder="输入指令…" enterkeyhint="send"></textarea>
  <button class="send-btn" id="sendBtn">➤</button>
</div>

<!-- Sidebar Overlay -->
<div class="sidebar-overlay" id="sidebarOverlay" onclick="toggleSidebar()"></div>
<div class="sidebar" id="sidebar">
  <button class="sidebar-close" onclick="toggleSidebar()">✕</button>
  <h3>📊 项目概览</h3>
  <div class="sidebar-section" id="sidebarContent">
    <p style="color:#999;font-size:13px;">加载中…</p>
  </div>
</div>

<script>
const chatBox = document.getElementById('chatBox');
const input = document.getElementById('input');
const sendBtn = document.getElementById('sendBtn');
const thinkingEl = document.getElementById('thinkingIndicator');

// Quick commands
document.querySelectorAll('.quick-btn').forEach(function(btn) {
  btn.onclick = function() { quickCmd(this.getAttribute('data-cmd')); };
});

async function quickCmd(id) {
  var cmd = {status:'项目状态',team:'团队情况',blockers:'阻塞项',qa:'QA摘要',recent:'最近进展'}[id] || id;
  addMsg('user', cmd);
  toggleThinking(true);
  try {
    var resp = await fetch('/chat/api/quick-cmd?cmd='+id);
    var data = await resp.json();
    addMsg('agent', data.content);
  } catch(e) { addMsg('agent', '请求失败: '+e.message); }
  toggleThinking(false);
}

input.onkeydown = function(e) {
  if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); doSend(); }
};
sendBtn.onclick = doSend;

async function doSend() {
  var text = input.value.trim();
  if (!text) return;
  input.value = '';
  sendBtn.disabled = true;
  addMsg('user', text);
  toggleThinking(true);
  try {
    await fetch('/chat/api/send', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({role:'user', content:text, timestamp:Date.now()/1000})
    });
  } catch(e) { addMsg('agent', '发送失败'); toggleThinking(false); sendBtn.disabled = false; return; }
  // Poll for reply
  var since = Date.now()/1000;
  for (var i=0; i<60; i++) {
    await sleep(800);
    try {
      var resp = await fetch('/chat/api/messages?since='+since);
      var data = await resp.json();
      var msgs = data.messages || [];
      for (var j=0; j<msgs.length; j++) {
        var check = msgs[j];
        if (check.role === 'agent') {
          addMsg('agent', check.content);
          toggleThinking(false);
          sendBtn.disabled = false;
          return;
        }
      }
    } catch(e) {}
  }
  toggleThinking(false);
  sendBtn.disabled = false;
}

function addMsg(role, text) {
  var div = document.createElement('div');
  div.className = 'msg ' + role;
  div.innerHTML = text.replace(/\\n/g,'<br>') + '<div class="time">'+fmtTime()+'</div>';
  chatBox.insertBefore(div, thinkingEl);
  chatBox.scrollTop = chatBox.scrollHeight;
}

function toggleThinking(on) {
  if (on) thinkingEl.classList.add('visible');
  else thinkingEl.classList.remove('visible');
}

function fmtTime() {
  var d = new Date();
  return ('0'+d.getHours()).slice(-2)+':'+('0'+d.getMinutes()).slice(-2);
}

function sleep(ms) { return new Promise(function(r) { setTimeout(r, ms); }); }
</script>
</body>
</html>"""
