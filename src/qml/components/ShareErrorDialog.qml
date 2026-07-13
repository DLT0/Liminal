import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import Liminal 1.0

Dialog {
    id: root

    title: "Không thể chia sẻ"
    modal: true
    anchors.centerIn: parent
    standardButtons: Dialog.Ok
    padding: 20
    width: Math.min(480, Overlay.overlay ? Overlay.overlay.width - 48 : 480)

    property string message: ""

    background: Rectangle {
        radius: 14
        color: Theme.glassStrong
        border.color: Theme.glassStrongBorder
        border.width: 1
    }

    function showError(text) {
        message = text || ""
        open()
    }

    contentItem: Text {
        width: root.availableWidth
        text: root.message
        wrapMode: Text.Wrap
        font.family: Theme.fontFamily
        font.pixelSize: Theme.bodySize
        color: Theme.textSecondary
        lineHeight: 1.4
    }
}
