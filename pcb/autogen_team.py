"""
KeepSafe 防丢器 — AutoGen 开发团队
=====================================
团队成员自动协作，完成硬件设计、固件开发、后端对接等任务。

配置参考: https://microsoft.github.io/autogen/stable/
"""

import os
from pathlib import Path

# Load API key from Hermes .env
env_file = Path.home() / ".hermes" / ".env"
if env_file.exists():
    for line in env_file.read_text().strip().split("\n"):
        if "=" in line and not line.startswith("#"):
            key, val = line.split("=", 1)
            key, val = key.strip(), val.strip().strip('"').strip("'")
            os.environ.setdefault(key, val)
import autogen
from autogen import AssistantAgent, UserProxyAgent, GroupChat, GroupChatManager

# ── LLM 配置 ──────────────────────────────
config_list = [
    {
        "model": "deepseek-chat",
        "base_url": "https://api.deepseek.com/v1",
        "api_key": os.environ.get("DEEPSEEK_API_KEY", ""),
    }
]

llm_config = {
    "config_list": config_list,
    "temperature": 0.3,
    "timeout": 120,
}

# ── 团队成员 ──────────────────────────────

# 硬件架构师 — 负责 PCB 设计、元器件选型
hardware_architect = AssistantAgent(
    name="HardwareArchitect",
    system_message="""你是 KeepSafe 防丢器的硬件架构师。职责:
1. 根据 PCB-DESIGN-V3.md 设计电路原理图和 PCB 布局
2. 选型元器件，确保 BOM 成本控制在 ¥50 以内
3. 输出 KiCad 或 EasyEDA 格式的设计文件
4. 与嘉立创对接打样和 SMT 贴片

当前规格: Air780EG 单芯片方案, 32×22mm 双层板, 黑色阻焊。
项目文档: ~/projects/keepsafe/docs/PCB-DESIGN-V3.md""",
    llm_config=llm_config,
)

# 固件工程师 — 负责 LuatOS/AT 固件开发
firmware_engineer = AssistantAgent(
    name="FirmwareEngineer",
    system_message="""你是 KeepSafe 防丢器的固件工程师。职责:
1. 开发 Air780EG LuatOS 固件 (Lua)
2. 实现 MQTT 连接、GPS 定位、低功耗管理
3. 编写 AT 指令测试脚本
4. 确保固件与后端 MQTT 协议对齐

固件代码: ~/projects/keepsafe/code/firmware-ec618/
MQTT 服务器: 43.163.5.90:1883""",
    llm_config=llm_config,
)

# 后端工程师 — 负责 FastAPI 后端
backend_engineer = AssistantAgent(
    name="BackendEngineer",
    system_message="""你是 KeepSafe 防丢器的后端工程师。职责:
1. 维护 FastAPI 后端服务
2. 确保 MQTT 消息处理、设备管理、告警推送正常
3. 编写测试用例，保持 160+ 测试全绿
4. 部署到 VPS 43.163.5.90

代码: ~/projects/keepsafe/code/backend/""",
    llm_config=llm_config,
)

# 小程序工程师 — 负责微信小程序
miniapp_engineer = AssistantAgent(
    name="MiniAppEngineer",
    system_message="""你是 KeepSafe 防丢器的小程序工程师。职责:
1. 维护微信小程序代码 (6 页面)
2. 确保与后端 API 对齐
3. 处理地图定位、设备绑定、告警展示

代码: ~/projects/keepsafe/code/miniapp/
AppID: 待注册""",
    llm_config=llm_config,
)

# 测试工程师 — 负责全链路测试
qa_engineer = AssistantAgent(
    name="QAEngineer",
    system_message="""你是 KeepSafe 项目的测试工程师。职责:
1. 运行全量测试确认无回归
2. 设计边界测试用例
3. 端到端流程验证

当前测试: 162 tests""",
    llm_config=llm_config,
)

# 用户代理 — 接收任务并分发
user_proxy = UserProxyAgent(
    name="UserProxy",
    human_input_mode="NEVER",
    max_consecutive_auto_reply=10,
    is_termination_msg=lambda x: x.get("content", "").rstrip().endswith("TERMINATE"),
    code_execution_config={"use_docker": False},
)

# ── 团队群聊 ──────────────────────────────

def create_keepsafe_team():
    """创建 KeepSafe 项目团队"""
    groupchat = GroupChat(
        agents=[user_proxy, hardware_architect, firmware_engineer, 
                backend_engineer, miniapp_engineer, qa_engineer],
        messages=[],
        max_round=50,
    )
    manager = GroupChatManager(groupchat=groupchat, llm_config=llm_config)
    return user_proxy, manager

# ── 快速启动 ──────────────────────────────

if __name__ == "__main__":
    print("""
    ╔═══════════════════════════════════╗
    ║   KeepSafe AutoGen 开发团队       ║
    ║   5 名工程师就绪                  ║
    ║                                  ║
    ║   硬件 / 固件 / 后端 / 小程序 / 测试 ║
    ╚═══════════════════════════════════╝
    """)

    user, manager = create_keepsafe_team()
    
    task = """
    请团队协作完成以下任务:
    
    1. HardwareArchitect: 生成 Air780EG 的 KiCad PCB 设计文件，包含:
       - 原理图 (含 SIM卡座/LED/按键/蜂鸣器/电池接口)
       - PCB 布局 (32×22mm 双层板)
       - 导出 Gerber 文件到 ~/projects/keepsafe/pcb/
    
    2. FirmwareEngineer: 确保 firmware-ec618/luatos/ 固件代码最新，
       配置 MQTT 连接到 43.163.5.90:1883
    
    3. BackendEngineer: 运行 162 测试确认全绿
    
    4. QAEngineer: 验证固件与后端的 MQTT 协议一致性
    
    各成员完成后回复 TERMINATE。
    """
    
    user.initiate_chat(manager, message=task)
