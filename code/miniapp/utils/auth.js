/**
 * 登录 + Token 管理模块
 */

const api = require('./api')

/**
 * 邮箱密码登录
 * @param {string} email - 邮箱
 * @param {string} password - 密码
 * @returns {Promise<{access_token: string, user_id: string}>}
 */
function loginWithEmail(email, password) {
  return new Promise((resolve, reject) => {
    wx.showLoading({ title: '登录中...', mask: true })

    api.login(email, password)
      .then((result) => {
        wx.hideLoading()
        const app = getApp()
        app.setAuth(result.access_token, { user_id: result.user_id })
        resolve(result)
      })
      .catch((err) => {
        wx.hideLoading()
        reject(err)
      })
  })
}

/**
 * 注册
 * @param {string} email - 邮箱
 * @param {string} password - 密码
 * @param {string} nickname - 昵称（可选）
 * @returns {Promise}
 */
function register(email, password, nickname) {
  return api.register(email, password, nickname)
}

/**
 * 检查登录状态，未登录则跳转
 * @param {boolean} autoRedirect - 是否自动跳转登录页
 * @returns {Promise<boolean>}
 */
function checkLogin(autoRedirect = true) {
  return new Promise((resolve) => {
    const app = getApp()
    if (app.globalData.isLoggedIn && app.globalData.token) {
      resolve(true)
      return
    }

    // 尝试从 Storage 恢复
    const token = wx.getStorageSync('token')
    if (token) {
      app.globalData.token = token
      app.globalData.isLoggedIn = true
      resolve(true)
      return
    }

    if (autoRedirect) {
      wx.navigateTo({ url: '/pages/login/login' })
    }
    resolve(false)
  })
}

/**
 * 获取当前 token
 * @returns {string}
 */
function getToken() {
  const app = getApp()
  return app.globalData.token || wx.getStorageSync('token') || ''
}

/**
 * 登出
 */
function logout() {
  const app = getApp()
  app.clearAuth()
  wx.reLaunch({ url: '/pages/login/login' })
}

module.exports = {
  loginWithEmail,
  register,
  checkLogin,
  getToken,
  logout
}
