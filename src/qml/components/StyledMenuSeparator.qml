import QtQuick
import QtQuick.Controls
import Liminal 1.0

MenuSeparator {
    implicitHeight: 9
    height: visible ? implicitHeight : 0
    clip: true
    contentItem: Rectangle {
        implicitHeight: 1
        color: Theme.glassStrongBorder
    }
}
