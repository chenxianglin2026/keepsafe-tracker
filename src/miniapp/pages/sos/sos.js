Page({
  data: {
    time: '3分钟',
    address: '菜市场西南门',
    detail: 'XX区XX路XX号 · 距您1.2km',
    deviceName: '爷爷'
  },

  onLoad(options) {
    if (options.name) {
      this.setData({ deviceName: options.name })
    }
    // 后续从这里接收后端推送的SOS数据
  },

  onNavigate() {
    const { address, detail } = this.data
    wx.openLocation({
      latitude: 39.9042,
      longitude: 116.4074,
      name: address,
      address: detail,
      scale: 18
    })
  },

  onCall() {
    wx.makePhoneCall({
      phoneNumber: '13800138000' // 后续改真实号码
    })
  },

  onSafe() {
    wx.showModal({
      title: '确认平安',
      content: '已联系到' + this.data.deviceName + '了吗？',
      success: (res) => {
        if (res.confirm) {
          wx.showToast({ title: '已确认平安', icon: 'success' })
          // 通知后端关闭SOS
          setTimeout(() => wx.navigateBack(), 1500)
        }
      }
    })
  }
})
