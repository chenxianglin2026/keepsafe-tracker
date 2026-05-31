App({
  globalData: {
    userInfo: null,
    token: null,
    isLoggedIn: false,
    deviceList: [],
    currentDevice: null
  },

  onLaunch() {
    // 初始化登录状态
    const token = wx.getStorageSync('token')
    if (token) {
      this.globalData.token = token
      this.globalData.isLoggedIn = true
    }
    console.log('[KeepSafe] App launched')
  },

  onShow() {
    // 检查登录状态
    if (!this.globalData.isLoggedIn) {
      // 尝试静默登录
      this.silentLogin()
    }
  },

  silentLogin() {
    const token = wx.getStorageSync('token')
    if (!token) return

    // 用现有 token 验证登录状态
    wx.request({
      url: 'http://43.163.5.90:8000/api/v1/users/profile',
      method: 'GET',
      header: {
        'Authorization': `Bearer ${token}`
      },
      success: (res) => {
        if (res.statusCode === 200) {
          this.globalData.token = token
          this.globalData.isLoggedIn = true
        } else {
          this.clearAuth()
        }
      },
      fail: () => {
        // 网络错误不强制登出，保留 token
        this.globalData.token = token
        this.globalData.isLoggedIn = true
      }
    })
  },

  clearAuth() {
    this.globalData.token = null
    this.globalData.isLoggedIn = false
    this.globalData.userInfo = null
    wx.removeStorageSync('token')
    wx.removeStorageSync('userInfo')
  },

  setAuth(token, userInfo) {
    this.globalData.token = token
    this.globalData.isLoggedIn = true
    this.globalData.userInfo = userInfo
    wx.setStorageSync('token', token)
    wx.setStorageSync('userInfo', userInfo)
  }
})
