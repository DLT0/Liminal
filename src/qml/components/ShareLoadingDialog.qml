import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import Liminal 1.0

Popup {
    id: root

    modal: true
    focus: true
    closePolicy: Popup.NoAutoClose
    anchors.centerIn: Overlay.overlay
    padding: 24
    width: Math.min(420, Overlay.overlay ? Overlay.overlay.width - 48 : 420)

    background: Rectangle {
        radius: 14
        color: Theme.glassStrong
        border.color: Theme.glassStrongBorder
        border.width: 1
    }

    contentItem: ColumnLayout {
        spacing: 16

        BusyIndicator {
            Layout.alignment: Qt.AlignHCenter
            running: root.visible
            width: 36
            height: 36
        }

        Text {
            Layout.fillWidth: true
            text: shareBridge.shareBusyMessage.length > 0
                ? shareBridge.shareBusyMessage
                : "Đang xử lý…"
            wrapMode: Text.Wrap
            horizontalAlignment: Text.AlignHCenter
            font.family: Theme.fontFamily
            font.pixelSize: Theme.bodySize
            font.weight: Font.DemiBold
            color: Theme.textPrimary
            lineHeight: 1.35
        }

        Text {
            Layout.fillWidth: true
            text: "Vui lòng đợi, không nhấn chia sẻ lại."
            wrapMode: Text.Wrap
            horizontalAlignment: Text.AlignHCenter
            font.family: Theme.fontFamily
            font.pixelSize: Theme.captionSize
            color: Theme.textMuted
        }
    }
}
