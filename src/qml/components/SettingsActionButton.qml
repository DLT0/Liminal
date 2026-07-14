import QtQuick
import Liminal 1.0

Rectangle {
    id: root

    property string label: ""
    property bool busy: false

    signal clicked()

    implicitWidth: labelText.implicitWidth + 32
    implicitHeight: 40
    radius: 8
    color: mouse.containsMouse && !busy ? Theme.bgCardHover : Theme.inputBg
    border.color: Theme.settingsCardBorder
    border.width: 1
    opacity: busy ? 0.65 : 1

    Behavior on color {
        ColorAnimation {
            duration: Theme.colorDuration
            easing.type: Easing.OutCubic
        }
    }

    Text {
        id: labelText
        anchors.centerIn: parent
        text: root.label
        font.family: Theme.fontFamily
        font.pixelSize: Theme.bodySize
        font.weight: Font.Medium
        color: Theme.textSecondary
    }

    MouseArea {
        id: mouse
        anchors.fill: parent
        hoverEnabled: true
        enabled: !root.busy
        cursorShape: enabled ? Qt.PointingHandCursor : Qt.ArrowCursor
        onClicked: root.clicked()
    }
}
