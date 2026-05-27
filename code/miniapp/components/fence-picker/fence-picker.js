/**
 * 围栏设置组件
 */
const api = require('../../utils/api')

// 全局地图插件 key
// 使用 WebService API 方式

Component({
  properties: {
    visible: {
      type: Boolean,
      value: false,
      observer: 'onVisibleChange'
    },
    deviceId: {
      type: String,
      value: ''
    },
    fenceData: {
      type: Object,
      value: null,
      observer: 'onFenceDataSet'
    }
  },

  data: {
    isEdit: false,
    fenceId: null,
    fenceName: '',
    fenceLatitude: null,
    fenceLongitude: null,
    fenceRadius: 500,
    fenceEnabled: true
  },

  methods: {
    /**
     * 当 visible 变化时
     */
    onVisibleChange(visible) {
      if (visible) {
        if (this.data.fenceData) {
          this.onFenceDataSet(this.data.fenceData)
        } else {
          this.resetForm()
        }
      }
    },

    /**
     * 当传入围栏数据时（编辑模式）
     */
    onFenceDataSet(data) {
      if (data) {
        this.setData({
          isEdit: true,
          fenceId: data.id || null,
          fenceName: data.name || '',
          fenceLatitude: data.lat || data.latitude || null,
          fenceLongitude: data.lng || data.longitude || null,
          fenceRadius: data.radius || 500,
          fenceEnabled: data.enabled !== false
        })
      }
    },

    /**
     * 重置表单（新建模式）
     */
    resetForm() {
      this.setData({
        isEdit: false,
        fenceId: null,
        fenceName: '',
        fenceLatitude: null,
        fenceLongitude: null,
        fenceRadius: 500,
        fenceEnabled: true
      })
    },

    preventMove() {
      // 阻止遮罩层滚动穿透
    },

    onClose() {
      this.triggerEvent('close')
    },

    onNameInput(e) {
      this.setData({ fenceName: e.detail.value })
    },

    /**
     * 选择位置 - 使用腾讯地图选点
     */
    onPickLocation() {
      const that = this
      wx.chooseLocation({
        success: (res) => {
          that.setData({
            fenceLatitude: res.latitude,
            fenceLongitude: res.longitude
          })
        },
        fail: (err) => {
          if (err.errMsg && err.errMsg.indexOf('cancel') === -1) {
            wx.showToast({ title: '定位失败', icon: 'none' })
          }
        }
      })
    },

    onRadiusSelect(e) {
      const radius = parseInt(e.currentTarget.dataset.radius, 10)
      this.setData({ fenceRadius: radius })
    },

    onEnabledChange(e) {
      this.setData({ fenceEnabled: e.detail.value })
    },

    /**
     * 保存围栏
     */
    onSave() {
      const { fenceName, fenceLatitude, fenceLongitude, fenceRadius, fenceEnabled, deviceId, isEdit, fenceId } = this.data

      // 表单验证
      if (!fenceName.trim()) {
        wx.showToast({ title: '请输入围栏名称', icon: 'none' })
        return
      }
      if (!fenceLatitude || !fenceLongitude) {
        wx.showToast({ title: '请选择围栏中心位置', icon: 'none' })
        return
      }

      const payload = {
        name: fenceName.trim(),
        lat: fenceLatitude,
        lng: fenceLongitude,
        radius: fenceRadius,
        enabled: fenceEnabled
      }

      wx.showLoading({ title: '保存中...', mask: true })

      const request = isEdit
        ? api.updateFence(deviceId, fenceId, payload)
        : api.createFence(deviceId, payload)

      request
        .then(() => {
          wx.hideLoading()
          wx.showToast({ title: '保存成功', icon: 'success' })
          this.triggerEvent('saved', { ...payload, id: fenceId })
          this.triggerEvent('close')
        })
        .catch((err) => {
          wx.hideLoading()
          wx.showToast({ title: err.message || '保存失败', icon: 'none' })
        })
    },

    /**
     * 删除围栏
     */
    onDelete() {
      const { deviceId, fenceId } = this.data
      wx.showModal({
        title: '确认删除',
        content: '确定要删除此围栏吗？',
        confirmColor: '#FF4757',
        success: (res) => {
          if (res.confirm) {
            wx.showLoading({ title: '删除中...', mask: true })
            api.deleteFence(deviceId, fenceId)
              .then(() => {
                wx.hideLoading()
                wx.showToast({ title: '已删除', icon: 'success' })
                this.triggerEvent('deleted', { fenceId })
                this.triggerEvent('close')
              })
              .catch((err) => {
                wx.hideLoading()
                wx.showToast({ title: err.message || '删除失败', icon: 'none' })
              })
          }
        }
      })
    }
  }
})
