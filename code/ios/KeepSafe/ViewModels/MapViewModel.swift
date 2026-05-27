import Foundation
import MapKit
import Combine

/// 地图首页 ViewModel
@MainActor
class MapViewModel: ObservableObject {
    // MARK: - Published Properties

    @Published var devices: [Device] = []
    @Published var selectedDevice: Device?
    @Published var region: MKCoordinateRegion
    @Published var deviceAnnotations: [DeviceAnnotation] = []
    @Published var isLoading = false
    @Published var errorMessage: String?
    @Published var showError = false

    // MARK: - Initialization

    init() {
        // Default to Beijing area
        region = MKCoordinateRegion(
            center: CLLocationCoordinate2D(latitude: 39.9042, longitude: 116.4074),
            span: MKCoordinateSpan(latitudeDelta: 0.05, longitudeDelta: 0.05)
        )
    }

    // MARK: - Data Loading

    /// 加载设备列表和位置
    func loadDevices() async {
        isLoading = true
        errorMessage = nil

        do {
            let fetchedDevices = try await APIService.shared.getDevices()
            devices = fetchedDevices

            // Update annotations by fetching each device's location
            var annotations: [DeviceAnnotation] = []
            for device in fetchedDevices {
                do {
                    let location = try await APIService.shared.getDeviceLocation(id: device.deviceId)
                    if let lat = location.latitude, let lng = location.longitude {
                        let annotation = DeviceAnnotation(
                            device: device,
                            coordinate: CLLocationCoordinate2D(
                                latitude: lat,
                                longitude: lng
                            )
                        )
                        annotations.append(annotation)
                    }
                } catch {
                    // Skip devices without location data
                    continue
                }
            }
            deviceAnnotations = annotations

            // Auto-select first device with location
            if selectedDevice == nil, let firstAnnotation = annotations.first {
                selectedDevice = firstAnnotation.device
                region.center = firstAnnotation.coordinate
            }
        } catch {
            errorMessage = error.localizedDescription
            showError = true
        }

        isLoading = false
    }

    /// 选择设备并聚焦
    func selectDevice(_ device: Device) {
        selectedDevice = device
        if let annotation = deviceAnnotations.first(where: { $0.device.deviceId == device.deviceId }) {
            withAnimation {
                region.center = annotation.coordinate
            }
        }
    }

    /// 刷新设备位置
    func refreshLocation() async {
        await loadDevices()
    }
}

// MARK: - Map Annotation

struct DeviceAnnotation: Identifiable {
    let id: String
    let device: Device
    let coordinate: CLLocationCoordinate2D

    init(device: Device, coordinate: CLLocationCoordinate2D) {
        self.id = device.deviceId
        self.device = device
        self.coordinate = coordinate
    }
}
