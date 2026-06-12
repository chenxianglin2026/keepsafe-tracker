/**
 * 设备绑定页面 - 输入设备码 + 密钥完成绑定
 * 支持: 手动输入 / 扫码绑定 / 粘贴剪贴板
 */
const api = require('../../utils/api')
const auth = require('../../utils/auth')

Page({
  data: {
    deviceId: '',
    deviceToken: '',
    nickname: '',
    binding: false
  },

  onLoad() {
    // 检查登录状态
    auth.checkLogin(true)
  },

  onDeviceIdInput(e) {
    this.setData({ deviceId: e.detail.value.trim() })
  },

  onTokenInput(e) {
    this.setData({ deviceToken: e.detail.value.trim() })
  },

  onNicknameInput(e) {
    this.setData({ nickname: e.detail.value.trim() })
  },

  /**
   * 扫码绑定 - 调用微信扫一扫
   * 期望二维码内容格式: KS-XXXXXXXX:TOKEN 或直接 JSON
   */
  onScanCode() {
    wx.scanCode({
      scanType: ['qrCode', 'barCode'],
      success: (res) => {
        const code = res.result.trim()
        this.parseScanResult(code)
      },
      fail: (err) => {
        if (err.errMsg.indexOf('cancel') === -1) {
          wx.showToast({ title: '扫码失败，请重试', icon: 'none' })
        }
      }
    })
  },

  /**
   * 从剪贴板粘贴
   */
  onPasteFromClipboard() {
    wx.getClipboardData({
      success: (res) => {
        const text = (res.data || '').trim()
        if (!text) {
          wx.showToast({ title: '剪贴板为空', icon: 'none' })
          return
        }
        this.parseScanResult(text)
      },
      fail: () => {
        wx.showToast({ title: '读取剪贴板失败', icon: 'none' })
      }
    })
  },

  /**
   * 解析扫码/粘贴结果
   * 支持格式:
   *   - "KS-XXXXXXXX:TOKEN"  设备ID:密钥
   *   - "device_id=KS-XXX&token=TOKEN"  URL参数格式
   */
  parseScanResult(code) {
    let deviceId = ''
    let deviceToken = ''

    // 格式1: device_id:token
    if (code.includes(':') && !code.includes('=')) {
      const parts = code.split(':')
      deviceId = parts[0].trim()
      deviceToken = parts.slice(1).join(':').trim()
    }
    // 格式2: URL 参数格式 (含 = 号)
    else if (code.includes('=')) {
      const params = {}
      code.split('&').forEach(pair => {
        const [k, v] = pair.split('=')
        if (k && v) params[k.trim()] = decodeURIComponent(v.trim())
      })
      deviceId = params.device_id || params.id || ''
      deviceToken = params.token || params.key || ''
    }
    // 格式3: 纯设备ID (仅单行文本)
    else {
      deviceId = code
    }

    if (!deviceId) {
      wx.showToast({ title: '无法识别设备信息', icon: 'none' })
      return
    }

    this.setData({
      deviceId,
      deviceToken
    })

    if (deviceToken) {
      wx.showToast({ title: '已识别设备信息', icon: 'success' })
    } else {
      wx.showToast({ title: '已识别设备ID，请补充密钥', icon: 'none' })
    }
  },

  /**
   * 清空输入
   */
  onClear() {
    this.setData({
      deviceId: '',
      deviceToken: '',
      nickname: ''
    })
  },

  /**
   * 执行绑定
   */
  onBind() {
    const { deviceId, deviceToken, nickname } = this.data

    if (!deviceId) {
      wx.showToast({ title: '请输入设备 ID', icon: 'none' })
      return
    }
    if (!deviceToken) {
      wx.showToast({ title: '请输入设备密钥', icon: 'none' })
      return
    }

    this.setData({ binding: true })

    api.bindDevice(deviceId, deviceToken, nickname || undefined)
      .then(() => {
        this.setData({ binding: false })
        wx.showToast({ title: '绑定成功！', icon: 'success' })
        setTimeout(() => {
          wx.navigateBack()
        }, 1500)
      })
      .catch((err) => {
        this.setData({ binding: false })
        wx.showToast({
          title: err.message || '绑定失败，请检查设备码和密钥',
          icon: 'none',
          duration: 3000
        })
      })
  }
})
