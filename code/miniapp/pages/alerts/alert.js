/**
 * 告警列表页面逻辑
 */
const api = require('../../utils/api')
const auth = require('../../utils/auth')
const mapUtil = require('../../utils/map')

Page({
  data: {
    alertList: [],
    currentFilter: 'all',
    page: 1,
    pageSize: 20,
    hasMore: true,
    loading: true
  },

  onLoad() {
    this.fetchAlerts()
  },

  onShow() {
    // 从首页跳转时刷新
    this.fetchAlerts()
  },

  /**
   * 下拉刷新
   */
  onPullDownRefresh() {
    this.setData({
      page: 1,
      alertList: [],
      hasMore: true
    })
    this.fetchAlerts().finally(() => {
      wx.stopPullDownRefresh()
    })
  },

  /**
   * 获取告警列表
   */
  fetchAlerts() {
    const { currentFilter, page, pageSize } = this.data

    const params = {
      page,
      page_size: pageSize
    }

    if (currentFilter !== 'all') {
      params.alert_type = currentFilter
    }

    this.setData({ loading: page === 1 })

    return api.getAlertList(params)
      .then((result) => {
        const items = result.items || []
        const total = result.total || 0

        this.setData({
          alertList: page === 1
            ? items
            : [...this.data.alertList, ...items],
          hasMore: this.data.alertList.length + items.length < total,
          loading: false
        })
      })
      .catch((err) => {
        this.setData({ loading: false })
        console.error('[KeepSafe] Fetch alerts error:', err)
      })
  },

  /**
   * 筛选切换
   */
  onFilterChange(e) {
    const type = e.currentTarget.dataset.type
    if (type === this.data.currentFilter) return

    this.setData({
      currentFilter: type,
      page: 1,
      alertList: [],
      hasMore: true,
      loading: true
    })
    this.fetchAlerts()
  },

  /**
   * 加载更多
   */
  onLoadMore() {
    if (!this.data.hasMore || this.data.loading) return
    this.setData({
      page: this.data.page + 1
    })
    this.fetchAlerts()
  },

  /**
   * 点击告警 - 标记已读
   */
  onAlertTap(e) {
    const item = e.currentTarget.dataset.item
    if (!item) return

    // 标记为已读
    if (!item.is_read) {
      api.markAlertRead(item.id)
        .then(() => {
          const list = this.data.alertList.map((a) => {
            if (a.id === item.id) {
              return { ...a, is_read: true }
            }
            return a
          })
          this.setData({ alertList: list })
        })
        .catch(() => {})
    }

    // 如果是 SOS 告警，打开详情页
    if (item.alert_type === 'sos') {
      const p = item.payload || {}
      wx.navigateTo({
        url: `/pages/sos-detail/sos-detail?device_id=${item.device_id || ''}&device_name=${encodeURIComponent(p.device_name || '')}&alert_id=${item.id}&latitude=${p.lat || 0}&longitude=${p.lng || 0}&timestamp=${item.ts || ''}`
      })
      return
    }
  },

  /**
   * 全部标为已读
   */
  onMarkAllRead() {
    wx.showLoading({ title: '处理中...' })
    api.markAllAlertsRead()
      .then(() => {
        wx.hideLoading()
        const list = this.data.alertList.map((a) => ({ ...a, is_read: true }))
        this.setData({ alertList: list })
        wx.showToast({ title: '已全部标记', icon: 'success' })
      })
      .catch((err) => {
        wx.hideLoading()
        wx.showToast({ title: err.message || '操作失败', icon: 'none' })
      })
  },

  /**
   * 告警类型中文名
   */
  alertTypeName(type) {
    const names = {
      sos: 'SOS 求助',
      fence: '围栏告警',
      low_battery: '低电量',
      offline: '设备离线'
    }
    return names[type] || '其他告警'
  },

  /**
   * 格式化时间
   */
  formatTime(time) {
    return mapUtil.formatTime(time)
  }
})
