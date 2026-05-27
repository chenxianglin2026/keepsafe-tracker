import SwiftUI
import MapKit

/// 地图首页 — 显示设备位置
struct MapView: View {
    @StateObject private var viewModel = MapViewModel()

    var body: some View {
        ZStack(alignment: .bottom) {
            // Map
            mapLayer
                .ignoresSafeArea(edges: .top)

            // Top overlay
            VStack {
                HStack {
                    Text("KeepSafe")
                        .font(.title2)
                        .fontWeight(.bold)
                        .foregroundColor(.white)
                    Spacer()
                    refreshButton
                }
                .padding(.horizontal)
                .padding(.top, safeAreaTop)
                .background(
                    LinearGradient(
                        gradient: Gradient(colors: [
                            Color.black.opacity(0.6),
                            Color.black.opacity(0.0)
                        ]),
                        startPoint: .top,
                        endPoint: .bottom
                    )
                    .ignoresSafeArea(edges: .top)
                )
                Spacer()
            }

            // Bottom device status card
            VStack(spacing: 0) {
                if viewModel.isLoading && viewModel.devices.isEmpty {
                    ProgressView("加载中...")
                        .padding()
                        .background(.ultraThinMaterial)
                        .cornerRadius(12)
                        .padding(.horizontal)
                        .padding(.bottom, 8)
                } else if let device = viewModel.selectedDevice {
                    deviceStatusCard(device)
                        .transition(.move(edge: .bottom).combined(with: .opacity))
                } else if viewModel.devices.isEmpty {
                    emptyStateView
                }
            }
            .padding(.bottom, 8)
        }
        .task {
            await viewModel.loadDevices()
        }
        .alert("错误", isPresented: $viewModel.showError) {
            Button("确定", role: .cancel) {}
        } message: {
            Text(viewModel.errorMessage ?? "未知错误")
        }
    }

    // MARK: - Map Layer

    private var mapLayer: some View {
        Map(
            coordinateRegion: $viewModel.region,
            annotationItems: viewModel.deviceAnnotations
        ) { annotation in
            MapAnnotation(coordinate: annotation.coordinate) {
                deviceMarker(annotation.device)
            }
        }
    }

    // MARK: - Device Marker

    private func deviceMarker(_ device: Device) -> some View {
        VStack(spacing: 2) {
            ZStack {
                Circle()
                    .fill(Color.white)
                    .frame(width: 40, height: 40)
                    .shadow(color: .black.opacity(0.3), radius: 4)

                Image(systemName: "location.circle.fill")
                    .font(.system(size: 18))
                    .foregroundColor(device.isActive ? .blue : .gray)
            }

            Text(device.nickname ?? device.deviceId)
                .font(.caption2)
                .fontWeight(.medium)
                .padding(.horizontal, 4)
                .padding(.vertical, 1)
                .background(Color.black.opacity(0.6))
                .foregroundColor(.white)
                .cornerRadius(4)
        }
        .onTapGesture {
            withAnimation {
                viewModel.selectDevice(device)
            }
        }
    }

    // MARK: - Device Status Card

    private func deviceStatusCard(_ device: Device) -> some View {
        VStack(spacing: 0) {
            // Header
            HStack {
                Image(systemName: "location.circle.fill")
                    .font(.title3)
                    .foregroundColor(.blue)
                Text(device.nickname ?? device.deviceId)
                    .font(.headline)
                Spacer()
                Text(device.isActive ? "在线" : "离线")
                    .font(.caption)
                    .fontWeight(.medium)
                    .padding(.horizontal, 8)
                    .padding(.vertical, 3)
                    .background((device.isActive ? Color.green : Color.secondary).opacity(0.2))
                    .foregroundColor(device.isActive ? .green : .secondary)
                    .cornerRadius(6)
            }
            .padding()

            Divider()

            // Status info
            VStack(spacing: 8) {
                HStack {
                    Image(systemName: "antenna.radiowaves.left.and.right")
                        .foregroundColor(device.isActive ? .green : .red)
                    Text(device.isActive ? "已连接" : "已断开")
                        .font(.caption)
                    Spacer()
                    if let lastSeen = device.lastSeen {
                        Image(systemName: "clock")
                            .foregroundColor(.secondary)
                        Text("上次在线: \(formatTime(lastSeen))")
                            .font(.caption2)
                            .foregroundColor(.secondary)
                    }
                }
            }
            .padding()
        }
        .background(.ultraThinMaterial)
        .cornerRadius(16)
        .shadow(color: .black.opacity(0.15), radius: 8, y: 4)
        .padding(.horizontal)
        .onTapGesture {
            // Could navigate to device detail
        }
    }

    private func formatTime(_ isoString: String) -> String {
        let formatter = ISO8601DateFormatter()
        formatter.formatOptions = [.withInternetDateTime, .withFractionalSeconds]

        if let date = formatter.date(from: isoString) {
            let relative = RelativeDateTimeFormatter()
            relative.unitsStyle = .abbreviated
            relative.locale = Locale(identifier: "zh-Hans")
            return relative.localizedString(for: date, relativeTo: Date())
        }

        return isoString
    }

    // MARK: - Empty State

    private var emptyStateView: some View {
        VStack(spacing: 8) {
            Image(systemName: "location.slash")
                .font(.largeTitle)
                .foregroundColor(.secondary)
            Text("暂无设备")
                .font(.subheadline)
                .foregroundColor(.secondary)
            Text("请在设置中绑定设备")
                .font(.caption)
                .foregroundColor(.secondary)
        }
        .padding()
        .background(.ultraThinMaterial)
        .cornerRadius(12)
        .padding(.horizontal)
    }

    // MARK: - Refresh Button

    private var refreshButton: some View {
        Button {
            Task {
                await viewModel.refreshLocation()
            }
        } label: {
            Image(systemName: "arrow.clockwise")
                .font(.body)
                .foregroundColor(.white)
                .padding(8)
                .background(Color.white.opacity(0.2))
                .clipShape(Circle())
        }
    }

    // MARK: - Safe Area Helper

    private var safeAreaTop: CGFloat {
        if let windowScene = UIApplication.shared.connectedScenes.first as? UIWindowScene,
           let window = windowScene.windows.first {
            return window.safeAreaInsets.top
        }
        return 0
    }
}

// MARK: - Preview

#Preview {
    MapView()
}
