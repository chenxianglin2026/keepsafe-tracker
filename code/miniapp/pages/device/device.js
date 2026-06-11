/**
 * 设备详情页面 - 展示设备状态、位置、SOS 记录
 */
const api = require('../../utils/api')
const auth = require('../../utils/auth')
const mapUtil = require('../../utils/map')

Page({
  data: {
    deviceId: '',
    deviceInfo: {},
    deviceStatus: {},
    mapCenter: { latitude: 39.908860, longitude: 116.397390 },
    mapScale: 15,
    markers: [],
    sosEvents: [],
    loading: true,
    lastSeenText: '--',
    batteryColor: '#6C6C80'
  },

  onLoad(options) {
    const deviceId = options.device_id || options.id || ''
    if (!deviceId) {
      wx.showToast({ title: '缺少设备 ID', icon: 'none' })
      setTimeout(() => wx.navigateBack(), 1500)
      return
    }

    this.setData({ deviceId })
    this.loadDeviceInfo()
    this.loadDeviceStatus()
    this.loadSosEvents()
  },

  /**
   * 加载设备基本信息 (名称等)
   */
  loadDeviceInfo() {
    auth.checkLogin(false).then((loggedIn) => {
      if (!loggedIn) return

      api.getDeviceList()
        .then((devices) => {
          const list = Array.isArray(devices) ? devices : []
          const device = list.find(d => d.device_id === this.data.deviceId)
          if (device) {
            this.setData({ deviceInfo: device, loading: false })
          } else {
            // 无法从列表找到，直接获取状态
            this.setData({ loading: false })
          }
        })
        .catch(() => {
          this.setData({ loading: false })
        })
    })
  },

  /**
   * 加载设备状态 (在线、电量、信号、位置)
   */
  loadDeviceStatus() {
    api.getDeviceStatus(this.data.deviceId)
      .then((status) => {
        const lat = status.lat || status.latitude || 39.908860
        const lng = status.lng || status.longitude || 116.397390

        this.setData({
          deviceStatus: status,
          lastSeenText: mapUtil.formatTime(status.last_seen),
          batteryColor: mapUtil.getBatteryColor(status.battery),
          mapCenter: { latitude: lat, longitude: lng },
          markers: [{
            id: 0,
            latitude: lat,
            longitude: lng,
            iconPath: status.online
              ? '../../images/marker-online.png'
              : '../../images/marker-offline.png',
            width: 44,
            height: 52,
            callout: {
              content: '当前位置',
              fontSize: 12,
              borderRadius: 8,
              bgColor: '#1A1A2E',
              color: '#FFFFFF',
              padding: 8,
              display: 'ALWAYS',
              textAlign: 'center'
            }
          }]
        })
      })
      .catch((err) => {
        console.error('[KeepSafe] Load device status error:', err)
      })
  },

  /**
   * 加载 SOS 事件列表
   */
  loadSosEvents() {
    api.getSosEvents(this.data.deviceId, 20)
      .then((events) => {
        this.setData({ sosEvents: Array.isArray(events) ? events : [] })
      })
      .catch(() => {})
  },

  /**
   * 刷新位置
   */
  onRefreshLocation() {
    wx.showLoading({ title: '刷新中...' })
    this.loadDeviceStatus()
    wx.hideLoading()
  },

  /**
   * 导航到设备位置
   */
  onNavigate() {
    const { mapCenter } = this.data
    wx.openLocation({
      latitude: mapCenter.latitude,
      longitude: mapCenter.longitude,
      name: this.data.deviceInfo.nickname || '设备位置',
      scale: 16
    })
  },

  /**
   * 设置围栏 - 跳转围栏管理页
   */
  onSetFence() {
    wx.navigateTo({
      url: `/pages/fence/fence?device_id=${this.data.deviceId}&nickname=${encodeURIComponent(this.data.deviceInfo.nickname || '')}`
    })
  },

  /**
   * 解绑设备
   */
  onUnbind() {
    wx.showModal({
      title: '确认解绑',
      content: '解绑后此设备将不再出现在您的设备列表中。确定要继续吗？',
      confirmColor: '#FF4757',
      success: (res) => {
        if (res.confirm) {
          wx.showLoading({ title: '解绑中...', mask: true })
          api.unbindDevice(this.data.deviceId)
            .then(() => {
              wx.hideLoading()
              wx.showToast({ title: '解绑成功', icon: 'success' })
              setTimeout(() => {
                wx.navigateBack()
              }, 1500)
            })
            .catch((err) => {
              wx.hideLoading()
              wx.showToast({
                title: err.message || '解绑失败',
                icon: 'none'
              })
            })
        }
      }
    })
  },

  /**
   * 格式化时间
   */
  formatTime(time) {
    return mapUtil.formatTime(time)
  },

  /**
   * 分享
   */
  onShareAppMessage() {
    const name = this.data.deviceInfo.nickname || '设备'
    return {
      title: `${name} 的位置 - KeepSafe`,
      path: `/pages/device/device?device_id=${this.data.deviceId}`,
      imageUrl: '../../images/share-banner.png'
    }
  }
})
