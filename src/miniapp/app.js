App({
  globalData: {
    token: '',
    deviceList: [],
    userInfo: null
  },
  onLaunch() {
    // 检查登录状态
    const token = wx.getStorageSync('token')
    if (token) {
      this.globalData.token = token
    }
  }
})
