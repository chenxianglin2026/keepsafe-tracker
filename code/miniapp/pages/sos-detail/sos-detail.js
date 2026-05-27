/**
 * SOS 告警详情页面
 */
const api = require('../../utils/api')
const mapUtil = require('../../utils/map')

Page({
  data: {
    // 从上一页传入
    deviceId: '',
    deviceName: '未知设备',
    alertId: '',
    latitude: 39.908860,
    longitude: 116.397390,
    timestamp: '',

    // 地图
    markers: [],
    scale: 16,

    // 显示
    timeText: '',
    battery: 0,
    batteryColor: '#6C6C80',
    address: '',

    // 状态
    acknowledged: false
  },

  onLoad(options) {
    const { device_id, device_name, alert_id, latitude, longitude, timestamp } = options

    const lat = parseFloat(latitude) || 39.908860
    const lng = parseFloat(longitude) || 116.397390

    this.setData({
      deviceId: device_id || '',
      deviceName: decodeURIComponent(device_name || '未知设备'),
      alertId: alert_id || '',
      latitude: lat,
      longitude: lng,
      timestamp: timestamp || '',
      timeText: mapUtil.formatTime(timestamp),
      markers: [{
        id: 0,
        latitude: lat,
        longitude: lng,
        iconPath: '/images/marker-online.png',
        width: 44,
        height: 52,
        callout: {
          content: 'SOS 位置',
          fontSize: 13,
          borderRadius: 8,
          bgColor: '#FF4757',
          color: '#FFFFFF',
          padding: 10,
          display: 'ALWAYS',
          textAlign: 'center'
        },
        label: {
          content: '🆘 SOS',
          fontSize: 14,
          color: '#FF4757',
          x: 0,
          y: -12
        }
      }]
    })

    // 获取设备最新状态
    this.loadDeviceStatus()

    // 标记告警已读
    if (alert_id) {
      api.markAlertRead(alert_id).catch(() => {})
    }
  },

  /**
   * 加载设备状态（电量、最新位置）
   */
  loadDeviceStatus() {
    if (!this.data.deviceId) return

    api.getDeviceStatus(this.data.deviceId)
      .then((status) => {
        if (status) {
          this.setData({
            battery: status.battery != null ? status.battery : 0,
            batteryColor: mapUtil.getBatteryColor(status.battery)
          })
        }
      })
      .catch(() => {})

    // 地址反查（需要腾讯地图逆地理编码 API，此处用坐标显示）
  },

  /**
   * 联系设备使用者（微信语音通话 - 需后续版本集成）
   */
  onCallDevice() {
    wx.showModal({
      title: '联系使用者',
      content: `设备 "${this.data.deviceName}" 发出了 SOS 求助。\n\n请尝试用电话联系该使用者。\n\n如无法取得联系，建议立即前往设备位置查看。`,
      confirmText: '我知道了',
      showCancel: false
    })
  },

  /**
   * 打开导航
   */
  onNavigate() {
    const { latitude, longitude, deviceName } = this.data
    wx.openLocation({
      latitude,
      longitude,
      name: `SOS - ${deviceName}`,
      scale: 16
    })
  },

  /**
   * 确认收到告警
   */
  onAcknowledge() {
    this.setData({ acknowledged: true })
    wx.showToast({ title: '已确认收到', icon: 'success' })

    // 通知后端已确认
    if (this.data.alertId) {
      api.markAlertRead(this.data.alertId).catch(() => {})
    }
  },

  /**
   * 分享 SOS 位置给家人
   */
  onShareAppMessage() {
    return {
      title: `🆘 SOS 求助 - ${this.data.deviceName}`,
      path: `/pages/sos-detail/sos-detail?device_id=${this.data.deviceId}&device_name=${encodeURIComponent(this.data.deviceName)}&latitude=${this.data.latitude}&longitude=${this.data.longitude}`,
      imageUrl: '/images/share-banner.png'
    }
  }
})
