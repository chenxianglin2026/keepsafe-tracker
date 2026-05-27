/**
 * 腾讯地图工具函数模块
 * 提供地图相关辅助功能
 */

/**
 * 计算两点之间的距离（米）—— Haversine 公式
 * @param {number} lat1 - 起点纬度
 * @param {number} lng1 - 起点经度
 * @param {number} lat2 - 终点纬度
 * @param {number} lng2 - 终点经度
 * @returns {number} 距离（米）
 */
function calcDistance(lat1, lng1, lat2, lng2) {
  const EARTH_RADIUS = 6371000
  const toRad = (deg) => (deg * Math.PI) / 180

  const dLat = toRad(lat2 - lat1)
  const dLng = toRad(lng2 - lng1)

  const a =
    Math.sin(dLat / 2) * Math.sin(dLat / 2) +
    Math.cos(toRad(lat1)) *
      Math.cos(toRad(lat2)) *
      Math.sin(dLng / 2) *
      Math.sin(dLng / 2)

  const c = 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a))
  return Math.round(EARTH_RADIUS * c)
}

/**
 * 格式化距离显示
 * @param {number} meters - 距离（米）
 * @returns {string} 格式化后的距离字符串
 */
function formatDistance(meters) {
  if (meters < 1000) {
    return `${meters}m`
  }
  return `${(meters / 1000).toFixed(1)}km`
}

/**
 * 格式化时间戳
 * @param {string|number} timestamp - ISO 字符串或时间戳
 * @returns {string} 格式化时间
 */
function formatTime(timestamp) {
  if (!timestamp) return '未知'
  const date = new Date(timestamp)
  const now = new Date()
  const diff = now - date

  // 1 分钟内
  if (diff < 60000) {
    return '刚刚'
  }
  // 1 小时内
  if (diff < 3600000) {
    return `${Math.floor(diff / 60000)}分钟前`
  }
  // 今天内
  if (date.toDateString() === now.toDateString()) {
    const h = date.getHours().toString().padStart(2, '0')
    const m = date.getMinutes().toString().padStart(2, '0')
    return `今天 ${h}:${m}`
  }
  // 昨天
  const yesterday = new Date(now)
  yesterday.setDate(yesterday.getDate() - 1)
  if (date.toDateString() === yesterday.toDateString()) {
    const h = date.getHours().toString().padStart(2, '0')
    const m = date.getMinutes().toString().padStart(2, '0')
    return `昨天 ${h}:${m}`
  }
  // 更早
  const month = (date.getMonth() + 1).toString().padStart(2, '0')
  const day = date.getDate().toString().padStart(2, '0')
  const h = date.getHours().toString().padStart(2, '0')
  const m = date.getMinutes().toString().padStart(2, '0')
  return `${month}/${day} ${h}:${m}`
}

/**
 * 判断设备是否在线
 * @param {string} lastReportTime - 最后上报时间
 * @param {number} timeoutMinutes - 超时阈值（分钟）
 * @returns {boolean}
 */
function isOnline(lastReportTime, timeoutMinutes = 15) {
  if (!lastReportTime) return false
  const now = Date.now()
  const last = new Date(lastReportTime).getTime()
  return now - last < timeoutMinutes * 60 * 1000
}

/**
 * 获取设备状态文本
 * @param {string} lastReportTime - 最后上报时间
 * @param {number} battery - 电量百分比
 * @returns {{ status: string, className: string }}
 */
function getDeviceStatus(lastReportTime, battery) {
  const online = isOnline(lastReportTime)
  if (!online) {
    return { status: '离线', className: 'tag-danger' }
  }
  if (battery != null && battery <= 20) {
    return { status: '低电量', className: 'tag-warning' }
  }
  return { status: '在线', className: 'tag-success' }
}

/**
 * 获取电池图标颜色
 * @param {number} battery - 电量百分比
 * @returns {string} 颜色值
 */
function getBatteryColor(battery) {
  if (battery == null) return '#6C6C80'
  if (battery <= 20) return '#FF4757'
  if (battery <= 50) return '#FFA502'
  return '#2ED573'
}

module.exports = {
  calcDistance,
  formatDistance,
  formatTime,
  isOnline,
  getDeviceStatus,
  getBatteryColor
}
