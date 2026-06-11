/**
 * 我的页面 - 设备管理 + 设置
 */
const api = require('../../utils/api')
const auth = require('../../utils/auth')

Page({
  data: {
    userInfo: {},
    deviceList: [],
    userLocation: null,
    appVersion: '1.0.0',

    // 绑定弹窗
    bindVisible: false,
    bindDeviceId: '',
    bindDeviceToken: '',
    bindDeviceName: ''
  },

  onLoad() {
    this.loadUserInfo()
    this.loadDevices()
    this.loadLocation()
  },

  onShow() {
    this.loadDevices()
  },

  /**
   * 加载用户信息
   */
  loadUserInfo() {
    const app = getApp()
    const userInfo = app.globalData.userInfo || {}

    // 尝试从本地存储获取
    if (!userInfo.nickName) {
      const stored = wx.getStorageSync('userInfo')
      if (stored) {
        this.setData({ userInfo: stored })
        return
      }

      // 从后端获取
      api.getUserInfo()
        .then((user) => {
          const info = {
            nickName: user.nickname || user.nickName || '用户',
            avatarUrl: user.avatar_url || user.avatarUrl || ''
          }
          this.setData({ userInfo: info })
          app.globalData.userInfo = info
          wx.setStorageSync('userInfo', info)
        })
        .catch(() => {})
    } else {
      this.setData({ userInfo })
    }
  },

  /**
   * 加载设备列表
   */
  loadDevices() {
    if (!auth.getToken()) return

    api.getDeviceList()
      .then((devices) => {
        this.setData({ deviceList: Array.isArray(devices) ? devices : [] })
      })
      .catch(() => {})
  },

  /**
   * 获取用户位置（用于卡片距离显示）
   */
  loadLocation() {
    wx.getLocation({
      type: 'gcj02',
      success: (res) => {
        this.setData({
          userLocation: {
            latitude: res.latitude,
            longitude: res.longitude
          }
        })
      },
      fail: () => {}
    })
  },

  // ============================================================
  // 设备操作事件
  // ============================================================

  /**
   * 点击设备卡片 - 跳转设备详情
   */
  onDeviceTap(e) {
    const device = e.detail.device
    if (device && device.device_id) {
      wx.navigateTo({
        url: `/pages/device/device?device_id=${device.device_id}`
      })
    }
  },

  /**
   * 添加设备 - 跳转绑定页面
   */
  onAddDevice() {
    wx.navigateTo({ url: '/pages/bind/bind' })
  },

  onLocateDevice(e) {
    const device = e.detail.device
    const lat = device.latitude || device.lat
    const lng = device.longitude || device.lng
    if (device && lat && lng) {
      wx.switchTab({
        url: '/pages/index/index'
      })
      // 跳转后由首页页面处理定位
      const pages = getCurrentPages()
      const indexPage = pages.find(p => p.route === 'pages/index/index')
      if (indexPage) {
        indexPage.onLocateDevice({ detail: { device } })
      }
    }
  },

  onFenceDevice(e) {
    const device = e.detail.device
    wx.switchTab({
      url: '/pages/index/index'
    })
    const pages = getCurrentPages()
    const indexPage = pages.find(p => p.route === 'pages/index/index')
    if (indexPage) {
      setTimeout(() => {
        indexPage.onFenceDevice({ detail: { device } })
      }, 500)
    }
  },

  onShareDevice(e) {
    const device = e.detail.device
    const pages = getCurrentPages()
    const indexPage = pages.find(p => p.route === 'pages/index/index')
    if (indexPage) {
      indexPage.onShareDevice({ detail: { device } })
    } else {
      wx.showToast({ title: '请先切换到地图页面', icon: 'none' })
    }
  },

  // ============================================================
  // 设置事件
  // ============================================================

  onNotificationSetting() {
    wx.openSetting({
      success: (res) => {
        console.log('[KeepSafe] Setting result:', res)
      }
    })
  },

  onMapSetting() {
    wx.showActionSheet({
      itemList: ['标准地图', '卫星地图'],
      success: (res) => {
        wx.showToast({
          title: res.tapIndex === 0 ? '已切换为标准地图' : '已切换为卫星地图',
          icon: 'none'
        })
      }
    })
  },

  onAbout() {
    wx.showModal({
      title: '关于 KeepSafe',
      content: `KeepSafe v${this.data.appVersion}\n\n一款守护家人安全的智能防丢器。通过实时定位、电子围栏、SOS 告警等功能，让关爱时刻在线。`,
      showCancel: false,
      confirmText: '知道了'
    })
  },

  onPrivacy() {
    wx.showModal({
      title: '隐私政策',
      content: 'KeepSafe 承诺保护您的隐私安全。我们仅收集必要的定位数据用于设备位置追踪，不会泄露您的个人信息。',
      showCancel: false,
      confirmText: '知道了'
    })
  },

  // ============================================================
  // 绑定设备弹窗
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
        this.loadDevices()
      })
      .catch((err) => {
        wx.hideLoading()
        wx.showToast({ title: err.message || '绑定失败', icon: 'none' })
      })
  },

  // ============================================================
  // 退出登录
  // ============================================================

  onLogout() {
    wx.showModal({
      title: '退出登录',
      content: '确定要退出登录吗？',
      confirmColor: '#FF4757',
      success: (res) => {
        if (res.confirm) {
          auth.logout()
        }
      }
    })
  },

  preventMove() {
    // 阻止弹窗背景滚动穿透
  }
})
