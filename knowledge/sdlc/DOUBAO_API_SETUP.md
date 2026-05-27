# 豆包 API Key 申请指南

> 火山引擎（豆包）官方渠道，2026-05 可用

---

## 申请步骤

### 第一步：注册火山引擎账号

打开：https://console.volcengine.com/
→ 点击右上角「注册」（手机号或邮箱均可）
→ 注册完成后登录

### 第二步：开通豆包大模型 API

1. 进入控制台 → 搜索「豆包大模型」或直接访问：
   https://console.volcengine.com/ark/region:ark+cn-beijing/

2. 点击「立即开通」或「创建 API Key」

3. 在 API Key 管理页面：
   → 点击「创建 API Key」
   → 复制生成的 Key（格式类似：`xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx`）

### 第三步：充值

豆包 API 是后付费，账户需要有余额才能调用：
- 控制台 → 费用中心 → 充值
- 建议首充 **10-50 元**（一张图几分钱，够用很久）
- 支持微信/支付宝

### 第四步：给我 Key

拿到 Key 后告诉我，我帮你配到：
- `~/.hermes/.env`（安全存储）
- `~/.hermes/config.yaml`（模型配置）

---

## API 调用信息

| 项目 | 值 |
|------|-----|
| API Endpoint | `https://ark.cn-beijing.volces.com/api/v3` |
| 看图模型 | `doubao-1.5-vision-pro-250515` |
| 干活模型 | `doubao-1.5-pro-250515` |
| 价格（看图） | 输入 0.35 元 / 百万 tokens |
| 价格（干活） | 输入 0.08 元 / 百万 tokens |
| 单张图成本 | 约 **0.03-0.08 元** |

---

## 配置模板（拿到 Key 后我用这个配）

```yaml
# config.yaml 修改
model:
  default: doubao-api
provider:
  doubao:
    api_key: {{YOUR_KEY}}
    base_url: https://ark.cn-beijing.volces.com/api/v3
# delegation 看图用 vision-pro
delegation:
  model: doubao-1.5-vision-pro-250515
  provider: doubao
```

拿到 Key 告诉我就行，1 分钟配好。
