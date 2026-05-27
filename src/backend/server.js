const express = require('express')
const mqtt = require('mqtt')
const app = express()
const PORT = 3800

app.use(express.json())

// ============ 内存数据库（后续替换为 SQLite） ============
const db = {
  users: [],
  devices: [],
  locations: [],
  fences: []
}

// ============ 微信小程序 API ============

// 微信登录
app.post('/api/login', (req, res) => {
  const { code, nickName } = req.body
  // 1. 用 code 向微信服务器换取 openid（上线时实现）
  // 2. 生成 token
  const token = 'token_' + Date.now()
  db.users.push({ id: 1, nickName, token, openid: 'mock_' + code })
  res.json({ code: 0, data: { token } })
})

// 绑定设备（扫码）
app.post('/api/device/bind', (req, res) => {
  const { deviceId, token } = req.body
  const user = db.users.find(u => u.token === token)
  if (!user) return res.status(401).json({ code: 1, msg: '未登录' })
  
  db.devices.push({
    id: deviceId,
    userId: user.id,
    name: '新设备',
    online: false,
    battery: 100
  })
  res.json({ code: 0, data: { success: true } })
})

// 设备列表
app.get('/api/device/list', (req, res) => {
  const devices = db.devices.map(d => ({
    ...d,
    lat: 39.9042,
    lng: 116.4074
  }))
  res.json({ code: 0, data: devices })
})

// 实时位置
app.get('/api/location/:deviceId', (req, res) => {
  const loc = db.locations
    .filter(l => l.deviceId === req.params.deviceId)
    .pop()
  res.json({ code: 0, data: loc || { lat: 39.9042, lng: 116.4074 } })
})

// 创建围栏
app.post('/api/fence', (req, res) => {
  const { deviceId, name, lat, lng, radius } = req.body
  db.fences.push({ id: Date.now(), deviceId, name, lat, lng, radius })
  res.json({ code: 0, data: { success: true } })
})

// 围栏列表
app.get('/api/fence/list', (req, res) => {
  res.json({ code: 0, data: db.fences })
})

// SOS 告警
app.post('/api/sos', (req, res) => {
  const { deviceId, lat, lng } = req.body
  console.log(`🚨 SOS! Device: ${deviceId} at ${lat},${lng}`)
  res.json({ code: 0, data: { alert: true } })
})

// ============ MQTT 设备接入 ============
const MQTT_BROKER = process.env.MQTT_BROKER || 'mqtt://test.mosquitto.org'
const mqttClient = mqtt.connect(MQTT_BROKER)

mqttClient.on('connect', () => {
  console.log('✅ MQTT 已连接')
  mqttClient.subscribe('keepsafe/+/location')
  mqttClient.subscribe('keepsafe/+/sos')
  mqttClient.subscribe('keepsafe/+/battery')
})

mqttClient.on('message', (topic, message) => {
  const data = JSON.parse(message.toString())
  const deviceId = topic.split('/')[1]
  
  if (topic.endsWith('/location')) {
    db.locations.push({ deviceId, ...data, time: Date.now() })
    console.log(`📍 Device ${deviceId}: ${data.lat},${data.lng}`)
  }
  
  if (topic.endsWith('/sos')) {
    console.log(`🚨 SOS from ${deviceId}!`)
    // TODO: 推送微信通知
  }
})

// ============ 启动 ============
app.listen(PORT, () => {
  console.log(`✅ KeepSafe 后端运行在 http://localhost:${PORT}`)
  console.log(`📡 MQTT 连接: ${MQTT_BROKER}`)
})

// 错误处理
process.on('uncaughtException', (err) => {
  console.error('未捕获异常:', err)
})
