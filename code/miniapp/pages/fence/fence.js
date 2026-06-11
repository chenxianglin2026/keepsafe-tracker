/**
 * 围栏管理页面
 * 支持创建圆形围栏、编辑、删除、开关切换
 */
const api = require('../../utils/api')
const auth = require('../../utils/auth')

Page({
  data: {
    deviceId: '',
    deviceNickname: '',
    fenceList: [],
    loading: true,

    // 编辑弹窗
    editVisible: false,
    editingId: null,
    editName: '',
    editLatitude: null,
    editLongitude: null,
    editRadius: 500,
    editEnabled: true
  },

  onLoad(options) {
    const deviceId = options.device_id || ''
    const nickname = options.nickname ? decodeURIComponent(options.nickname) : ''

    if (!deviceId) {
      wx.showToast({ title: '缺少设备 ID', icon: 'none' })
      setTimeout(() => wx.navigateBack(), 1500)
      return
    }

    this.setData({ deviceId, deviceNickname: nickname })
    this.loadFences()
  },

  onShow() {
    if (this.data.deviceId) {
      this.loadFences()
    }
  },

  /**
   * 加载围栏列表
   */
  loadFences() {
    this.setData({ loading: true })

    api.getFenceList(this.data.deviceId)
      .then((fences) => {
        this.setData({
          fenceList: Array.isArray(fences) ? fences : [],
          loading: false
        })
      })
      .catch((err) => {
        console.error('[KeepSafe] Load fences error:', err)
        this.setData({ loading: false })
        wx.showToast({ title: err.message || '加载围栏失败', icon: 'none' })
      })
  },

  /**
   * 创建围栏
   */
  onCreateFence() {
    this.setData({
      editVisible: true,
      editingId: null,
      editName: '',
      editLatitude: null,
      editLongitude: null,
      editRadius: 500,
      editEnabled: true
    })
  },

  /**
   * 编辑围栏
   */
  onEditFence(e) {
    const item = e.currentTarget.dataset.item
    if (!item) return

    this.setData({
      editVisible: true,
      editingId: item.id,
      editName: item.name || '',
      editLatitude: item.lat || item.latitude,
      editLongitude: item.lng || item.longitude,
      editRadius: item.radius || 500,
      editEnabled: item.enabled !== false
    })
  },

  /**
   * 保存围栏 (创建或更新)
   */
  onSaveFence() {
    const { deviceId, editingId, editName, editLatitude, editLongitude, editRadius, editEnabled } = this.data

    if (!editName.trim()) {
      wx.showToast({ title: '请输入围栏名称', icon: 'none' })
      return
    }
    if (!editLatitude || !editLongitude) {
      wx.showToast({ title: '请选择围栏中心位置', icon: 'none' })
      return
    }

    const payload = {
      name: editName.trim(),
      lat: editLatitude,
      lng: editLongitude,
      radius: editRadius,
      enabled: editEnabled
    }

    wx.showLoading({ title: '保存中...', mask: true })

    const request = editingId
      ? api.updateFence(deviceId, editingId, payload)
      : api.createFence(deviceId, payload)

    request
      .then(() => {
        wx.hideLoading()
        wx.showToast({ title: '保存成功', icon: 'success' })
        this.setData({ editVisible: false })
        this.loadFences()
      })
      .catch((err) => {
        wx.hideLoading()
        wx.showToast({ title: err.message || '保存失败', icon: 'none' })
      })
  },

  /**
   * 删除围栏
   */
  onDeleteFence(e) {
    const fenceId = e.currentTarget.dataset.id
    wx.showModal({
      title: '确认删除',
      content: '确定要删除此围栏吗？',
      confirmColor: '#FF4757',
      success: (res) => {
        if (res.confirm) {
          wx.showLoading({ title: '删除中...', mask: true })
          api.deleteFence(this.data.deviceId, fenceId)
            .then(() => {
              wx.hideLoading()
              wx.showToast({ title: '已删除', icon: 'success' })
              this.loadFences()
            })
            .catch((err) => {
              wx.hideLoading()
              wx.showToast({ title: err.message || '删除失败', icon: 'none' })
            })
        }
      }
    })
  },

  /**
   * 切换围栏开关
   */
  onToggleFence(e) {
    const fenceId = e.currentTarget.dataset.id
    const enabled = !e.currentTarget.dataset.enabled

    api.updateFence(this.data.deviceId, fenceId, { enabled })
      .then(() => {
        // 本地更新
        const list = this.data.fenceList.map(f => {
          if (f.id === fenceId) return { ...f, enabled }
          return f
        })
        this.setData({ fenceList: list })
      })
      .catch((err) => {
        wx.showToast({ title: err.message || '操作失败', icon: 'none' })
      })
  },

  /**
   * 选择位置 - 使用微信地图选点
   */
  onPickLocation() {
    wx.chooseLocation({
      success: (res) => {
        this.setData({
          editLatitude: res.latitude,
          editLongitude: res.longitude
        })
      },
      fail: (err) => {
        if (err.errMsg && err.errMsg.indexOf('cancel') === -1) {
          wx.showToast({ title: '定位失败', icon: 'none' })
        }
      }
    })
  },

  /**
   * 选择半径
   */
  onRadiusSelect(e) {
    const radius = parseInt(e.currentTarget.dataset.radius, 10)
    this.setData({ editRadius: radius })
  },

  /**
   * 输入事件
   */
  onNameInput(e) {
    this.setData({ editName: e.detail.value })
  },

  onEditClose() {
    this.setData({ editVisible: false })
  },

  preventMove() {
    // 阻止弹窗背景滚动穿透
  }
})
