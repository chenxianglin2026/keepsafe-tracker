/**
 * 登录/注册页面
 */
const auth = require('../../utils/auth')

Page({
  data: {
    mode: 'login',   // 'login' | 'register'
    email: '',
    password: '',
    nickname: '',
    logging: false,
    registering: false
  },

  onLoad(options) {
    // 如果已登录，直接跳首页
    if (auth.getToken()) {
      wx.switchTab({ url: '/pages/index/index' })
      return
    }
    // 支持 URL 参数指定模式
    if (options.mode === 'register') {
      this.setData({ mode: 'register' })
    }
  },

  // ============================================================
  // 输入事件
  // ============================================================

  onEmailInput(e) {
    this.setData({ email: e.detail.value.trim() })
  },

  onPasswordInput(e) {
    this.setData({ password: e.detail.value })
  },

  onNicknameInput(e) {
    this.setData({ nickname: e.detail.value.trim() })
  },

  // ============================================================
  // 登录
  // ============================================================

  onLogin() {
    const { email, password } = this.data

    if (!email) {
      wx.showToast({ title: '请输入邮箱', icon: 'none' })
      return
    }
    if (!password) {
      wx.showToast({ title: '请输入密码', icon: 'none' })
      return
    }
    if (password.length < 6) {
      wx.showToast({ title: '密码至少6位', icon: 'none' })
      return
    }

    this.setData({ logging: true })

    auth.loginWithEmail(email, password)
      .then(() => {
        wx.showToast({ title: '登录成功', icon: 'success' })
        setTimeout(() => {
          wx.switchTab({ url: '/pages/index/index' })
        }, 500)
      })
      .catch((err) => {
        this.setData({ logging: false })
        wx.showToast({
          title: err.message || '登录失败，请检查账号密码',
          icon: 'none',
          duration: 2500
        })
      })
  },

  // ============================================================
  // 注册
  // ============================================================

  onRegister() {
    const { email, password, nickname } = this.data

    if (!nickname) {
      wx.showToast({ title: '请输入昵称', icon: 'none' })
      return
    }
    if (!email) {
      wx.showToast({ title: '请输入邮箱', icon: 'none' })
      return
    }
    if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) {
      wx.showToast({ title: '请输入有效邮箱', icon: 'none' })
      return
    }
    if (!password || password.length < 6) {
      wx.showToast({ title: '密码至少6位', icon: 'none' })
      return
    }

    this.setData({ registering: true })

    auth.register(email, password, nickname)
      .then(() => {
        wx.showToast({ title: '注册成功', icon: 'success' })
        // 注册成功后自动登录
        return auth.loginWithEmail(email, password)
      })
      .then(() => {
        setTimeout(() => {
          wx.switchTab({ url: '/pages/index/index' })
        }, 500)
      })
      .catch((err) => {
        this.setData({ registering: false })
        wx.showToast({
          title: err.message || '注册失败',
          icon: 'none',
          duration: 2500
        })
      })
  },

  // ============================================================
  // 切换登录/注册
  // ============================================================

  onSwitchMode() {
    const nextMode = this.data.mode === 'login' ? 'register' : 'login'
    this.setData({ mode: nextMode })
  },

  // ============================================================
  // 协议
  // ============================================================

  onPrivacy() {
    wx.showModal({
      title: '隐私政策',
      content: 'KeepSafe 承诺保护您的隐私安全。我们仅收集必要的定位数据用于设备位置追踪，不会泄露您的个人信息。',
      showCancel: false,
      confirmText: '知道了'
    })
  },

  onTerms() {
    wx.showModal({
      title: '服务条款',
      content: '欢迎使用 KeepSafe 老人小孩防丢器服务。使用本服务即表示您同意遵守相关法律法规。',
      showCancel: false,
      confirmText: '知道了'
    })
  }
})
