# KeepSafe 项目 — Hermes 多模型角色配置方案

> 基于你的分析：VL2 看图、Chat 干活

---

## 一、核心原则

| 角色 | 用途 | 模型 | 能力 |
|------|------|------|------|
| **执行型 Agent** | 写代码、改模型、调工具 | `deepseek-chat` | ✅ function calling |
| **看图型 Agent** | 读图、提取尺寸/结构 | `deepseek-vl2` | ❌ 不能调用工具 |

---

## 二、推荐配置（可粘贴）

在 `~/.hermes/config.yaml` 中修改 `delegation` 段：

```yaml
delegation:
  # ---- 执行型 Agent（默认）: 结构/后端/固件 ----
  model: deepseek-chat
  provider: deepseek
  base_url: https://api.deepseek.com/v1
  api_key: ''
  inherit_mcp_toolsets: true
  max_iterations: 50
  child_timeout_seconds: 600
  max_concurrent_children: 3
  max_spawn_depth: 1
  orchestrator_enabled: true
```

### 看图型 Agent 的调用方式

由于 VL2 不支持 function calling，不能放在 `delegation` 默认配置里。需要用 `execute_code` 工具手动调用 API：

```python
import requests, json, base64

def analyze_design_image(image_path: str) -> str:
    """调用 DeepSeek-VL2 API 分析设计图"""
    with open(image_path, "rb") as f:
        b64 = base64.b64encode(f.read()).decode()
    
    resp = requests.post(
        "https://api.deepseek.com/v1/chat/completions",
        headers={
            "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
            "Content-Type": "application/json"
        },
        json={
            "model": "deepseek-vl2-small",
            "messages": [{
                "role": "user",
                "content": [
                    {"type": "text", "text": "详细描述这张设计图的外形尺寸、按键位置、开孔位置、挂耳结构、材质建议"},
                    {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{b64}"}}
                ]
            }],
            "temperature": 0.1,
            "max_tokens": 2048
        }
    )
    return resp.json()["choices"][0]["message"]["content"]
```

---

## 三、工作流（修改后）

```
用户发设计图（PNG/JPG）
        │
        ▼
我（PM）用 execute_code 调用 VL2 API 读图
        │
        ▼
VL2 返回文字描述：尺寸、结构、按键位置、开孔
        │
        ▼
我（PM）把文字描述整合到任务上下文中
        │
        ▼
派结构工程师（deepseek-chat）→ 写/改 OpenSCAD 模型
```

---

## 四、不需要修改当前配置的原因

当前你的 config.yaml 中 `delegation` 已经是：
```yaml
delegation:
  model: ''         # 为空 = 继承主模型 deepseek-chat
  provider: ''
```

这正好就是我们要的——**执行型 Agent 默认走 deepseek-chat**。
VL2 只有在需要看图时才按需调用，不占用 delegation 配置。

---

## 五、如果要默认长期配置

如果你希望以后看图也能走自动化流程，可以增加一个 `auxiliary.vision` 的配置指向 VL2：

```yaml
auxiliary:
  vision:
    provider: deepseek
    model: deepseek-vl2-small
    base_url: https://api.deepseek.com/v1
    api_key: ''
    timeout: 120
```

这样 Hermes 的 vision 功能自动用 VL2 做图片分析。但注意：这只能用于 `vision_analyze` 工具，不能用于子 Agent。

---

## 六、模型选型建议

| 场景 | 推荐模型 | 理由 |
|------|---------|------|
| 日常开发（写代码/固件/后端）| `deepseek-chat` | function calling 支持好 |
| 看图提取尺寸 | `deepseek-vl2-small` | 便宜，够用 |
| 复杂模具图分析 | `deepseek-vl2` | 比 small 版更稳 |
| DFM 分析 + 报告整理 | VL2 识图 → Chat 出报告 | 组合最优 |

---

*配置路径：~/.hermes/config.yaml*
*修改后重启 hermes 生效*
