import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import Liminal 1.0

Dialog {
    id: root

    title: "Mã chia sẻ"
    modal: true
    anchors.centerIn: parent
    standardButtons: Dialog.Close
    padding: 20

    property string shareCode: ""

    background: Rectangle {
        radius: 14
        color: Theme.glassStrong
        border.color: Theme.glassStrongBorder
        border.width: 1
    }

    function showCode(code) {
        shareCode = code || ""
        open()
    }

    contentItem: ColumnLayout {
        spacing: 14

        Text {
            Layout.fillWidth: true
            text: "Gửi mã này cho bạn bè trong vòng 15 phút. Họ nhập mã tại Music hoặc Videos → Nhập mã."
            wrapMode: Text.Wrap
            font.family: Theme.fontFamily
            font.pixelSize: Theme.bodySize
            color: Theme.textSecondary
        }

        Rectangle {
            Layout.fillWidth: true
            Layout.preferredHeight: 52
            radius: 10
            color: Theme.inputBg
            border.color: Theme.inputBorder

            Text {
                anchors.centerIn: parent
                text: root.shareCode
                font.family: Theme.fontFamily
                font.pixelSize: 28
                font.weight: Font.Bold
                font.letterSpacing: 4
                color: Theme.accentStart
            }
        }

        Rectangle {
            Layout.fillWidth: true
            Layout.preferredHeight: 36
            radius: 8
            color: copyMouse.containsMouse ? Theme.hoverOverlay : Theme.cardBg
            border.color: Theme.inputBorder

            Text {
                anchors.centerIn: parent
                text: "Sao chép mã"
                font.family: Theme.fontFamily
                font.pixelSize: Theme.bodySize
                font.weight: Font.DemiBold
                color: Theme.textPrimary
            }

            MouseArea {
                id: copyMouse
                anchors.fill: parent
                hoverEnabled: true
                cursorShape: Qt.PointingHandCursor
                onClicked: backend.copyToClipboard(root.shareCode)
            }
        }
    }
}
