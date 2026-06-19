/**
 * API 封装模块 — KeepSafe 微信小程序
 * 统一管理所有后端 REST API 调用
 * baseUrl: http://43.163.5.90:8000/api/v1
 */

const BASE_URL = 'https://a.7yijia888.com/api/v1'

/** 最大重试次数 */
const MAX_RETRIES = 2

/** 需要重试的 HTTP 状态码 (网络类错误) */
const RETRYABLE_STATUS = [502, 503, 504]

/** 标准错误码 */
const ERR_CODE = {
  NETWORK: -1,
  TIMEOUT: -2,
  AUTH_EXPIRED: -3,
  FORBIDDEN: -4,
  SERVER: -5,
  CANCELLED: -6,
}

/** 默认超时时间 (毫秒) */
const DEFAULT_TIMEOUT = 15000

/** 并发请求追踪: 防止短时间内重复请求同一端点 */
const inflightRequests = new Map()

/** 已注册的请求/响应拦截器 */
const interceptors = {
  request: [],   // (config) => config
  response: [],  // (response) => response
  error: [],     // (error) => error
}

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
 * 将 wx.request 的 fail 回调和 success 中的非2xx 统一为 { code, message, data, raw }
 */
function normalizeError(err) {
  // Error 实例 (网络异常 / JS 异常)
  if (err instanceof Error) {
    const code = err.message && err.message.includes('timeout')
      ? ERR_CODE.TIMEOUT
      : ERR_CODE.NETWORK
    return { code, message: err.message || '网络连接失败', raw: err }
  }
  // wx.request fail 回调的 err 对象
  if (typeof err === 'object' && err !== null) {
    // 超时检测: wx 的 fail 回调中 err.errMsg 可能包含 "timeout"
    if (err.errMsg && /timeout/i.test(err.errMsg)) {
      return { code: ERR_CODE.TIMEOUT, message: '请求超时，请检查网络', raw: err }
    }
    return {
      code: err.statusCode || err.code || ERR_CODE.NETWORK,
      message: err.message
        || (err.data && (err.data.detail || err.data.message))
        || '请求失败',
      data: err.data,
      raw: err
    }
  }
  return { code: ERR_CODE.NETWORK, message: String(err), raw: err }
}

/**
 * 生成请求缓存键
 */
function makeCacheKey(path) {
  return path
}

/**
 * 注册请求拦截器
 * @param {function} fn - (config) => config
 */
api.addRequestInterceptor = (fn) => {
  interceptors.request.push(fn)
}

/**
 * 注册响应拦截器
 * @param {function} fn - (response) => response
 */
api.addResponseInterceptor = (fn) => {
  interceptors.response.push(fn)
}

/**
 * 注册错误拦截器
 * @param {function} fn - (error) => error
 */
api.addErrorInterceptor = (fn) => {
  interceptors.error.push(fn)
}

/**
 * 移除所有拦截器
 */
api.clearInterceptors = () => {
  interceptors.request.length = 0
  interceptors.response.length = 0
  interceptors.error.length = 0
}

/**
 * 清除指定路径的 inflight 请求缓存 (用于手动刷新场景)
 * @param {string} path
 */
api.clearInflight = (path) => {
  inflightRequests.delete(makeCacheKey(path))
}

/**
 * 通用请求封装 (带重试 + 并发去重 + 拦截器)
 * @param {string} method - HTTP method
 * @param {string} path - API 路径（不含 baseUrl）
 * @param {object} data - 请求体/查询参数数据
 * @param {object} options - 额外选项 { timeout, headers, skipAuth, skipDedup, signal }
 * @param {number} [retryCount] - 内部重试计数器
 * @returns {Promise}
 */
function request(method, path, data = null, options = {}, retryCount = 0) {
  const cacheKey = makeCacheKey(path)

  // 并发去重: 如果已有相同请求在进行中且未要求跳过去重，返回同一个 Promise
  if (!options.skipDedup && inflightRequests.has(cacheKey)) {
    const existing = inflightRequests.get(cacheKey)
    // 只对 GET 请求做去重，写操作需要每次真实执行
    if (method === 'GET') {
      return existing
    }
  }

  const promise = new Promise((resolve, reject) => {
    // 检查是否已取消
    if (options.signal && options.signal.aborted) {
      const err = normalizeError({ message: '请求已取消', statusCode: ERR_CODE.CANCELLED })
      reject(err)
      return
    }

    const url = `${BASE_URL}${path}`
    let header = { ...getHeaders(), ...options.headers }

    // 应用请求拦截器
    let reqConfig = { url, method, data: method === 'GET' && data ? null : data, header, timeout: options.timeout || DEFAULT_TIMEOUT }
    for (const fn of interceptors.request) {
      try {
        reqConfig = fn(reqConfig) || reqConfig
      } catch (e) {
        console.error('[KeepSafe API] Request interceptor error:', e)
      }
    }

    const requestTask = wx.request({
      url: reqConfig.url,
      method: reqConfig.method,
      data: reqConfig.data,
      header: reqConfig.header,
      timeout: reqConfig.timeout,

      success: (res) => {
        // 成功 (2xx)
        if (res.statusCode >= 200 && res.statusCode < 300) {
          let result = res.data
          // 应用响应拦截器
          for (const fn of interceptors.response) {
            try {
              result = fn(result) || result
            } catch (e) {
              console.error('[KeepSafe API] Response interceptor error:', e)
            }
          }
          resolve(result)
          return
        }

        // 401 — Token 过期
        if (res.statusCode === 401) {
          const app = getApp()
          app.clearAuth()
          wx.navigateTo({ url: '/pages/login/login' })
          const authErr = normalizeError({
            statusCode: 401,
            code: ERR_CODE.AUTH_EXPIRED,
            message: '登录已过期，请重新登录',
            data: res.data
          })
          // 错误拦截器
          for (const fn of interceptors.error) {
            try { fn(authErr) } catch (e) {}
          }
          reject(authErr)
          return
        }

        // 403 — 权限不足
        if (res.statusCode === 403) {
          const forbiddenErr = normalizeError({
            statusCode: 403,
            code: ERR_CODE.FORBIDDEN,
            message: res.data?.detail || '没有权限执行此操作',
            data: res.data
          })
          for (const fn of interceptors.error) {
            try { fn(forbiddenErr) } catch (e) {}
          }
          reject(forbiddenErr)
          return
        }

        // 可重试的错误 (502/503/504)
        const err = {
          statusCode: res.statusCode,
          code: res.statusCode >= 500 ? ERR_CODE.SERVER : res.statusCode,
          message: res.data?.detail || res.data?.message || `服务器错误 (${res.statusCode})`,
          data: res.data
        }

        if (RETRYABLE_STATUS.includes(res.statusCode) && retryCount < MAX_RETRIES) {
          console.warn(`[KeepSafe API] Retrying ${path} (${retryCount + 1}/${MAX_RETRIES})`)
          setTimeout(() => {
            request(method, path, data, options, retryCount + 1)
              .then(resolve)
              .catch(reject)
          }, Math.min(1000 * Math.pow(2, retryCount), 5000)) // 指数退避: 1s, 2s, max 5s
          return
        }

        const normalizedErr = normalizeError(err)
        for (const fn of interceptors.error) {
          try { fn(normalizedErr) } catch (e) {}
        }
        reject(normalizedErr)
      },

      fail: (failErr) => {
        // 请求被取消 (wx 主动 abort)
        if (failErr.errMsg && /abort/i.test(failErr.errMsg)) {
          const cancelErr = normalizeError({
            message: '请求已取消',
            code: ERR_CODE.CANCELLED,
            raw: failErr
          })
          for (const fn of interceptors.error) {
            try { fn(cancelErr) } catch (e) {}
          }
          reject(cancelErr)
          return
        }

        // 网络错误 — 重试
        if (retryCount < MAX_RETRIES) {
          console.warn(`[KeepSafe API] Network error, retrying ${path} (${retryCount + 1}/${MAX_RETRIES})`)
          setTimeout(() => {
            request(method, path, data, options, retryCount + 1)
              .then(resolve)
              .catch(reject)
          }, Math.min(1000 * Math.pow(2, retryCount), 5000))
          return
        }

        const netErr = normalizeError({
          statusCode: ERR_CODE.NETWORK,
          message: '网络连接失败，请检查网络设置',
          raw: failErr
        })
        for (const fn of interceptors.error) {
          try { fn(netErr) } catch (e) {}
        }
        reject(netErr)
      }
    })

    // 支持外部取消: options.signal 上挂载 abort
    if (options.signal) {
      if (options.signal.aborted) {
        requestTask.abort()
        reject(normalizeError({ message: '请求已取消', code: ERR_CODE.CANCELLED }))
        return
      }
      const originalOnAbort = options.signal.onabort
      options.signal.onabort = () => {
        requestTask.abort()
        if (originalOnAbort) originalOnAbort()
      }
    }
  })

  // 注册到 inflight 追踪
  if (!options.skipDedup) {
    inflightRequests.set(cacheKey, promise)
    // 请求完成/失败后清理
    const cleanup = () => { inflightRequests.delete(cacheKey) }
    promise.then(cleanup, cleanup)
  }

  return promise
}

/**
 * 创建一个可取消的信号对象
 * @returns {{ signal: { aborted: boolean, onabort: function|null }, abort: function }}
 */
api.createCancelSignal = () => {
  const signal = { aborted: false, onabort: null }
  return {
    signal,
    abort: () => {
      signal.aborted = true
      if (signal.onabort) signal.onabort()
    }
  }
}

/** ============================================================
 * HTTP 方法快捷封装
 * ============================================================ */

const api = {
  /** 标准错误码 */
  ERR_CODE,

  get: (path, params = {}, options = {}) => {
    // wx.request 对 GET 请求需将 params 拼接到 URL
    const qs = Object.keys(params)
      .filter(k => params[k] !== null && params[k] !== undefined && params[k] !== '')
      .map(k => `${encodeURIComponent(k)}=${encodeURIComponent(params[k])}`)
      .join('&')
    const fullPath = qs ? `${path}?${qs}` : path
    return request('GET', fullPath, null, options)
  },
  post: (path, data = {}, options = {}) => request('POST', path, data, options),
  put: (path, data = {}, options = {}) => request('PUT', path, data, options),
  patch: (path, data = {}, options = {}) => request('PATCH', path, data, options),
  delete: (path, data = {}, options = {}) => request('DELETE', path, data, options),

  /**
   * 安全请求: 自动 catch 错误并返回标准化错误对象，不抛异常
   * 适用于不希望 try-catch 包裹的调用场景
   * @returns {Promise<{ ok: boolean, data?: any, error?: object }>}
   */
  safeGet: async (path, params = {}, options = {}) => {
    try {
      const data = await api.get(path, params, options)
      return { ok: true, data }
    } catch (error) {
      return { ok: false, error: normalizeError(error) }
    }
  },
  safePost: async (path, data = {}, options = {}) => {
    try {
      const result = await api.post(path, data, options)
      return { ok: true, data: result }
    } catch (error) {
      return { ok: false, error: normalizeError(error) }
    }
  },
  safePut: async (path, data = {}, options = {}) => {
    try {
      const result = await api.put(path, data, options)
      return { ok: true, data: result }
    } catch (error) {
      return { ok: false, error: normalizeError(error) }
    }
  },

  /** ============================================================
   * 用户相关 API
   * ============================================================ */

  /**
   * 用户登录（邮箱+密码）
   * @param {string} email
   * @param {string} password
   * @returns {Promise<{access_token: string, token_type: string, user_id: string}>}
   */
  login: (email, password) => api.post('/users/login', { email, password }, { skipDedup: true }),

  /**
   * 用户注册
   * @param {string} email
   * @param {string} password
   * @param {string} [nickname]
   * @returns {Promise<{message: string}>}
   */
  register: (email, password, nickname) =>
    api.post('/users/register', { email, password, nickname }, { skipDedup: true }),

  /**
   * 获取当前用户信息
   * @returns {Promise<{user_id: string, email: string, nickname: string, avatar_url: string, phone: string, created_at: string}>}
   */
  getUserInfo: () => api.get('/users/profile'),

  /**
   * 更新用户信息
   * @param {object} data - { nickname?, avatar_url?, phone? }
   * @returns {Promise}
   */
  updateUserInfo: (data) => api.put('/users/profile', data),

  /**
   * 注册推送 token
   * @param {string} platform - "ios" | "android"
   * @param {string} token - FCM / APNs token
   * @returns {Promise<{message: string}>}
   */
  registerPushToken: (platform, token) =>
    api.post('/users/me/push-token', { platform, token }, { skipDedup: true }),

  /** ============================================================
   * 设备相关 API
   * ============================================================ */

  /**
   * 获取已绑定设备列表
   * @returns {Promise<Array<{device_id: string, nickname: string, bound_at: string, is_active: boolean, last_seen: string}>>}
   */
  getDeviceList: () => api.get('/users/me/devices'),

  /**
   * 获取设备最新位置
   * @param {string} deviceId
   * @returns {Promise<{device_id: string, ts: string, lat: number, lng: number, battery: number, ...}>}
   */
  getDeviceLocation: (deviceId) => api.get(`/devices/${deviceId}/location`),

  /**
   * 获取设备状态
   * @param {string} deviceId
   * @returns {Promise<{device_id: string, online: boolean, battery: number, charging: boolean, rssi: number, last_seen: string, lat: number, lng: number}>}
   */
  getDeviceStatus: (deviceId) => api.get(`/devices/${deviceId}/status`),

  /**
   * 获取设备位置历史
   * @param {string} deviceId
   * @param {string} [from] - ISO 起始时间
   * @param {string} [to] - ISO 结束时间
   * @param {number} [limit=100] - 返回条数
   * @returns {Promise<Array>}
   */
  getDeviceLocationHistory: (deviceId, from, to, limit = 100) =>
    api.get(`/devices/${deviceId}/history`, { from, to, limit }),

  /**
   * 获取 SOS 事件列表
   * @param {string} deviceId
   * @param {number} [limit=50] - 返回条数
   * @returns {Promise<Array>}
   */
  getSosEvents: (deviceId, limit = 50) =>
    api.get(`/devices/${deviceId}/sos/events`, { limit }),

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
  bindDevice: (deviceId, deviceToken, nickname) => {
    const app = getApp()
    const userId = app.globalData.userInfo?.user_id || ''
    return api.post('/devices/bind', {
      device_id: deviceId,
      token: deviceToken,
      user_id: userId,
      ...(nickname ? { nickname } : {})
    }, { skipDedup: true })
  },

  /**
   * 解绑设备 (后端通过 JWT 识别用户，无需传 userId)
   * @param {string} deviceId
   * @returns {Promise<{success: boolean, message: string}>}
   */
  unbindDevice: (deviceId) => api.delete(`/devices/${deviceId}/bind`, {}, { skipDedup: true }),

  /** ============================================================
   * 围栏相关 API
   * ============================================================ */

  /**
   * 获取设备围栏列表
   * @param {string} deviceId
   * @returns {Promise<Array>} - 直接返回围栏数组
   */
  getFenceList: (deviceId) =>
    api.get(`/devices/${deviceId}/fences`).then(result => {
      // 后端返回 { fences: [...], total: N }，解包为纯数组
      if (result && Array.isArray(result.fences)) {
        return result.fences
      }
      return []
    }).catch(err => {
      // 降级: 返回空数组，避免调用方崩溃
      console.error('[KeepSafe API] getFenceList failed:', err)
      return []
    }),

  /**
   * 获取单个围栏详情
   * @param {string} deviceId
   * @param {number} fenceId
   * @returns {Promise<{id: number, device_id: string, name: string, lat: number, lng: number, radius: number, enabled: boolean, ...}>}
   */
  getFenceById: (deviceId, fenceId) =>
    api.get(`/devices/${deviceId}/fences/${fenceId}`),

  /**
   * 创建围栏
   * @param {string} deviceId
   * @param {object} fenceData - { name, lat, lng, radius, enabled? }
   * @returns {Promise}
   */
  createFence: (deviceId, fenceData) =>
    api.post(`/devices/${deviceId}/fences`, fenceData, { skipDedup: true }),

  /**
   * 更新围栏
   * @param {string} deviceId
   * @param {number} fenceId
   * @param {object} fenceData - { name?, lat?, lng?, radius?, enabled? }
   * @returns {Promise}
   */
  updateFence: (deviceId, fenceId, fenceData) =>
    api.put(`/devices/${deviceId}/fences/${fenceId}`, fenceData, { skipDedup: true }),

  /**
   * 删除围栏
   * @param {string} deviceId
   * @param {number} fenceId
   * @returns {Promise<{message: string}>}
   */
  deleteFence: (deviceId, fenceId) =>
    api.delete(`/devices/${deviceId}/fences/${fenceId}`, {}, { skipDedup: true }),

  /** ============================================================
   * 告警相关 API
   * ============================================================ */

  /**
   * 获取告警列表 (分页 + 筛选)
   * @param {object} [params] - { page, page_size, alert_type, is_read }
   * @returns {Promise<{items: Array, total: number, page: number, page_size: number}>}
   */
  getAlertList: (params = {}) => api.get('/alerts/', params),

  /**
   * 标记单个告警为已读
   * @param {number|string} alertId
   * @returns {Promise}
   */
  markAlertRead: (alertId) => api.put(`/alerts/${alertId}/read`, {}, { skipDedup: true }),

  /**
   * 标记所有告警为已读
   * @returns {Promise<{message: string}>}
   */
  markAllAlertsRead: () => api.put('/alerts/read-all', {}, { skipDedup: true }),

  /** ============================================================
   * 分享相关 API
   * ============================================================ */

  /**
   * 获取设备位置分享链接
   * TODO: 后端暂未实现，需后续添加 /devices/{deviceId}/share-link 端点
   * @param {string} deviceId
   * @returns {Promise<{share_url: string}>}
   */
  getShareLink: (deviceId) => {
    return new Promise((resolve, reject) => {
      wx.showToast({ title: '分享功能开发中', icon: 'none' })
      reject({ code: ERR_CODE.SERVER, message: '分享功能暂未开放' })
    })
    // 后端端点就绪后启用:
    // api.get(`/devices/${deviceId}/share-link`)
  },

  /**
   * 分享设备给其他用户
   * @param {string} deviceId
   * @param {string} sharedWithEmail
   * @param {string} [permissions='view'] - 'view' | 'control'
   * @returns {Promise}
   */
  shareDevice: (deviceId, sharedWithEmail, permissions = 'view') =>
    api.post(`/devices/${deviceId}/share`, {
      shared_with_email: sharedWithEmail,
      permissions
    }, { skipDedup: true }),

  /**
   * 获取设备分享列表
   * @param {string} deviceId
   * @returns {Promise<{shares: Array, total: number}>}
   */
  getShareList: (deviceId) =>
    api.get(`/devices/${deviceId}/shares`),

  /**
   * 撤销设备分享
   * @param {string} deviceId
   * @param {number} shareId
   * @returns {Promise<{message: string}>}
   */
  revokeShare: (deviceId, shareId) =>
    api.delete(`/devices/${deviceId}/share/${shareId}`, {}, { skipDedup: true }),

  /**
   * 获取分享给我的设备列表
   * @returns {Promise<{devices: Array, total: number}>}
   */
  getSharedWithMe: () =>
    api.get('/devices/shared-with-me'),
}

module.exports = api
