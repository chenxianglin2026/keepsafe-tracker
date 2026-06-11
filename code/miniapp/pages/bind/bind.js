/**
 * 设备绑定页面 - 输入设备码 + 密钥完成绑定
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
