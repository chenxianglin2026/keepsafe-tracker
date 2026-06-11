/**
 * 登录 + JWT Token 管理模块
 *
 * 职责:
 * 1. 用户登录/注册
 * 2. JWT token 存储、读取、验证、过期检测
 * 3. 自动登出 + 跳转登录页
 */

const api = require('./api')

/** Token 过期前多久触发刷新（毫秒），默认 5 分钟 */
const TOKEN_REFRESH_MARGIN = 5 * 60 * 1000

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

    // 1. 从全局状态检查
    if (app.globalData.isLoggedIn && app.globalData.token) {
      // 检查 token 是否过期
      if (isTokenExpired(app.globalData.token)) {
        app.clearAuth()
        if (autoRedirect) {
          wx.navigateTo({ url: '/pages/login/login' })
        }
        resolve(false)
        return
      }
      resolve(true)
      return
    }

    // 2. 尝试从 Storage 恢复
    const token = wx.getStorageSync('token')
    if (token) {
      if (isTokenExpired(token)) {
        app.clearAuth()
        if (autoRedirect) {
          wx.navigateTo({ url: '/pages/login/login' })
        }
        resolve(false)
        return
      }
      app.globalData.token = token
      app.globalData.isLoggedIn = true
      resolve(true)
      return
    }

    // 3. 未登录
    if (autoRedirect) {
      wx.navigateTo({ url: '/pages/login/login' })
    }
    resolve(false)
  })
}

/**
 * 解码 JWT payload（不验证签名，仅提取 payload 部分）
 * @param {string} token - JWT token string
 * @returns {object|null} 解码后的 payload，失败返回 null
 */
function decodeTokenPayload(token) {
  if (!token) return null
  try {
    const parts = token.split('.')
    if (parts.length !== 3) return null
    // Base64url 解码 payload
    const payload = parts[1]
    const decoded = wx.base64ToArrayBuffer
      ? _decodeWithAPI(payload)
      : _decodeManual(payload)
    if (!decoded) return null
    return JSON.parse(decoded)
  } catch (e) {
    return null
  }
}

/**
 * 使用 wx.base64ToArrayBuffer API 解码
 */
function _decodeWithAPI(payload) {
  try {
    const base64 = _base64UrlToBase64(payload)
    const buf = wx.base64ToArrayBuffer(base64)
    // ArrayBuffer → string
    const bytes = new Uint8Array(buf)
    let str = ''
    for (let i = 0; i < bytes.length; i++) {
      str += String.fromCharCode(bytes[i])
    }
    return str
  } catch (e) {
    return null
  }
}

/**
 * 手动 base64 解码（fallback）
 */
function _decodeManual(payload) {
  try {
    const base64 = _base64UrlToBase64(payload)
    // 微信小程序可能没有 atob，尝试用内置方式
    const chars = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/='
    let output = ''
    let i = 0
    while (i < base64.length) {
      const enc1 = chars.indexOf(base64.charAt(i++))
      const enc2 = chars.indexOf(base64.charAt(i++))
      const enc3 = chars.indexOf(base64.charAt(i++))
      const enc4 = chars.indexOf(base64.charAt(i++))
      const chr1 = (enc1 << 2) | (enc2 >> 4)
      const chr2 = ((enc2 & 15) << 4) | (enc3 >> 2)
      const chr3 = ((enc3 & 3) << 6) | enc4
      output += String.fromCharCode(chr1)
      if (enc3 !== 64) output += String.fromCharCode(chr2)
      if (enc4 !== 64) output += String.fromCharCode(chr3)
    }
    return output
  } catch (e) {
    return null
  }
}

/**
 * Base64url → Base64 标准格式
 */
function _base64UrlToBase64(str) {
  let base64 = str.replace(/-/g, '+').replace(/_/g, '/')
  while (base64.length % 4) {
    base64 += '='
  }
  return base64
}

/**
 * 判断 token 是否已过期
 * @param {string} token - JWT token
 * @returns {boolean} true 表示已过期
 */
function isTokenExpired(token) {
  const payload = decodeTokenPayload(token)
  if (!payload || !payload.exp) {
    // 无法解码或没有 exp 字段，保守处理为未过期
    return false
  }
  // exp 是 Unix 时间戳（秒），加上刷新余量
  const now = Math.floor(Date.now() / 1000)
  const margin = Math.floor(TOKEN_REFRESH_MARGIN / 1000)
  return (payload.exp - margin) <= now
}

/**
 * 获取 token 剩余有效时间（秒）
 * @param {string} token
 * @returns {number} 剩余秒数，-1 表示无法解析
 */
function getTokenRemainingTime(token) {
  const payload = decodeTokenPayload(token)
  if (!payload || !payload.exp) return -1
  return payload.exp - Math.floor(Date.now() / 1000)
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
 * 获取当前用户 ID
 * @returns {string}
 */
function getUserId() {
  const app = getApp()
  if (app.globalData.userInfo && app.globalData.userInfo.user_id) {
    return app.globalData.userInfo.user_id
  }
  const payload = decodeTokenPayload(getToken())
  return (payload && payload.sub) || ''
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
  getUserId,
  logout,
  decodeTokenPayload,
  isTokenExpired,
  getTokenRemainingTime
}
