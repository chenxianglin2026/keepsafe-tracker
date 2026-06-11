/**
 * map-locator 组件 — 可复用地图片段
 *
 * 功能：
 *   - 地图展示 + 标记
 *   - 显示用户当前位置 (show-location)
 *   - 一键定位到我的位置
 *   - 支持标记点击事件回传
 *   - 支持缩放与滚动控制
 *
 * 属性：
 *   latitude  {Number}  地图中心纬度
 *   longitude {Number}  地图中心经度
 *   scale     {Number}  缩放级别 (3-20, default 15)
 *   markers   {Array}   标记数组
 *   showZoom  {Boolean} 是否显示缩放控件 (default true)
 *
 * 事件：
 *   bind:location  — 用户点击"我的位置"按钮后回传当前定位 { latitude, longitude }
 *   bind:markertap — 标记被点击 { markerId, marker }
 *   bind:regionchange — 地图区域变化
 */
Component({
  properties: {
    latitude: {
      type: Number,
      value: 39.908860,
      observer: '_onCenterChange'
    },
    longitude: {
      type: Number,
      value: 116.397390,
      observer: '_onCenterChange'
    },
    scale: {
      type: Number,
      value: 15
    },
    markers: {
      type: Array,
      value: []
    },
    showZoom: {
      type: Boolean,
      value: true
    }
  },

  data: {
    _mapContext: null,
    _userLocation: null
  },

  lifetimes: {
    attached() {
      this._getUserLocation()
    }
  },

  methods: {
    /**
     * 获取用户当前位置并缓存
     */
    _getUserLocation() {
      wx.getLocation({
        type: 'gcj02',
        success: (res) => {
          this.setData({ _userLocation: { latitude: res.latitude, longitude: res.longitude } })
        },
        fail: () => {
          // 用户拒绝/失败，不报错，button 仍可用
        }
      })
    },

    /**
     * 外部更新中心时，移动地图到该位置
     */
    _onCenterChange(newVal, oldVal) {
      if (oldVal == null) return // 初始化时不触发
      const ctx = this._getMapCtx()
      if (!ctx) return
      ctx.moveToLocation({
        latitude: this.properties.latitude,
        longitude: this.properties.longitude
      })
    },

    /**
     * 获取 MapContext
     */
    _getMapCtx() {
      if (!this.data._mapContext) {
        this.data._mapContext = wx.createMapContext('mapLocator', this)
      }
      return this.data._mapContext
    },

    // ── 事件转发 ──────────────────────────────────

    onMarkerTap(e) {
      this.triggerEvent('markertap', e.detail)
    },

    onRegionChange(e) {
      if (e.type === 'end') {
        this.triggerEvent('regionchange', e.detail)
      }
    },

    onMapTap() {
      this.triggerEvent('maptap')
    },

    // ── 我的位置按钮 ──────────────────────────────

    /**
     * 定位到我的位置 (先重新获取 -> 移动地图)
     */
    onLocateMe() {
      const that = this
      wx.getLocation({
        type: 'gcj02',
        success: (res) => {
          const loc = { latitude: res.latitude, longitude: res.longitude }
          that.setData({ _userLocation: loc })

          const ctx = that._getMapCtx()
          ctx.moveToLocation({
            latitude: loc.latitude,
            longitude: loc.longitude
          })

          that.triggerEvent('location', loc)
        },
        fail: () => {
          wx.showToast({ title: '无法获取位置，请确认权限', icon: 'none' })
        }
      })
    },

    // ── 缩放控制 ──────────────────────────────────

    onZoomIn() {
      const newScale = Math.min(this.properties.scale + 2, 20)
      this._updateScale(newScale)
    },

    onZoomOut() {
      const newScale = Math.max(this.properties.scale - 2, 3)
      this._updateScale(newScale)
    },

    _updateScale(scale) {
      this.setData({ scale })
      const ctx = this._getMapCtx()
      if (ctx && ctx.setScale) {
        ctx.setScale({ scale })
      }
    }
  }
})
