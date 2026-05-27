const app = getApp()

Page({
  data: {
    latitude: 39.9042,
    longitude: 116.4074,
    scale: 14,
    markers: [],
    deviceList: [],
    deviceName: '👴 爷爷',
    locationText: '加载中...',
    lastUpdate: '刚刚',
    battery: 82
  },

  onLoad() {
    this.loadDeviceList()
    this.startLocationUpdate()
  },

  onShow() {
    this.loadDeviceList()
  },

  loadDeviceList() {
    // 模拟数据，后续接真实API
    const mockList = [
      { id: 1, name: '👴 爷爷', online: true, lat: 39.9042, lng: 116.4074 },
      { id: 2, name: '👶 小宝', online: true, lat: 39.9060, lng: 116.4100 }
    ]
    this.setData({
      deviceList: mockList,
      markers: mockList.map(d => ({
        id: d.id,
        latitude: d.lat,
        longitude: d.lng,
        iconPath: '/images/marker.png',
        width: 32,
        height: 40,
        label: { content: d.name, fontSize: 14 }
      })),
      latitude: mockList[0].lat,
      longitude: mockList[0].lng,
      locationText: '菜市场附近'
    })
  },

  startLocationUpdate() {
    // 定时刷新（后续用WebSocket/MQTT实时推送）
    setInterval(() => {
      this.setData({ lastUpdate: '刚刚' })
    }, 30000)
  },

  onRefresh() {
    wx.showLoading({ title: '定位中...' })
    this.loadDeviceList()
    setTimeout(() => wx.hideLoading(), 1000)
  },

  onFence() {
    wx.navigateTo({ url: '/pages/fence/fence' })
  },

  onDeviceTap(e) {
    const id = e.currentTarget.dataset.id
    wx.navigateTo({ url: `/pages/device/device?id=${id}` })
  },

  onAddDevice() {
    wx.navigateTo({ url: '/pages/bind/bind' })
  }
})
