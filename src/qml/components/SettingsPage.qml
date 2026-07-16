import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import Liminal 1.0

Item {
    id: root

    property string mediaRoot: ""
    property string musicDir: ""
    property string videoDir: ""
    property string uiConfigPath: ""
    property string ytDlpUpdateStatus: ""

    signal pickMediaRoot()
    signal openUiConfigDir()
    signal updateYtDlpRequested()

    readonly property var categories: [
        { id: "general", label: "Chung", icon: "tune" },
        { id: "appearance", label: "Giao diện", icon: "palette" },
        { id: "playback", label: "Phát media", icon: "movie" },
        { id: "library", label: "Thư viện", icon: "folder" },
        { id: "advanced", label: "Nâng cao", icon: "build" }
    ]

    readonly property bool useSideNav: width >= 720
    readonly property bool compactContent: contentFlickable.width < 480

    property int currentCategory: 0

    onCurrentCategoryChanged: contentFlickable.contentY = 0

    function reloadStatusDescription() {
        switch (uiConfig.reloadState) {
        case "reloading": return uiConfig.reloadMessage
        case "ok": return uiConfig.reloadMessage
        case "error": return uiConfig.reloadMessage
        case "disabled": return "Bật lại để tự động áp dụng thay đổi từ settings.json."
        default: return "Theo dõi thay đổi từ settings.json và áp dụng ngay lập tức."
        }
    }

    function reloadStatusColor() {
        switch (uiConfig.reloadState) {
        case "ok": return Theme.trafficGreen
        case "error": return Theme.trafficRed
        case "reloading": return Theme.accent
        default: return Theme.textSecondary
        }
    }

    Rectangle {
        anchors.fill: parent
        color: Theme.bgBase
    }

    RowLayout {
        anchors.fill: parent
        anchors.margins: Theme.contentPadding
        anchors.topMargin: 0
        spacing: 0

        // ── Category navigation ──
        Rectangle {
            Layout.preferredWidth: root.useSideNav ? 196 : 0
            Layout.fillHeight: true
            visible: root.useSideNav
            color: "transparent"
            clip: true

            ColumnLayout {
                anchors.fill: parent
                anchors.topMargin: 4
                spacing: 4

                Repeater {
                    model: root.categories

                    SettingsNavItem {
                        Layout.fillWidth: true
                        label: modelData.label
                        iconName: modelData.icon
                        active: root.currentCategory === index
                        onClicked: root.currentCategory = index
                    }
                }

                Item { Layout.fillHeight: true }
            }

            Rectangle {
                anchors.right: parent.right
                anchors.top: parent.top
                anchors.bottom: parent.bottom
                width: 1
                color: Theme.settingsCardBorder
            }
        }

        ColumnLayout {
            Layout.fillWidth: true
            Layout.fillHeight: true
            spacing: 12

            // Mobile / narrow: category picker
            StyledComboBox {
                Layout.fillWidth: true
                visible: !root.useSideNav
                model: root.categories.map(function(item) { return item.label })
                currentIndex: root.currentCategory
                onActivated: root.currentCategory = index
            }

            Flickable {
                id: contentFlickable
                Layout.fillWidth: true
                Layout.fillHeight: true
                clip: true
                contentWidth: width
                contentHeight: categoryPanel.implicitHeight + 8
                boundsBehavior: Flickable.StopAtBounds
                interactive: contentHeight > height

                ScrollBar.vertical: ScrollBar { policy: ScrollBar.AsNeeded }

                WheelHandler {
                    target: contentFlickable
                    onWheel: function(event) {
                        var delta = event.pixelDelta.y
                        if (delta === 0)
                            delta = event.angleDelta.y / 2
                        if (delta === 0 || !contentFlickable.interactive)
                            return
                        var maximum = Math.max(0, contentFlickable.contentHeight - contentFlickable.height)
                        contentFlickable.contentY = Math.max(0, Math.min(maximum,
                            contentFlickable.contentY - delta))
                        event.accepted = true
                    }
                }

                ColumnLayout {
                    id: categoryPanel
                    width: contentFlickable.width
                    spacing: 16

                    // ── Chung ──
                    ColumnLayout {
                        Layout.fillWidth: true
                        spacing: 16
                        visible: root.currentCategory === 0

                        SettingsSection {
                            Layout.fillWidth: true
                            iconName: "tune"
                            title: "Thiết lập chung"
                            subtitle: "Các tuỳ chọn hoạt động và đồng bộ cấu hình của ứng dụng."

                            SettingsToggleRow {
                                Layout.fillWidth: true
                                label: "Tự động áp dụng cấu hình"
                                description: root.reloadStatusDescription()
                                checked: uiConfig.autoReloadEnabled
                                interactive: true
                                onToggled: uiConfig.setAutoReloadEnabled(checked)
                            }

                            Text {
                                Layout.fillWidth: true
                                Layout.topMargin: 4
                                text: uiConfig.reloadMessage
                                font.family: Theme.fontFamily
                                font.pixelSize: Theme.settingsSubtitleSize
                                color: root.reloadStatusColor()
                                wrapMode: Text.WordWrap
                                visible: uiConfig.reloadState === "reloading"
                                    || uiConfig.reloadState === "ok"
                                    || uiConfig.reloadState === "error"
                            }
                        }
                    }

                    // ── Giao diện ──
                    ColumnLayout {
                        Layout.fillWidth: true
                        spacing: 16
                        visible: root.currentCategory === 1

                        SettingsSection {
                            Layout.fillWidth: true
                            iconName: "palette"
                            title: "Tùy chỉnh giao diện"
                            subtitle: "Chỉnh màu sắc, thanh điều hướng và bố cục thông qua tệp settings.json."

                            Text {
                                Layout.fillWidth: true
                                text: "Xem tệp settings.json.example để biết danh sách tham số hỗ trợ (ví dụ: liminal.colorCustomizations.accent, liminal.sidebar.width)."
                                font.family: Theme.fontFamily
                                font.pixelSize: Theme.settingsSubtitleSize
                                color: Theme.textMuted
                                wrapMode: Text.WordWrap
                            }

                            ColumnLayout {
                                Layout.fillWidth: true
                                spacing: 8
                                visible: root.compactContent

                                SettingsPathField {
                                    Layout.fillWidth: true
                                    path: root.uiConfigPath
                                    placeholder: "~/.config/liminal/settings.json"
                                }

                                SettingsActionButton {
                                    Layout.fillWidth: true
                                    label: "Mở thư mục cấu hình"
                                    onClicked: root.openUiConfigDir()
                                }
                            }

                            RowLayout {
                                Layout.fillWidth: true
                                spacing: 8
                                visible: !root.compactContent

                                SettingsPathField {
                                    Layout.fillWidth: true
                                    path: root.uiConfigPath
                                    placeholder: "~/.config/liminal/settings.json"
                                }

                                SettingsActionButton {
                                    Layout.preferredWidth: 180
                                    label: "Mở thư mục cấu hình"
                                    onClicked: root.openUiConfigDir()
                                }
                            }
                        }
                    }

                    // ── Phát media ──
                    ColumnLayout {
                        Layout.fillWidth: true
                        spacing: 16
                        visible: root.currentCategory === 2

                        SettingsSection {
                            Layout.fillWidth: true
                            iconName: "movie"
                            title: "Trình phát video"
                            subtitle: "Thiết lập có hiệu lực khi bạn mở Focus Mode lần tiếp theo."

                            StyledComboBox {
                                Layout.fillWidth: true
                                model: [
                                    "Phát trong ứng dụng (Qt Multimedia)",
                                    "Phát qua mpv (cửa sổ riêng)"
                                ]
                                currentIndex: backend.videoPlaybackMode === "mpv" ? 1 : 0
                                onActivated: backend.setVideoPlaybackMode(index === 1 ? "mpv" : "inapp")
                            }
                        }
                    }

                    // ── Thư viện ──
                    ColumnLayout {
                        Layout.fillWidth: true
                        spacing: 16
                        visible: root.currentCategory === 3

                        SettingsSection {
                            Layout.fillWidth: true
                            iconName: "folder"
                            title: "Vị trí lưu trữ"
                            subtitle: "Chọn thư mục gốc cho thư viện nhạc, video và sách điện tử."

                            Text {
                                Layout.fillWidth: true
                                text: "Đường dẫn mặc định: ~/Media/Liminal (Linux), C:\\Users\\<tên người dùng>\\Media\\Liminal (Windows)"
                                font.family: Theme.fontFamily
                                font.pixelSize: Theme.settingsSubtitleSize
                                color: Theme.textMuted
                                wrapMode: Text.WordWrap
                            }

                            RowLayout {
                                Layout.fillWidth: true
                                spacing: 8

                                SettingsPathField {
                                    Layout.fillWidth: true
                                    path: root.mediaRoot
                                    placeholder: "Đang khởi tạo đường dẫn mặc định…"
                                }

                                IconButton {
                                    Layout.preferredWidth: 40
                                    Layout.preferredHeight: 40
                                    icon: "folder"
                                    iconSize: 20
                                    bordered: true
                                    onClicked: root.pickMediaRoot()
                                }
                            }

                            RowLayout {
                                Layout.fillWidth: true
                                spacing: 8
                                visible: root.mediaRoot !== ""

                                AppIcon {
                                    name: backend.freeDiskSpaceGB < 10 ? "warning" : "info"
                                    font.pixelSize: 16
                                    color: backend.freeDiskSpaceGB < 10 ? Theme.trafficYellow : Theme.textMuted
                                }

                                Text {
                                    Layout.fillWidth: true
                                    Layout.minimumWidth: 0
                                    text: backend.freeDiskSpaceGB < 10
                                        ? "Dung lượng trống: " + backend.freeDiskSpaceGB.toFixed(1) + " GB. Cảnh báo: dung lượng dưới 10 GB — vui lòng giải phóng dung lượng hoặc chuyển sang thư mục khác."
                                        : "Dung lượng trống: " + backend.freeDiskSpaceGB.toFixed(1) + " GB."
                                    font.family: Theme.fontFamily
                                    font.pixelSize: Theme.settingsSubtitleSize
                                    color: backend.freeDiskSpaceGB < 10 ? Theme.trafficYellow : Theme.textSecondary
                                    wrapMode: Text.WordWrap
                                }
                            }
                        }
                    }

                    // ── Nâng cao ──
                    ColumnLayout {
                        Layout.fillWidth: true
                        spacing: 16
                        visible: root.currentCategory === 4

                        SettingsSection {
                            Layout.fillWidth: true
                            iconName: "build"
                            title: "Công cụ nâng cao"
                            subtitle: "Cập nhật module yt-dlp để duy trì khả năng tải xuống khi các nền tảng thay đổi."

                            RowLayout {
                                Layout.fillWidth: true
                                spacing: 12
                                visible: !root.compactContent

                                SettingsActionButton {
                                    Layout.preferredWidth: 200
                                    label: "Cập nhật yt-dlp"
                                    busy: root.ytDlpUpdateStatus === "Đang cập nhật yt-dlp…"
                                    onClicked: root.updateYtDlpRequested()
                                }

                                Text {
                                    Layout.fillWidth: true
                                    Layout.minimumWidth: 0
                                    visible: root.ytDlpUpdateStatus !== ""
                                    text: root.ytDlpUpdateStatus
                                    font.family: Theme.fontFamily
                                    font.pixelSize: Theme.settingsSubtitleSize
                                    color: Theme.textSecondary
                                    wrapMode: Text.WordWrap
                                }
                            }

                            ColumnLayout {
                                Layout.fillWidth: true
                                spacing: 8
                                visible: root.compactContent

                                SettingsActionButton {
                                    Layout.fillWidth: true
                                    label: "Cập nhật yt-dlp"
                                    busy: root.ytDlpUpdateStatus === "Đang cập nhật yt-dlp…"
                                    onClicked: root.updateYtDlpRequested()
                                }

                                Text {
                                    Layout.fillWidth: true
                                    visible: root.ytDlpUpdateStatus !== ""
                                    text: root.ytDlpUpdateStatus
                                    font.family: Theme.fontFamily
                                    font.pixelSize: Theme.settingsSubtitleSize
                                    color: Theme.textSecondary
                                    wrapMode: Text.WordWrap
                                }
                            }
                        }

                        SettingsSection {
                            Layout.fillWidth: true
                            iconName: "cookie"
                            title: "Cookie trình duyệt cho YouTube"
                            subtitle: "Dùng cookie từ trình duyệt để giảm lỗi HTTP 403 khi tải video YouTube."

                            StyledComboBox {
                                Layout.fillWidth: true
                                model: [
                                    "Không dùng cookie",
                                    "Firefox",
                                    "Chrome",
                                    "Chromium",
                                    "Brave",
                                    "Edge",
                                    "Opera"
                                ]
                                readonly property var browserKeys: ["", "firefox", "chrome", "chromium", "brave", "edge", "opera"]
                                currentIndex: {
                                    var idx = browserKeys.indexOf(backend.youtubeCookiesBrowser)
                                    return idx >= 0 ? idx : 0
                                }
                                onActivated: backend.setYoutubeCookiesBrowser(browserKeys[index])
                            }
                        }
                    }

                    Item {
                        Layout.fillWidth: true
                        Layout.preferredHeight: 8
                    }
                }
            }

        }
    }
}
