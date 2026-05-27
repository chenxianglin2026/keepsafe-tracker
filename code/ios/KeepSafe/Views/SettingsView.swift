import SwiftUI

/// 设置页面 — 设备管理 + 用户资料
struct SettingsView: View {
    @StateObject private var viewModel = SettingsViewModel()
    @State private var showUnbindConfirm: Device?

    var body: some View {
        NavigationStack {
            List {
                // MARK: User Profile Section
                Section {
                    NavigationLink {
                        profileEditView
                    } label: {
                        HStack(spacing: 12) {
                            // Avatar
                            ZStack {
                                Circle()
                                    .fill(Color.blue.opacity(0.2))
                                    .frame(width: 56, height: 56)
                                Image(systemName: "person.circle.fill")
                                    .font(.system(size: 32))
                                    .foregroundColor(.blue)
                            }

                            VStack(alignment: .leading, spacing: 2) {
                                Text(viewModel.user?.nickname ?? "用户")
                                    .font(.headline)
                                Text(viewModel.user?.phone ?? "点击设置个人信息")
                                    .font(.caption)
                                    .foregroundColor(.secondary)
                            }
                        }
                        .padding(.vertical, 4)
                    }
                }

                // MARK: Device Management Section
                Section("我的设备") {
                    if viewModel.devices.isEmpty {
                        HStack {
                            Spacer()
                            VStack(spacing: 8) {
                                Image(systemName: "device.tag.slash")
                                    .font(.title2)
                                    .foregroundColor(.secondary)
                                Text("暂无绑定设备")
                                    .font(.subheadline)
                                    .foregroundColor(.secondary)
                            }
                            Spacer()
                        }
                        .padding(.vertical, 8)
                    } else {
                        ForEach(viewModel.devices) { device in
                            deviceRow(device)
                                .swipeActions(edge: .trailing, allowsFullSwipe: true) {
                                    Button("解绑", role: .destructive) {
                                        showUnbindConfirm = device
                                    }
                                }
                        }
                    }

                    // Bind new device button
                    Button {
                        viewModel.showDeviceBindSheet = true
                    } label: {
                        Label("绑定新设备", systemImage: "plus.circle.fill")
                            .foregroundColor(.blue)
                    }
                }

                // MARK: Notification Settings
                Section("通知设置") {
                    Toggle(isOn: $viewModel.settings.notificationsEnabled) {
                        Label("推送通知", systemImage: "bell.fill")
                    }
                    .onChange(of: viewModel.settings.notificationsEnabled) { _, newValue in
                        if newValue && !viewModel.pushNotificationEnabled {
                            Task { await viewModel.requestPushPermission() }
                        }
                        viewModel.saveSettings()
                    }

                    Toggle(isOn: $viewModel.settings.soundEnabled) {
                        Label("声音", systemImage: "speaker.wave.2.fill")
                    }
                    .disabled(!viewModel.settings.notificationsEnabled)
                    .onChange(of: viewModel.settings.soundEnabled) { _, _ in
                        viewModel.saveSettings()
                    }

                    Toggle(isOn: $viewModel.settings.vibrationEnabled) {
                        Label("震动", systemImage: "iphone.radiowaves.left.and.right")
                    }
                    .disabled(!viewModel.settings.notificationsEnabled)
                    .onChange(of: viewModel.settings.vibrationEnabled) { _, _ in
                        viewModel.saveSettings()
                    }
                }

                // MARK: Map Settings
                Section("地图设置") {
                    Picker("地图类型", selection: $viewModel.settings.mapType) {
                        ForEach(AppSettings.MapType.allCases) { type in
                            Text(type.displayName).tag(type)
                        }
                    }
                    .onChange(of: viewModel.settings.mapType) { _, _ in
                        viewModel.saveSettings()
                    }
                }

                // MARK: About Section
                Section("关于") {
                    HStack {
                        Text("版本")
                        Spacer()
                        Text("1.0.0")
                            .foregroundColor(.secondary)
                    }
                    NavigationLink {
                        aboutView
                    } label: {
                        Text("关于 KeepSafe")
                    }
                }
            }
            .navigationTitle("设置")
            .navigationBarTitleDisplayMode(.large)
            .task {
                viewModel.loadSettings()
                await viewModel.loadData()
            }
            .refreshable {
                await viewModel.loadData()
            }
            .sheet(isPresented: $viewModel.showDeviceBindSheet) {
                DeviceBindView()
            }
            .alert("解绑设备", isPresented: .init(
                get: { showUnbindConfirm != nil },
                set: { if !$0 { showUnbindConfirm = nil } }
            )) {
                Button("取消", role: .cancel) {}
                Button("解绑", role: .destructive) {
                    if let device = showUnbindConfirm {
                        Task { await viewModel.unbindDevice(device) }
                    }
                    showUnbindConfirm = nil
                }
            } message: {
                Text("确定要解绑「\(showUnbindConfirm?.nickname ?? showUnbindConfirm?.deviceId ?? "")」吗？解绑后设备将不再受监控。")
            }
        }
    }

    // MARK: - Device Row

    private func deviceRow(_ device: Device) -> some View {
        HStack(spacing: 12) {
            ZStack {
                Circle()
                    .fill(deviceActiveColor(device.isActive).opacity(0.15))
                    .frame(width: 40, height: 40)
                Image(systemName: "location.circle.fill")
                    .font(.system(size: 16))
                    .foregroundColor(deviceActiveColor(device.isActive))
            }

            VStack(alignment: .leading, spacing: 2) {
                Text(device.nickname ?? device.deviceId)
                    .font(.subheadline)
                    .fontWeight(.semibold)
                Text(device.deviceId)
                    .font(.caption)
                    .foregroundColor(.secondary)
                    .lineLimit(1)
                Text(device.isActive ? "在线" : "离线")
                    .font(.caption2)
                    .foregroundColor(deviceActiveColor(device.isActive))
            }

            Spacer()

            // Status indicator
            Image(systemName: device.isActive ? "circle.fill" : "circle")
                .font(.caption)
                .foregroundColor(deviceActiveColor(device.isActive))
        }
        .padding(.vertical, 2)
    }

    private func deviceActiveColor(_ isActive: Bool) -> Color {
        isActive ? .green : .secondary
    }

    // MARK: - Profile Edit View

    private var profileEditView: some View {
        Form {
            Section("个人信息") {
                HStack {
                    Text("昵称")
                    Spacer()
                    Text(viewModel.user?.nickname ?? "未设置")
                        .foregroundColor(.secondary)
                }
                HStack {
                    Text("手机号")
                    Spacer()
                    Text(viewModel.user?.phone ?? "未设置")
                        .foregroundColor(.secondary)
                }
                HStack {
                    Text("邮箱")
                    Spacer()
                    Text(viewModel.user?.email ?? "未设置")
                        .foregroundColor(.secondary)
                }
            }
        }
        .navigationTitle("个人资料")
        .navigationBarTitleDisplayMode(.inline)
    }

    // MARK: - About View

    private var aboutView: some View {
        List {
            Section {
                VStack(spacing: 12) {
                    Image(systemName: "shield.checkered")
                        .font(.system(size: 48))
                        .foregroundColor(.blue)
                    Text("KeepSafe")
                        .font(.title2)
                        .fontWeight(.bold)
                    Text("防丢器 · 老人小孩定位器")
                        .font(.subheadline)
                        .foregroundColor(.secondary)
                    Text("版本 1.0.0")
                        .font(.caption)
                        .foregroundColor(.secondary)
                }
                .frame(maxWidth: .infinity)
                .padding(.vertical, 20)
            }

            Section {
                Link(destination: URL(string: "https://keepsafe.app/privacy")!) {
                    Label("隐私政策", systemImage: "hand.raised.fill")
                }
                Link(destination: URL(string: "https://keepsafe.app/terms")!) {
                    Label("服务条款", systemImage: "doc.text.fill")
                }
            }
        }
        .navigationTitle("关于")
        .navigationBarTitleDisplayMode(.inline)
    }
}

// MARK: - Preview

#Preview {
    SettingsView()
}
