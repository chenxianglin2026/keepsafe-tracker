/**
 * API 封装模块 — KeepSafe 微信小程序
 * 统一管理所有后端 REST API 调用
 * baseUrl: http://43.163.5.90:8000/api/v1
 */

const BASE_URL = 'http://43.163.5.90:8000/api/v1'

/** 最大重试次数 */
const MAX_RETRIES = 2

/** 需要重试的 HTTP 状态码 (网络类错误) */
const RETRYABLE_STATUS = [502, 503, 504]

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
 * 标准化错误对象
 */
function normalizeError(err) {
  if (err instanceof Error) {
    return { code: -1, message: err.message || '网络连接失败', raw: err }
  }
  if (typeof err === 'object' && err !== null) {
    return {
      code: err.statusCode || err.code || -1,
      message: err.message || (err.data && (err.data.detail || err.data.message)) || '请求失败',
      data: err.data,
      raw: err
    }
  }
  return { code: -1, message: String(err), raw: err }
}

/**
 * 通用请求封装 (带重试)
 * @param {string} method - HTTP method
 * @param {string} path - API 路径（不含 baseUrl）
 * @param {object} data - 请求体/查询参数数据
 * @param {object} options - 额外选项 { timeout, headers, skipAuth }
 * @returns {Promise}
 */
function request(method, path, data = null, options = {}, retryCount = 0) {
  return new Promise((resolve, reject) => {
    const url = `${BASE_URL}${path}`
    const header = { ...getHeaders(), ...options.headers }

    wx.request({
      url,
      method,
      data: method === 'GET' && data ? null : data,
      header,
      timeout: options.timeout || 15000,
      success: (res) => {
        // 成功 (2xx)
        if (res.statusCode >= 200 && res.statusCode < 300) {
          resolve(res.data)
          return
        }

        // 401 — Token 过期
        if (res.statusCode === 401) {
          const app = getApp()
          app.clearAuth()
          wx.navigateTo({ url: '/pages/login/login' })
          reject(normalizeError({
            statusCode: 401,
            message: '登录已过期，请重新登录',
            data: res.data
          }))
          return
        }

        // 403 — 权限不足
        if (res.statusCode === 403) {
          reject(normalizeError({
            statusCode: 403,
            message: res.data?.detail || '没有权限执行此操作',
            data: res.data
          }))
          return
        }

        // 可重试的错误
        const err = {
          statusCode: res.statusCode,
          message: res.data?.detail || res.data?.message || `服务器错误 (${res.statusCode})`,
          data: res.data
        }

        if (RETRYABLE_STATUS.includes(res.statusCode) && retryCount < MAX_RETRIES) {
          console.warn(`[KeepSafe API] Retrying ${path} (${retryCount + 1}/${MAX_RETRIES})`)
          setTimeout(() => {
            request(method, path, data, options, retryCount + 1)
              .then(resolve)
              .catch(reject)
          }, 1000 * (retryCount + 1))
          return
        }

        reject(normalizeError(err))
      },
      fail: (err) => {
        // 网络错误 — 重试
        if (retryCount < MAX_RETRIES) {
          console.warn(`[KeepSafe API] Network error, retrying ${path} (${retryCount + 1}/${MAX_RETRIES})`)
          setTimeout(() => {
            request(method, path, data, options, retryCount + 1)
              .then(resolve)
              .catch(reject)
          }, 1000 * (retryCount + 1))
          return
        }

        reject(normalizeError({
          statusCode: -1,
          message: '网络连接失败，请检查网络设置',
          raw: err
        }))
      }
    })
  })
}

/** ============================================================
 * HTTP 方法快捷封装
 * ============================================================ */

const api = {
  get: (path, params = {}, options = {}) => {
    // wx.request 对 GET 请求需将 params 拼接到 URL
    const qs = Object.keys(params)
      .filter(k => params[k] !== null && params[k] !== undefined)
      .map(k => `${encodeURIComponent(k)}=${encodeURIComponent(params[k])}`)
      .join('&')
    const fullPath = qs ? `${path}?${qs}` : path
    return request('GET', fullPath, null, options)
  },
  post: (path, data = {}, options = {}) => request('POST', path, data, options),
  put: (path, data = {}, options = {}) => request('PUT', path, data, options),
  patch: (path, data = {}, options = {}) => request('PATCH', path, data, options),
  delete: (path, data = {}, options = {}) => request('DELETE', path, data, options),
}

/** ============================================================
 * 用户相关 API
 * ============================================================ */

/**
 * 用户登录（邮箱+密码）
 * @param {string} email
 * @param {string} password
 * @returns {Promise<{access_token: string, token_type: string, user_id: string}>}
 */
api.login = (email, password) => api.post('/users/login', { email, password })

/**
 * 用户注册
 * @param {string} email
 * @param {string} password
 * @param {string} [nickname]
 * @returns {Promise<{message: string}>}
 */
api.register = (email, password, nickname) =>
  api.post('/users/register', { email, password, nickname })

/**
 * 获取当前用户信息
 * @returns {Promise<{user_id: string, email: string, nickname: string, avatar_url: string, phone: string, created_at: string}>}
 */
api.getUserInfo = () => api.get('/users/profile')

/**
 * 更新用户信息
 * @param {object} data - { nickname?, avatar_url?, phone? }
 * @returns {Promise}
 */
api.updateUserInfo = (data) => api.put('/users/profile', data)

/**
 * 注册推送 token
 * @param {string} platform - "ios" | "android"
 * @param {string} token - FCM / APNs token
 * @returns {Promise<{message: string}>}
 */
api.registerPushToken = (platform, token) =>
  api.post('/users/me/push-token', { platform, token })

/** ============================================================
 * 设备相关 API
 * ============================================================ */

/**
 * 获取已绑定设备列表
 * @returns {Promise<Array<{device_id: string, nickname: string, bound_at: string, is_active: boolean, last_seen: string}>>}
 */
api.getDeviceList = () => api.get('/users/me/devices')

/**
 * 获取设备最新位置
 * @param {string} deviceId
 * @returns {Promise<{device_id: string, ts: string, lat: number, lng: number, battery: number, ...}>}
 */
api.getDeviceLocation = (deviceId) => api.get(`/devices/${deviceId}/location`)

/**
 * 获取设备状态
 * @param {string} deviceId
 * @returns {Promise<{device_id: string, online: boolean, battery: number, charging: boolean, rssi: number, last_seen: string, lat: number, lng: number}>}
 */
api.getDeviceStatus = (deviceId) => api.get(`/devices/${deviceId}/status`)

/**
 * 获取设备位置历史
 * @param {string} deviceId
 * @param {string} [from] - ISO 起始时间
 * @param {string} [to] - ISO 结束时间
 * @param {number} [limit=100] - 返回条数
 * @returns {Promise<Array>}
 */
api.getDeviceLocationHistory = (deviceId, from, to, limit = 100) =>
  api.get(`/devices/${deviceId}/history`, { from, to, limit })

/**
 * 获取 SOS 事件列表
 * @param {string} deviceId
 * @param {number} [limit=50] - 返回条数
 * @returns {Promise<Array>}
 */
api.getSosEvents = (deviceId, limit = 50) =>
  api.get(`/devices/${deviceId}/sos/events`, { limit })

/** ============================================================
 * 设备绑定 API
 * ============================================================ */

/**
 * 绑定设备
 * @param {string} deviceId - 设备 ID
 * @param {string} deviceToken - 设备密钥/令牌
 * @param {string} [nickname] - 设备昵称（可选）
 * @returns {Promise<{success: boolean, message: string}>}
 */
api.bindDevice = (deviceId, deviceToken, nickname) => {
  const app = getApp()
  const userId = app.globalData.userInfo?.user_id || ''
  return api.post('/devices/bind', {
    device_id: deviceId,
    token: deviceToken,
    user_id: userId,
    ...(nickname ? { nickname } : {})
  })
}

/**
 * 解绑设备 (后端通过 JWT 识别用户，无需传 userId)
 * @param {string} deviceId
 * @returns {Promise<{success: boolean, message: string}>}
 */
api.unbindDevice = (deviceId) => api.delete(`/devices/${deviceId}/bind`)

/** ============================================================
 * 围栏相关 API
 * ============================================================ */

/**
 * 获取设备围栏列表
 * @param {string} deviceId
 * @returns {Promise<Array>} - 直接返回围栏数组
 */
api.getFenceList = (deviceId) =>
  api.get(`/devices/${deviceId}/fences`).then(result => {
    // 后端返回 { fences: [...], total: N }，解包为纯数组
    if (result && Array.isArray(result.fences)) {
      return result.fences
    }
    return []
  })

/**
 * 获取单个围栏详情
 * @param {string} deviceId
 * @param {number} fenceId
 * @returns {Promise<{id: number, device_id: string, name: string, lat: number, lng: number, radius: number, enabled: boolean, ...}>}
 */
api.getFenceById = (deviceId, fenceId) =>
  api.get(`/devices/${deviceId}/fences/${fenceId}`)

/**
 * 创建围栏
 * @param {string} deviceId
 * @param {object} fenceData - { name, lat, lng, radius, enabled? }
 * @returns {Promise}
 */
api.createFence = (deviceId, fenceData) =>
  api.post(`/devices/${deviceId}/fences`, fenceData)

/**
 * 更新围栏
 * @param {string} deviceId
 * @param {number} fenceId
 * @param {object} fenceData - { name?, lat?, lng?, radius?, enabled? }
 * @returns {Promise}
 */
api.updateFence = (deviceId, fenceId, fenceData) =>
  api.put(`/devices/${deviceId}/fences/${fenceId}`, fenceData)

/**
 * 删除围栏
 * @param {string} deviceId
 * @param {number} fenceId
 * @returns {Promise<{message: string}>}
 */
api.deleteFence = (deviceId, fenceId) =>
  api.delete(`/devices/${deviceId}/fences/${fenceId}`)

/** ============================================================
 * 告警相关 API
 * ============================================================ */

/**
 * 获取告警列表 (分页 + 筛选)
 * @param {object} [params] - { page, page_size, alert_type, is_read }
 * @returns {Promise<{items: Array, total: number, page: number, page_size: number}>}
 */
api.getAlertList = (params = {}) => api.get('/alerts/', params)

/**
 * 标记单个告警为已读
 * @param {number|string} alertId
 * @returns {Promise}
 */
api.markAlertRead = (alertId) => api.put(`/alerts/${alertId}/read`)

/**
 * 标记所有告警为已读
 * @returns {Promise<{message: string}>}
 */
api.markAllAlertsRead = () => api.put('/alerts/read-all')

/** ============================================================
 * 分享相关 API
 * ============================================================ */

/**
 * 获取设备位置分享链接
 * TODO: 后端暂未实现，需后续添加 /devices/{deviceId}/share-link 端点
 * @param {string} deviceId
 * @returns {Promise<{share_url: string}>}
 */
api.getShareLink = (deviceId) => {
  return new Promise((resolve, reject) => {
    wx.showToast({ title: '分享功能开发中', icon: 'none' })
    reject({ code: -1, message: '分享功能暂未开放' })
  })
  // 后端端点就绪后启用:
  // api.get(`/devices/${deviceId}/share-link`)
}

module.exports = api
