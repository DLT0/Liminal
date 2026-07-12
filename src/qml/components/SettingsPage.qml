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

    ScrollView {
        anchors.fill: parent
        anchors.margins: Theme.contentPadding
        clip: true

        ColumnLayout {
            width: parent.width
            spacing: 20

            Text {
                text: "Cài đặt"
                font.family: Theme.fontFamily
                font.pixelSize: Theme.pageTitleSize
                font.weight: Font.Bold
                color: Theme.textPrimary
            }

            // ── General Settings ──

            Text {
                Layout.fillWidth: true
                text: "Vị trí lưu trữ: Chọn thư mục gốc cho thư viện của bạn. Liminal sẽ tự động quản lý và phân loại các tệp âm nhạc và video bên trong."
                font.family: Theme.fontFamily
                font.pixelSize: Theme.bodySize
                color: Theme.textMuted
                wrapMode: Text.WordWrap
            }

            GlassPanel {
                Layout.fillWidth: true
                Layout.preferredHeight: rootPanel.implicitHeight + 24
                radius: Theme.cardRadius

                ColumnLayout {
                    id: rootPanel
                    anchors.fill: parent
                    anchors.margins: 16
                    spacing: 10

                    Text {
                        Layout.fillWidth: true
                        text: "Đường dẫn mặc định: ~/Media/Liminal (Linux) hoặc C:\\Users\\<tên_người_dùng>\\Media\\Liminal (Windows)"
                        font.family: Theme.fontFamily
                        font.pixelSize: Theme.captionSize
                        color: Theme.textMuted
                        wrapMode: Text.WordWrap
                    }

                    RowLayout {
                        Layout.fillWidth: true
                        spacing: 10

                        Rectangle {
                            Layout.fillWidth: true
                            Layout.preferredHeight: 40
                            radius: 8
                            color: Theme.inputBg
                            border.color: Theme.inputBorder

                            Text {
                                anchors.fill: parent
                                anchors.margins: 10
                                text: root.mediaRoot || "Đang thiết lập mặc định…"
                                font.family: Theme.fontFamily
                                font.pixelSize: Theme.bodySize
                                color: Theme.textSecondary
                                elide: Text.ElideMiddle
                                verticalAlignment: Text.AlignVCenter
                            }
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
                }
            }

            Text {
                Layout.fillWidth: true
                text: "Cấu hình giao diện: Thực hiện tùy chỉnh thông qua tệp settings.json. Các thay đổi sẽ có hiệu lực sau khi khởi động lại ứng dụng."
                font.family: Theme.fontFamily
                font.pixelSize: Theme.bodySize
                color: Theme.textMuted
                wrapMode: Text.WordWrap
                Layout.topMargin: 10
            }

            GlassPanel {
                Layout.fillWidth: true
                Layout.preferredHeight: uiPanel.implicitHeight + 24
                radius: Theme.cardRadius

                ColumnLayout {
                    id: uiPanel
                    anchors.fill: parent
                    anchors.margins: 16
                    spacing: 10

                    Text {
                        Layout.fillWidth: true
                        text: "Tệp cấu hình hệ thống"
                        font.family: Theme.fontFamily
                        font.pixelSize: Theme.bodySize
                        font.weight: Font.Bold
                        color: Theme.textPrimary
                    }

                    Text {
                        Layout.fillWidth: true
                        text: "Vui lòng tham khảo tệp settings.json.example để xem chi tiết các tham số cấu hình được hỗ trợ (ví dụ: liminal.colorCustomizations.accent, liminal.sidebar.width)."
                        font.family: Theme.fontFamily
                        font.pixelSize: Theme.captionSize
                        color: Theme.textMuted
                        wrapMode: Text.WordWrap
                    }

                    RowLayout {
                        Layout.fillWidth: true
                        spacing: 10

                        Rectangle {
                            Layout.fillWidth: true
                            Layout.preferredHeight: 40
                            radius: 8
                            color: Theme.inputBg
                            border.color: Theme.inputBorder

                            Text {
                                anchors.fill: parent
                                anchors.margins: 10
                                text: root.uiConfigPath || "~/.config/liminal/settings.json"
                                font.family: Theme.fontFamily
                                font.pixelSize: Theme.bodySize
                                color: Theme.textSecondary
                                elide: Text.ElideMiddle
                                verticalAlignment: Text.AlignVCenter
                            }
                        }

                        Rectangle {
                            Layout.preferredWidth: 160
                            Layout.preferredHeight: 40
                            radius: 8
                            color: Theme.glassFill
                            border.color: Theme.glassBorder
                            border.width: 1

                            Text {
                                anchors.centerIn: parent
                                text: "Mở thư mục"
                                font.family: Theme.fontFamily
                                font.pixelSize: Theme.bodySize
                                font.weight: Font.Bold
                                color: Theme.textSecondary
                            }

                            MouseArea {
                                anchors.fill: parent
                                cursorShape: Qt.PointingHandCursor
                                onClicked: root.openUiConfigDir()
                            }
                        }
                    }
                }
            }

            // ── Advanced Settings ──
            Text {
                text: "Nâng cao"
                font.family: Theme.fontFamily
                font.pixelSize: 18
                font.weight: Font.Bold
                color: Theme.textPrimary
                Layout.topMargin: 20
            }

            Text {
                Layout.fillWidth: true
                text: "Cập nhật module yt-dlp: Đảm bảo khả năng tương thích và khắc phục các sự cố tải xuống khi các nền tảng trực tuyến cập nhật thuật toán."
                font.family: Theme.fontFamily
                font.pixelSize: Theme.bodySize
                color: Theme.textMuted
                wrapMode: Text.WordWrap
            }

            RowLayout {
                Layout.fillWidth: true
                spacing: 12

                Rectangle {
                    Layout.preferredWidth: 200
                    Layout.preferredHeight: 44
                    radius: Theme.cardRadius
                    color: Theme.glassFill
                    border.color: Theme.glassBorder
                    border.width: 1

                    Text {
                        anchors.centerIn: parent
                        text: "Cập nhật yt-dlp"
                        font.family: Theme.fontFamily
                        font.pixelSize: Theme.bodySize
                        font.weight: Font.Bold
                        color: Theme.textSecondary
                    }

                    MouseArea {
                        anchors.fill: parent
                        cursorShape: Qt.PointingHandCursor
                        onClicked: root.updateYtDlpRequested()
                    }
                }

                Text {
                    Layout.fillWidth: true
                    text: root.ytDlpUpdateStatus
                    font.family: Theme.fontFamily
                    font.pixelSize: Theme.bodySize
                    color: Theme.textMuted
                    elide: Text.ElideRight
                }
            }
        }
    }
}
