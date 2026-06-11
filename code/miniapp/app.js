/**
 * KeepSafe 微信小程序 - App 入口
 * 
 * 负责:
 * 1. 全局状态管理 (token, userInfo, deviceList)
 * 2. 启动时 token 验证 + 静默登录
 * 3. Token 过期自动处理
 */

App({
  globalData: {
    userInfo: null,
    token: null,
    isLoggedIn: false,
    deviceList: [],
    currentDevice: null
  },

  onLaunch() {
    // 从本地存储恢复登录状态
    const token = wx.getStorageSync('token')
    if (token) {
      // 验证 token 是否过期
      const auth = require('./utils/auth')
      if (!auth.isTokenExpired(token)) {
        this.globalData.token = token
        this.globalData.isLoggedIn = true
      } else {
        // Token 已过期，清除
        wx.removeStorageSync('token')
        wx.removeStorageSync('userInfo')
      }
    }
    console.log('[KeepSafe] App launched, loggedIn:', this.globalData.isLoggedIn)
  },

  onShow() {
    // 检查登录状态，如 token 有效则验证
    if (this.globalData.isLoggedIn) {
      this.silentLogin()
    }
  },

  /**
   * 静默登录 - 用现有 token 验证登录状态
   * 如果 token 已过期或无效，清除认证信息
   */
  silentLogin() {
    const api = require('./utils/api')
    const auth = require('./utils/auth')
    const token = this.globalData.token || wx.getStorageSync('token')

    if (!token) return

    // 先检查 token 是否已过期
    if (auth.isTokenExpired(token)) {
      this.clearAuth()
      return
    }

    // 用 token 请求用户信息来验证有效性
    api.getUserInfo()
      .then((user) => {
        // Token 有效，更新用户信息
        this.globalData.token = token
        this.globalData.isLoggedIn = true
        this.globalData.userInfo = {
          user_id: user.user_id,
          nickName: user.nickname || user.nickName || '',
          avatarUrl: user.avatar_url || ''
        }
      })
      .catch((err) => {
        // 401/403 - Token 无效
        if (err && (err.code === 401 || err.statusCode === 401)) {
          console.log('[KeepSafe] Token invalid, clearing auth')
          this.clearAuth()
        }
        // 网络错误等不做处理，保留现有 token
      })
  },

  /**
   * 清除认证信息
   */
  clearAuth() {
    this.globalData.token = null
    this.globalData.isLoggedIn = false
    this.globalData.userInfo = null
    this.globalData.deviceList = []
    this.globalData.currentDevice = null
    wx.removeStorageSync('token')
    wx.removeStorageSync('userInfo')
    console.log('[KeepSafe] Auth cleared')
  },

  /**
   * 设置认证信息
   * @param {string} token - JWT access token
   * @param {object} userInfo - 用户信息 { user_id, nickname?, avatar_url? }
   */
  setAuth(token, userInfo) {
    this.globalData.token = token
    this.globalData.isLoggedIn = true
    this.globalData.userInfo = userInfo || {}
    wx.setStorageSync('token', token)
    if (userInfo) {
      wx.setStorageSync('userInfo', userInfo)
    }
    console.log('[KeepSafe] Auth set, user_id:', userInfo?.user_id)
  }
})
