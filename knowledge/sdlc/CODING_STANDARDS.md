# 编码规范

## 通用
- 不允许硬编码 API Key / Token / 密码 → 必须用 `{{PLACEHOLDER}}`
- 异常必须有 try-catch 处理
- 关键函数必须有 docstring
- 日志不能泄露用户隐私（位置、手机号等）

## 后端
- Python 遵循 PEP8
- API 必须有输入校验
- 数据库使用参数化查询防注入

## iOS
- 遵守 SwiftLint 规范
- 定位权限使用 `requestWhenInUseAuthorization`
- 后台定位需配置 Capabilities

## 嵌入式
- C 语言用 MISRA-C 子集
- 看门狗必须配置
- 低功耗通过 GPIO 中断唤醒
