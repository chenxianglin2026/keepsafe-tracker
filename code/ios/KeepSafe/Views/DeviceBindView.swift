import SwiftUI

/// 设备绑定页面
struct DeviceBindView: View {
    @Environment(\.dismiss) private var dismiss
    @StateObject private var viewModel = DeviceBindViewModel()

    var body: some View {
        NavigationStack {
            ScrollView {
                VStack(spacing: 24) {
                    // Header
                    VStack(spacing: 8) {
                        Image(systemName: "plus.viewfinder")
                            .font(.system(size: 48))
                            .foregroundColor(.blue)
                        Text("绑定设备")
                            .font(.title2)
                            .fontWeight(.bold)
                        Text("输入设备 ID")
                            .font(.subheadline)
                            .foregroundColor(.secondary)
                    }
                    .padding(.top, 20)

                    // Device ID Input
                    VStack(alignment: .leading, spacing: 8) {
                        Text("设备 ID")
                            .font(.headline)
                        TextField("请输入设备 ID", text: $viewModel.deviceId)
                            .textFieldStyle(.roundedBorder)
                            .autocapitalization(.none)
                            .disableAutocorrection(true)
                    }
                    .padding(.horizontal)

                    // Bind token Input
                    VStack(alignment: .leading, spacing: 8) {
                        Text("绑定码")
                            .font(.headline)
                        TextField("请输入设备上的绑定码", text: $viewModel.token)
                            .textFieldStyle(.roundedBorder)
                            .autocapitalization(.none)
                            .disableAutocorrection(true)
                    }
                    .padding(.horizontal)

                    // Bind Button
                    Button {
                        Task { await viewModel.bind() }
                    } label: {
                        if viewModel.isBinding {
                            ProgressView()
                                .progressViewStyle(.circular)
                                .tint(.white)
                        } else {
                            Text("绑定设备")
                                .fontWeight(.semibold)
                        }
                    }
                    .frame(maxWidth: .infinity)
                    .padding()
                    .background(Color.blue)
                    .foregroundColor(.white)
                    .cornerRadius(12)
                    .padding(.horizontal)
                    .disabled(viewModel.isBinding || viewModel.deviceId.isEmpty || viewModel.token.isEmpty)

                    // Error message
                    if let error = viewModel.errorMessage {
                        Text(error)
                            .font(.caption)
                            .foregroundColor(.red)
                            .multilineTextAlignment(.center)
                            .padding(.horizontal)
                    }

                    // Success state
                    if viewModel.bindSuccess {
                        VStack(spacing: 12) {
                            Image(systemName: "checkmark.circle.fill")
                                .font(.system(size: 48))
                                .foregroundColor(.green)
                            Text("绑定成功！")
                                .font(.headline)
                                .foregroundColor(.green)
                            Text("设备「\(viewModel.deviceId)」已成功绑定")
                                .font(.subheadline)
                                .foregroundColor(.secondary)
                                .multilineTextAlignment(.center)
                        }
                        .padding()
                    }

                    Spacer()
                }
            }
            .navigationTitle("绑定设备")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .cancellationAction) {
                    Button("取消") {
                        dismiss()
                    }
                }
                if viewModel.bindSuccess {
                    ToolbarItem(placement: .confirmationAction) {
                        Button("完成") {
                            dismiss()
                        }
                    }
                }
            }
        }
    }
}

// MARK: - DeviceBindViewModel

@MainActor
class DeviceBindViewModel: ObservableObject {
    @Published var deviceId = ""
    @Published var token = ""
    @Published var isBinding = false
    @Published var bindSuccess = false
    @Published var errorMessage: String?

    private let userId: String

    init(userId: String = "") {
        self.userId = userId
    }

    func bind() async {
        guard !deviceId.isEmpty, !token.isEmpty else { return }

        isBinding = true
        errorMessage = nil

        do {
            let _ = try await APIService.shared.bindDevice(
                deviceId: deviceId,
                token: token,
                userId: userId
            )
            bindSuccess = true
        } catch {
            errorMessage = error.localizedDescription
        }

        isBinding = false
    }
}

// MARK: - Preview

#Preview {
    DeviceBindView()
}
