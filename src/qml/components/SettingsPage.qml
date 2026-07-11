import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import Liminal 1.0

Item {
    id: root

    property string mediaRoot: ""
    property string musicDir: ""
    property string videoDir: ""
    property int themeIndex: 0
    property string ytDlpUpdateStatus: ""

    signal pickMediaRoot()
    signal themeSelected(int index)
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
                text: "Thư mục lưu trữ: Chọn một thư mục gốc, Liminal sẽ tự tạo Music và Videos bên trong."
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
                        text: "Mặc định: ~/Media/Liminal (Linux) hoặc C:\\Users\\<bạn>\\Media\\Liminal (Windows)"
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
                text: "Giao diện: Chọn bộ màu phù hợp với sở thích của bạn."
                font.family: Theme.fontFamily
                font.pixelSize: Theme.bodySize
                color: Theme.textMuted
                wrapMode: Text.WordWrap
                Layout.topMargin: 10
            }

            RowLayout {
                Layout.fillWidth: true
                spacing: 12

                Repeater {
                    model: Theme.themeNames

                    delegate: Rectangle {
                        Layout.fillWidth: true
                        Layout.preferredHeight: 72
                        radius: Theme.cardRadius
                        color: root.themeIndex === index ? Theme.accentStart : Theme.glassFill
                        border.color: root.themeIndex === index ? Theme.accentEnd : Theme.glassBorder
                        border.width: root.themeIndex === index ? 2 : 1

                        Behavior on color { ColorAnimation { duration: Theme.colorDuration } }
                        Behavior on border.color { ColorAnimation { duration: Theme.colorDuration } }

                        ColumnLayout {
                            anchors.centerIn: parent
                            spacing: 4

                            Rectangle {
                                Layout.alignment: Qt.AlignHCenter
                                width: 24; height: 24; radius: 12
                                gradient: Gradient {
                                    orientation: Gradient.Horizontal
                                    GradientStop { position: 0; color: Theme.palettes[index].accentStart }
                                    GradientStop { position: 1; color: Theme.palettes[index].accentEnd }
                                }
                            }

                            Text {
                                Layout.alignment: Qt.AlignHCenter
                                text: modelData
                                font.family: Theme.fontFamily
                                font.pixelSize: Theme.captionSize
                                font.weight: root.themeIndex === index ? Font.Bold : Font.Normal
                                color: root.themeIndex === index ? Theme.textOnAccent : Theme.textSecondary
                            }
                        }

                        MouseArea {
                            anchors.fill: parent
                            cursorShape: Qt.PointingHandCursor
                            onClicked: root.themeSelected(index)
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
                text: "Cập nhật yt-dlp để sửa các lỗi tải xuống khi các nền tảng (như YouTube) thay đổi thuật toán."
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
