/**
 * API 封装模块
 * 统一管理所有后端 REST API 调用
 * baseUrl: http://localhost:8000/api/v1
 */

const BASE_URL = 'http://43.163.5.90:8000/api/v1'

/**
 * 获取存储的 token
 */
function getToken() {
  const app = getApp()
  return app.globalData.token || wx.getStorageSync('token') || ''
}

/**
 * 通用请求头
 */
function getHeaders() {
  const token = getToken()
  const headers = {
    'Content-Type': 'application/json',
  }
  if (token) {
    headers['Authorization'] = `Bearer ${token}`
  }
  return headers
}

/**
 * 通用请求封装
 * @param {string} method - HTTP method
 * @param {string} path - API 路径（不含 baseUrl）
 * @param {object} data - 请求体数据
 * @param {object} options - 额外选项
 * @returns {Promise}
 */
function request(method, path, data = null, options = {}) {
  return new Promise((resolve, reject) => {
    const url = `${BASE_URL}${path}`
    const header = { ...getHeaders(), ...options.headers }

    wx.request({
      url,
      method,
      data,
      header,
      timeout: options.timeout || 10000,
      success: (res) => {
        if (res.statusCode >= 200 && res.statusCode < 300) {
          resolve(res.data)
        } else if (res.statusCode === 401) {
          // Token 过期，清除登录状态
          const app = getApp()
          app.clearAuth()
          wx.navigateTo({ url: '/pages/login/login' })
          reject(new Error('登录已过期，请重新登录'))
        } else {
          reject({
            code: res.statusCode,
            message: res.data?.detail || res.data?.message || '请求失败',
            data: res.data
          })
        }
      },
      fail: (err) => {
        reject({
          code: -1,
          message: '网络连接失败，请检查网络设置',
          raw: err
        })
      }
    })
  })
}

/** HTTP 方法快捷封装 */
const api = {
  get: (path, params = {}, options = {}) => request('GET', path, params, options),
  post: (path, data = {}, options = {}) => request('POST', path, data, options),
  put: (path, data = {}, options = {}) => request('PUT', path, data, options),
  patch: (path, data = {}, options = {}) => request('PATCH', path, data, options),
  delete: (path, data = {}, options = {}) => request('DELETE', path, data, options),
}

// ============================================================
// 设备相关 API
// ============================================================

/**
 * 获取设备列表
 * @returns {Promise<Array>}
 */
api.getDeviceList = () => api.get('/users/me/devices')

/**
 * 绑定新设备
 * @param {string} deviceId - 设备 ID
 * @param {string} token - 设备绑定码
 * @param {string} userId - 用户 ID
 * @param {string} nickname - 设备昵称（可选）
 * @returns {Promise}
 */
api.bindDevice = (deviceId, nickname) => {
  const app = getApp()
  const userId = app.globalData.userInfo?.user_id || ''
  const token = app.globalData.token || ''
  return api.post('/devices/bind', {
    device_id: deviceId,
    token: token,
    user_id: userId,
    ...(nickname ? { nickname } : {})
  })
}

/**
 * 解绑设备
 * @param {string} deviceId - 设备 ID
 * @param {string} userId - 用户 ID
 * @returns {Promise}
 */
api.unbindDevice = (deviceId, userId) => api.delete(`/devices/${deviceId}/bind?user_id=${userId}`)

/**
 * 获取设备最新位置
 * @param {string} deviceId - 设备 ID
 * @returns {Promise<{latitude: number, longitude: number, timestamp: string, battery: number}>}
 */
api.getDeviceLocation = (deviceId) => api.get(`/devices/${deviceId}/location`)

/**
 * 获取设备状态
 * @param {string} deviceId - 设备 ID
 * @returns {Promise}
 */
api.getDeviceStatus = (deviceId) => api.get(`/devices/${deviceId}/status`)

/**
 * 获取设备位置历史
 * @param {string} deviceId - 设备 ID
 * @param {string} from - 起始时间 ISO 字符串
 * @param {string} to - 结束时间 ISO 字符串
 * @returns {Promise<Array>}
 */
api.getDeviceLocationHistory = (deviceId, from, to) =>
  api.get(`/devices/${deviceId}/history`, { from: from, to: to })

/**
 * 获取 SOS 事件列表
 * @param {string} deviceId - 设备 ID
 * @returns {Promise<Array>}
 */
api.getSosEvents = (deviceId) => api.get(`/devices/${deviceId}/sos/events`)

// ============================================================
// 围栏相关 API
// ============================================================

/**
 * 获取设备围栏列表
 * @param {string} deviceId - 设备 ID
 * @returns {Promise<Array>}
 */
api.getFenceList = (deviceId) => api.get(`/devices/${deviceId}/fences`)

/**
 * 创建围栏
 * @param {string} deviceId - 设备 ID
 * @param {object} fenceData - { name, latitude, longitude, radius, enable }
 * @returns {Promise}
 */
api.createFence = (deviceId, fenceData) => api.post(`/devices/${deviceId}/fences`, fenceData)

/**
 * 更新围栏
 * @param {string} deviceId - 设备 ID
 * @param {string} fenceId - 围栏 ID
 * @param {object} fenceData - { name, latitude, longitude, radius, enable }
 * @returns {Promise}
 */
api.updateFence = (deviceId, fenceId, fenceData) =>
  api.put(`/devices/${deviceId}/fences/${fenceId}`, fenceData)

/**
 * 删除围栏
 * @param {string} deviceId - 设备 ID
 * @param {string} fenceId - 围栏 ID
 * @returns {Promise}
 */
api.deleteFence = (deviceId, fenceId) => api.delete(`/devices/${deviceId}/fences/${fenceId}`)

// ============================================================
// 告警相关 API
// ============================================================

/**
 * 获取告警列表
 * @param {object} params - { device_id, type, page, page_size }
 * @returns {Promise<{items: Array, total: number}>}
 */
api.getAlertList = (params = {}) => api.get('/alerts/', params)

/**
 * 标记告警为已读
 * @param {string} alertId - 告警 ID
 * @returns {Promise}
 */
api.markAlertRead = (alertId) => api.put(`/alerts/${alertId}/read`)

/**
 * 标记所有告警为已读
 * @returns {Promise}
 */
api.markAllAlertsRead = () => api.put('/alerts/read-all')

// ============================================================
// 用户相关 API
// ============================================================

/**
 * 用户登录（邮箱+密码）
 * @param {string} email - 邮箱
 * @param {string} password - 密码
 * @returns {Promise<{access_token: string, user_id: string}>}
 */
api.login = (email, password) => api.post('/users/login', { email, password })

/**
 * 用户注册
 * @param {string} email - 邮箱
 * @param {string} password - 密码
 * @param {string} nickname - 昵称（可选）
 * @returns {Promise}
 */
api.register = (email, password, nickname) => api.post('/users/register', { email, password, nickname })

/**
 * 获取用户信息
 * @returns {Promise}
 */
api.getUserInfo = () => api.get('/users/profile')

/**
 * 更新用户信息
 * @param {object} data - { nickname, avatar_url }
 * @returns {Promise}
 */
api.updateUserInfo = (data) => api.put('/users/profile', data)

/**
 * 注册推送 token
 * @param {string} platform - 平台（ios/android）
 * @param {string} token - 推送 token
 * @returns {Promise}
 */
api.registerPushToken = (platform, token) => api.post('/users/me/push-token', { platform, token })

module.exports = api
