/**
 * 设备状态卡片组件
 */
const mapUtil = require('../../utils/map')

Component({
  properties: {
    device: {
      type: Object,
      value: {},
      observer: 'updateStatus'
    },
    userLocation: {
      type: Object,
      value: null,
      observer: 'updateDistance'
    }
  },

  data: {
    statusText: '--',
    statusClass: '',
    batteryPercent: 0,
    batteryColor: '#6C6C80',
    lastTime: '--',
    distance: null
  },

  methods: {
    /**
     * 更新设备状态显示
     */
    updateStatus() {
      const device = this.data.device
      if (!device) return

      const status = device.is_active ? '在线' : '离线'
      const className = device.is_active ? 'online' : 'offline'
      const lastTime = mapUtil.formatTime(device.last_seen)
      const batteryPercent = device.battery != null ? Math.max(0, Math.min(100, device.battery)) : 0
      const batteryColor = mapUtil.getBatteryColor(device.battery)

      this.setData({
        statusText: status,
        statusClass: className,
        lastTime,
        batteryPercent,
        batteryColor
      })

      this.updateDistance()
    },

    /**
     * 更新距离显示
     */
    updateDistance() {
      const device = this.data.device
      const userLoc = this.data.userLocation
      if (!device || !userLoc) {
        return
      }
      const lat = device.lat || device.latitude
      const lng = device.lng || device.longitude
      if (!lat || !lng) return
      const dist = mapUtil.calcDistance(
        userLoc.latitude, userLoc.longitude,
        lat, lng
      )
      this.setData({
        distance: mapUtil.formatDistance(dist)
      })
    },

    onTap() {
      this.triggerEvent('tap', { device: this.data.device })
    },

    onLocate(e) {
      if (e) e.stopPropagation && e.stopPropagation()
      this.triggerEvent('locate', { device: this.data.device })
    },

    onFence(e) {
      if (e) e.stopPropagation && e.stopPropagation()
      this.triggerEvent('fence', { device: this.data.device })
    },

    onShare(e) {
      if (e) e.stopPropagation && e.stopPropagation()
      this.triggerEvent('share', { device: this.data.device })
    }
  },

  lifetimes: {
    attached() {
      this.updateStatus()
    }
  }
})
