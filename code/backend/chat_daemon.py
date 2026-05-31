#!/usr/bin/env python3
"""
KeepSafe Chat Agent — 聊天轮询守护进程
定时检查后端是否有新用户消息，调用 Hermes Agent 回复。
"""

import json
import logging
import os
import subprocess
import time
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.error import URLError

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [CHAT] %(levelname)s: %(message)s",
)
logger = logging.getLogger("chat-agent")

BACKEND_URL = os.environ.get("BACKEND_URL", "http://127.0.0.1:8000")
POLL_INTERVAL = 2  # 秒
MAX_WAIT_TIME = 120  # 最长等待回复时间（秒）


class ChatAgent:
    def __init__(self):
        self.last_ts = time.time()
        self.pending_messages = []

    def _fetch(self, path: str) -> dict:
        """GET 请求后端。"""
        req = Request(f"{BACKEND_URL}{path}")
        try:
            with urlopen(req, timeout=10) as resp:
                return json.loads(resp.read().decode())
        except URLError as e:
            logger.warning("Backend request failed: %s", e)
            return {"messages": [], "agent_thinking": False}

    def _post(self, path: str, data: dict) -> bool:
        """POST 请求后端。"""
        body = json.dumps(data).encode()
        req = Request(f"{BACKEND_URL}{path}", data=body, method="POST")
        req.add_header("Content-Type", "application/json")
        try:
            with urlopen(req, timeout=10) as resp:
                return resp.status == 200
        except URLError as e:
            logger.warning("Backend POST failed: %s", e)
            return False

    def call_hermes(self, message: str) -> str:
        """调用 Hermes Agent (OpenClaw) 获取回复。"""
        try:
            result = subprocess.run(
                ["openclaw", "agent", "-m", message, "--agent", "main"],
                capture_output=True,
                text=True,
                timeout=120,
                cwd=str(Path.home() / "projects" / "keepsafe"),
            )
            output = result.stdout.strip()
            if result.returncode != 0:
                logger.error("OpenClaw failed: %s", result.stderr[:200])
                return f"（处理出错：{result.stderr[:100]}）"
            if not output:
                return "（没有获取到回复）"
            return output
        except subprocess.TimeoutExpired:
            return "（回复超时，请重试）"
        except FileNotFoundError:
            # 如果没有 openclaw，尝试用 Hermes 直接处理
            return self._fallback_reply(message)
        except Exception as e:
            logger.error("Agent call failed: %s", e)
            return f"（调用失败：{str(e)[:100]}）"

    def _fallback_reply(self, message: str) -> str:
        """兜底回复。"""
        return f"收到：{message}\n（Agent 正在处理中，请稍候重试）"

    def run(self):
        """主循环。"""
        logger.info("Chat Agent started. Polling %s/chat/api/poll", BACKEND_URL)

        while True:
            try:
                self._tick()
            except KeyboardInterrupt:
                logger.info("Shutting down...")
                break
            except Exception as e:
                logger.error("Tick error: %s", e)
                time.sleep(POLL_INTERVAL)

    def _tick(self):
        result = self._fetch(f"/chat/api/messages?since={self.last_ts}")
        msgs = result.get("messages", [])

        if not msgs:
            time.sleep(POLL_INTERVAL)
            return

        # 找最新的用户消息
        latest_user_msg = None
        for msg in msgs:
            if msg["role"] == "user":
                ts = msg["timestamp"]
                if ts > (latest_user_msg["timestamp"] if latest_user_msg else 0):
                    latest_user_msg = msg

        if not latest_user_msg:
            self.last_ts = max(m["timestamp"] for m in msgs)
            time.sleep(POLL_INTERVAL)
            return

        self.last_ts = latest_user_msg["timestamp"]
        content = latest_user_msg["content"]

        logger.info("New message: %s", content[:60])

        # 设置思考中
        self._post("/chat/api/messages", {
            "role": "__thinking",
            "content": "",
            "timestamp": time.time()
        })

        # 调用 Hermes Agent
        reply = self.call_hermes(content)

        # 发回复
        self._post("/chat/api/send", {
            "role": "agent",
            "content": reply,
            "timestamp": time.time()
        })

        logger.info("Reply sent: %s", reply[:60])

        # 拉一下最新时间戳
        result = self._fetch(f"/chat/api/messages?since={self.last_ts}")
        for msg in result.get("messages", []):
            if msg["timestamp"] > self.last_ts:
                self.last_ts = msg["timestamp"]

        time.sleep(POLL_INTERVAL)


if __name__ == "__main__":
    agent = ChatAgent()
    agent.run()
