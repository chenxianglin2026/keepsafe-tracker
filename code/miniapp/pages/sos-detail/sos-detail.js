/**
 * SOS 告警详情页面 (增强版)
 * 功能：地图定位、逆地理编码、实时追踪、紧急联系
 */
const api = require('../../utils/api')
const mapUtil = require('../../utils/map')

/** 腾讯地图 WebService API Key (用于逆地理编码) */
const MAP_KEY = 'YOUR_TENCENT_MAP_KEY'

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
    acknowledged: false,
    tracking: false,      // 是否正在追踪
    sosEventsCount: 0,    // SOS 历史事件数量

    // 追踪定时器
    _trackTimer: null
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

    // 逆地理编码获取地址
    this.reverseGeocode(lat, lng)

    // 获取设备最新状态
    this.loadDeviceStatus()

    // 获取 SOS 历史事件数量
    this.loadSosEventCount()

    // 标记告警已读
    if (alert_id) {
      api.markAlertRead(alert_id).catch(() => {})
    }
  },

  onUnload() {
    // 停止追踪
    this.stopTracking()
  },

  // ═══════════════════════════════════════════════════
  //  地址反查
  // ═══════════════════════════════════════════════════

  /**
   * 腾讯地图逆地理编码 (坐标 -> 地址)
   */
  reverseGeocode(lat, lng) {
    wx.request({
      url: 'https://apis.map.qq.com/ws/geocoder/v1/',
      data: {
        location: `${lat},${lng}`,
        key: MAP_KEY,
        get_poi: 1
      },
      success: (res) => {
        if (res.statusCode === 200 && res.data && res.data.status === 0) {
          const addr = res.data.result.address || res.data.result.formatted_addresses?.recommend || ''
          if (addr) {
            this.setData({ address: addr })
          } else {
            this.setData({ address: `${lat.toFixed(6)}, ${lng.toFixed(6)}` })
          }
        } else {
          this.fallbackAddress(lat, lng)
        }
      },
      fail: () => {
        this.fallbackAddress(lat, lng)
      }
    })
  },

  /**
   * 降级方案：显示坐标
   */
  fallbackAddress(lat, lng) {
    this.setData({
      address: `${lat.toFixed(6)}, ${lng.toFixed(6)}`
    })
  },

  // ═══════════════════════════════════════════════════
  //  设备状态 + SOS 事件
  // ═══════════════════════════════════════════════════

  /**
   * 加载设备状态（电量、最新位置）
   */
  loadDeviceStatus() {
    if (!this.data.deviceId) return

    api.getDeviceStatus(this.data.deviceId)
      .then((status) => {
        if (status) {
          const updates = {
            battery: status.battery != null ? status.battery : 0,
            batteryColor: mapUtil.getBatteryColor(status.battery)
          }

          // 如果设备有新位置，更新地图
          if (status.lat && status.lng) {
            updates.latitude = status.lat
            updates.longitude = status.lng
            updates.markers = [{
              id: 0,
              latitude: status.lat,
              longitude: status.lng,
              iconPath: '/images/marker-online.png',
              width: 44,
              height: 52,
              callout: {
                content: 'SOS 追踪位置',
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
            // 反查新地址
            this.reverseGeocode(status.lat, status.lng)
          }

          this.setData(updates)
        }
      })
      .catch(() => {})
  },

  /**
   * 获取 SOS 历史事件数量
   */
  loadSosEventCount() {
    if (!this.data.deviceId) return

    api.getSosEvents(this.data.deviceId, 50)
      .then((events) => {
        this.setData({ sosEventsCount: Array.isArray(events) ? events.length : 0 })
      })
      .catch(() => {})
  },

  // ═══════════════════════════════════════════════════
  //  实时追踪
  // ═══════════════════════════════════════════════════

  /**
   * 开始追踪设备位置（每 10 秒刷新一次）
   */
  onStartTracking() {
    if (this.data.tracking) return

    this.setData({ tracking: true })
    wx.showToast({ title: '开始实时追踪位置', icon: 'none', duration: 1500 })

    // 立即获取一次
    this.loadDeviceStatus()

    // 定时刷新
    const timer = setInterval(() => {
      this.loadDeviceStatus()
    }, 10000)

    this.setData({ _trackTimer: timer })
    // 存储到实例变量避免 setData 导致渲染
    this._trackTimer = timer
  },

  /**
   * 停止追踪
   */
  stopTracking() {
    if (this._trackTimer) {
      clearInterval(this._trackTimer)
      this._trackTimer = null
    }
    const dataTimer = this.data._trackTimer
    if (dataTimer) {
      clearInterval(dataTimer)
    }
    this.setData({ tracking: false })
  },

  onStopTracking() {
    this.stopTracking()
    wx.showToast({ title: '已停止追踪', icon: 'none' })
  },

  // ═══════════════════════════════════════════════════
  //  操作按钮
  // ═══════════════════════════════════════════════════

  /**
   * 联系设备使用者
   */
  onCallDevice() {
    wx.showActionSheet({
      itemList: ['拨打紧急联系人', '拨打 110 报警', '拨打 120 急救'],
      success: (res) => {
        switch (res.tapIndex) {
          case 1:
            wx.makePhoneCall({ phoneNumber: '110' })
            break
          case 2:
            wx.makePhoneCall({ phoneNumber: '120' })
            break
          default:
            // 紧急联系人 — 暂未配置，提示用户
            wx.showModal({
              title: '联系使用者',
              content: `设备 "${this.data.deviceName}" 发出了 SOS 求助。\n\n请尝试用电话联系该使用者。\n\n如无法取得联系，建议立即前往设备位置查看。`,
              confirmText: '我知道了',
              showCancel: false
            })
        }
      }
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
  },

  // ═══════════════════════════════════════════════════
  //  地图事件
  // ═══════════════════════════════════════════════════

  onMapMarkerTap(e) {
    const markerId = e.detail.markerId
    if (markerId === 0 && this.data.markers[0]) {
      // 点击 SOS 标记，打开导航
      this.onNavigate()
    }
  },

  // ═══════════════════════════════════════════════════
  //  紧急号码快捷拨号
  // ═══════════════════════════════════════════════════

  onCallPolice() {
    wx.showModal({
      title: '拨打 110 报警',
      content: '确认拨打 110 报警电话？',
      confirmText: '拨打',
      cancelText: '取消',
      success: (res) => {
        if (res.confirm) {
          wx.makePhoneCall({ phoneNumber: '110' })
        }
      }
    })
  },

  onCallAmbulance() {
    wx.showModal({
      title: '拨打 120 急救',
      content: '确认拨打 120 急救电话？',
      confirmText: '拨打',
      cancelText: '取消',
      success: (res) => {
        if (res.confirm) {
          wx.makePhoneCall({ phoneNumber: '120' })
        }
      }
    })
  },

  onCallFire() {
    wx.showModal({
      title: '拨打 119 火警',
      content: '确认拨打 119 火警电话？',
      confirmText: '拨打',
      cancelText: '取消',
      success: (res) => {
        if (res.confirm) {
          wx.makePhoneCall({ phoneNumber: '119' })
        }
      }
    })
  }
})
