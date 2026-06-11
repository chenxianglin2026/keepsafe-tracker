/**
 * 首页 - 地图页面逻辑
 * 核心功能：地图展示、设备位置标记、定位、围栏设置
 */
const api = require('../../utils/api')
const auth = require('../../utils/auth')
const mapUtil = require('../../utils/map')

Page({
  data: {
    // 地图
    mapCenter: {
      latitude: 39.908860,
      longitude: 116.397390
    },
    mapScale: 15,
    markers: [],
    circles: [],

    // 设备
    deviceList: [],
    deviceCount: 0,

    // 用户
    userLocation: null,

    // 告警
    unreadAlertCount: 0,

    // 状态
    loading: true,
    lastRefreshTime: '',
    refreshTimer: null,

    // 围栏弹窗
    fenceVisible: false,
    fenceDeviceId: '',
    fenceEditData: null,

    // 绑定弹窗
    bindVisible: false,
    bindDeviceId: '',
    bindDeviceToken: '',
    bindDeviceName: ''
  },

  onLoad() {
    this.initLocation()
    this.loadData()
    this.startPolling()
  },

  onShow() {
    // 检查是否有新告警
    this.fetchUnreadAlertCount()
    // 刷新设备位置
    this.refreshDevices()
  },

  onUnload() {
    // 清理定时器
    if (this.data.refreshTimer) {
      clearInterval(this.data.refreshTimer)
    }
  },

  /**
   * 初始化用户位置
   */
  initLocation() {
    wx.getLocation({
      type: 'gcj02',
      success: (res) => {
        this.setData({
          userLocation: {
            latitude: res.latitude,
            longitude: res.longitude
          },
          mapCenter: {
            latitude: res.latitude,
            longitude: res.longitude
          }
        })
      },
      fail: () => {
        // 授权失败，使用默认位置（北京）
        wx.showToast({
          title: '请在设置中开启位置权限',
          icon: 'none',
          duration: 3000
        })
      }
    })
  },

  /**
   * 加载初始数据
   */
  loadData() {
    auth.checkLogin().then((loggedIn) => {
      if (loggedIn) {
        this.fetchDevices()
      } else {
        this.setData({ loading: false })
      }
    })
  },

  /**
   * 获取设备列表
   */
  fetchDevices() {
    return api.getDeviceList()
      .then((devices) => {
        const list = Array.isArray(devices) ? devices : []
        this.setData({
          deviceList: list,
          deviceCount: list.length,
          loading: false,
          lastRefreshTime: mapUtil.formatTime(new Date().toISOString())
        })
        this.updateMarkers()
      })
      .catch((err) => {
        console.error('[KeepSafe] Fetch devices error:', err)
        this.setData({ loading: false })
        wx.showToast({
          title: err.message || '获取设备列表失败',
          icon: 'none'
        })
      })
  },

  /**
   * 刷新设备位置（不显示加载状态）
   */
  refreshDevices() {
    if (!auth.getToken()) return
    api.getDeviceList()
      .then((devices) => {
        const list = Array.isArray(devices) ? devices : []
        this.setData({
          deviceList: list,
          deviceCount: list.length,
          lastRefreshTime: mapUtil.formatTime(new Date().toISOString())
        })
        this.updateMarkers()
      })
      .catch(() => {
        // 静默失败
      })
  },

  /**
   * 更新地图标记
   */
  updateMarkers() {
    const markers = []
    const circles = []

    this.data.deviceList.forEach((device, index) => {
      // Skip devices without location data
      if (!device.latitude && !device.lat) return

      const lat = device.latitude || device.lat
      const lng = device.longitude || device.lng
      const name = device.nickname || device.name || '设备'
      const isActive = device.is_active !== false

      // 设备标记
      markers.push({
        id: index,
        latitude: lat,
        longitude: lng,
        title: name,
        iconPath: isActive
          ? '../../images/marker-online.png'
          : '../../images/marker-offline.png',
        width: 44,
        height: 52,
        callout: {
          content: `${name} - ${isActive ? '在线' : '离线'}`,
          fontSize: 12,
          borderRadius: 8,
          borderWidth: 0,
          bgColor: '#1A1A2E',
          padding: 8,
          display: 'ALWAYS',
          textAlign: 'center'
        },
        label: {
          content: name,
          fontSize: 11,
          color: '#FFFFFF',
          x: 0,
          y: -8
        }
      })
    })

    this.setData({ markers, circles })
  },

  /**
   * 开始轮询
   */
  startPolling() {
    // 每 30 秒刷新一次
    const timer = setInterval(() => {
      this.refreshDevices()
      this.fetchUnreadAlertCount()
    }, 30000)
    this.setData({ refreshTimer: timer })
  },

  /**
   * 获取未读告警数
   */
  fetchUnreadAlertCount() {
    return api.getAlertList({ page_size: 1 })
      .then((result) => {
        if (result && result.total !== undefined) {
          this.setData({ unreadAlertCount: result.total })
        }
      })
      .catch(() => {})
  },

  // ============================================================
  // 事件处理
  // ============================================================

  /**
   * 手动刷新
   */
  onRefresh() {
    wx.showLoading({ title: '刷新中...', mask: true })
    Promise.all([
      this.fetchDevices(),
      this.fetchUnreadAlertCount()
    ]).finally(() => {
      wx.hideLoading()
    })
  },

  /**
   * 点击地图标记
   */
  onMarkerTap(e) {
    const markerId = e.detail.markerId
    const device = this.data.deviceList[markerId]
    if (device) {
      wx.showActionSheet({
        itemList: ['查看位置', '设置围栏', '分享位置'],
        success: (res) => {
          switch (res.tapIndex) {
            case 0:
              this.onLocateDevice({ detail: { device } })
              break
            case 1:
              this.onFenceDevice({ detail: { device } })
              break
            case 2:
              this.onShareDevice({ detail: { device } })
              break
          }
        }
      })
    }
  },

  /**
   * 地图区域变化
   */
  onRegionChange(e) {
    if (e.type === 'end') {
      const center = e.detail.centerLocation
      this.setData({
        mapCenter: {
          latitude: center.latitude,
          longitude: center.longitude
        }
      })
    }
  },

  onMapTap() {
    // 地图点击可收起设备卡片
  },

  /**
   * 定位设备 - 调整地图到设备位置
   */
  onLocateDevice(e) {
    const device = e.detail.device
    const lat = device.latitude || device.lat
    const lng = device.longitude || device.lng
    if (device && lat && lng) {
      this.setData({
        mapCenter: {
          latitude: lat,
          longitude: lng
        },
        mapScale: 16
      })
      wx.showToast({
        title: `定位到 ${device.nickname || device.name || '设备'}`,
        icon: 'none',
        duration: 1500
      })
    }
  },

  /**
   * 设置围栏
   */
  onFenceDevice(e) {
    const device = e.detail.device

    // 先尝试获取已有围栏
    api.getFenceList(device.device_id)
      .then((fences) => {
        const fenceList = Array.isArray(fences) ? fences : []
        if (fenceList.length > 0) {
          // 编辑第一个围栏
          this.setData({
            fenceVisible: true,
            fenceDeviceId: device.device_id,
            fenceEditData: fenceList[0]
          })
        } else {
          // 新建围栏，使用设备当前位置作为默认
          this.setData({
            fenceVisible: true,
            fenceDeviceId: device.device_id,
            fenceEditData: {
              lat: device.latitude || device.lat,
              lng: device.longitude || device.lng,
              radius: 500,
              name: `${device.nickname || device.name || '设备'} 围栏`,
              enabled: true
            }
          })
        }
      })
      .catch(() => {
        // 获取围栏失败，新建
        this.setData({
          fenceVisible: true,
          fenceDeviceId: device.device_id,
          fenceEditData: null
        })
      })
  },

  /**
   * 分享设备位置
   */
  onShareDevice(e) {
    const device = e.detail.device
    wx.showLoading({ title: '生成分享链接...' })

    api.getShareLink(device.device_id)
      .then((result) => {
        wx.hideLoading()
        const name = device.nickname || device.name || '设备'
        wx.showSharePanel({
          title: `查看 ${name} 的位置`,
          path: `/pages/share/index?device_id=${device.device_id}`,
          imageUrl: '../../images/share-banner.png'
        })
      })
      .catch((err) => {
        wx.hideLoading()
        wx.showToast({
          title: err.message || '生成分享链接失败',
          icon: 'none'
        })
      })
  },

  /**
   * 点击设备卡片
   */
  onDeviceTap(e) {
    const device = e.detail.device
    this.onLocateDevice({ detail: { device } })
  },

  /**
   * 居中到我的位置
   */
  onCenterMap() {
    if (this.data.userLocation) {
      this.setData({
        mapCenter: {
          latitude: this.data.userLocation.latitude,
          longitude: this.data.userLocation.longitude
        },
        mapScale: 15
      })
    } else {
      wx.showToast({
        title: '无法获取您的位置',
        icon: 'none'
      })
    }
  },

  /**
   * 跳转到告警页面
   */
  onShowAlerts() {
    wx.switchTab({ url: '/pages/alerts/alert' })
  },

  // ============================================================
  // 围栏弹窗事件
  // ============================================================

  onFenceClose() {
    this.setData({
      fenceVisible: false,
      fenceEditData: null
    })
  },

  onFenceSaved(e) {
    // 围栏保存后刷新设备列表以更新围栏标记
    this.refreshDevices()
  },

  onFenceDeleted(e) {
    // 围栏删除后刷新
    this.refreshDevices()
  },

  // ============================================================
  // 绑定设备弹窗事件
  // ============================================================

  onBindDevice() {
    this.setData({
      bindVisible: true,
      bindDeviceId: '',
      bindDeviceToken: '',
      bindDeviceName: ''
    })
  },

  onBindClose() {
    this.setData({ bindVisible: false })
  },

  onBindInput(e) {
    this.setData({ bindDeviceId: e.detail.value })
  },

  onBindTokenInput(e) {
    this.setData({ bindDeviceToken: e.detail.value })
  },

  onBindNameInput(e) {
    this.setData({ bindDeviceName: e.detail.value })
  },

  onBindConfirm() {
    const { bindDeviceId, bindDeviceToken, bindDeviceName } = this.data
    if (!bindDeviceId.trim()) {
      wx.showToast({ title: '请输入设备码', icon: 'none' })
      return
    }
    if (!bindDeviceToken.trim()) {
      wx.showToast({ title: '请输入设备密钥', icon: 'none' })
      return
    }

    wx.showLoading({ title: '绑定中...', mask: true })

    api.bindDevice(bindDeviceId.trim(), bindDeviceToken.trim(), bindDeviceName.trim() || undefined)
      .then(() => {
        wx.hideLoading()
        wx.showToast({ title: '绑定成功', icon: 'success' })
        this.setData({ bindVisible: false })
        this.fetchDevices()
      })
      .catch((err) => {
        wx.hideLoading()
        wx.showToast({
          title: err.message || '绑定失败，请检查设备码',
          icon: 'none'
        })
      })
  },

  preventMove() {
    // 阻止弹窗背景滚动穿透
  },

  /**
   * 下拉刷新
   */
  onPullDownRefresh() {
    Promise.all([
      this.fetchDevices(),
      this.fetchUnreadAlertCount()
    ]).finally(() => {
      wx.stopPullDownRefresh()
      wx.showToast({ title: '已刷新', icon: 'success', duration: 1000 })
    })
  },

  /**
   * 分享设置
   */
  onShareAppMessage() {
    return {
      title: 'KeepSafe - 实时守护家人安全',
      path: '/pages/index/index',
      imageUrl: '../../images/share-banner.png'
    }
  },

  onShareTimeline() {
    return {
      title: 'KeepSafe - 实时守护家人安全',
      imageUrl: '../../images/share-banner.png'
    }
  }
})
