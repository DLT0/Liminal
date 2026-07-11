import QtQuick
import QtQuick.Controls
import Liminal 1.0

ToolTip {
    id: control
    delay: 500
    timeout: 5000
    x: parent ? Math.round((parent.width - width) / 2) : 0
    y: parent ? -height - 8 : 0
    padding: 9

    contentItem: Text {
        text: control.text
        font.family: Theme.fontFamily
        font.pixelSize: Theme.captionSize
        color: Theme.textPrimary
    }

    background: Rectangle {
        color: Theme.glassStrong
        radius: 7
        border.width: 1
        border.color: Theme.glassStrongBorder
    }
}
