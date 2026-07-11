import QtQuick
import Liminal 1.0

Rectangle {
    id: root

    property string icon: ""
    property bool filled: false
    property bool active: false
    property int iconSize: 20
    property color iconColor: active ? Theme.accentStart : Theme.textSecondary
    property color hoverColor: active ? Theme.hoverOverlay : Theme.hoverOverlay

    signal clicked()

    width: Theme.iconButtonSize
    height: Theme.iconButtonSize
    radius: width / 2
    color: mouse.containsMouse ? hoverColor : "transparent"
    border.color: bordered ? "#1affffff" : "transparent"
    border.width: bordered ? 1 : 0

    property bool bordered: false

    AppIcon {
        anchors.centerIn: parent
        name: root.icon
        filled: root.filled
        color: root.iconColor
        font.pixelSize: root.iconSize

        Behavior on color {
            ColorAnimation {
                duration: Theme.colorDuration
                easing.type: Easing.OutCubic
            }
        }
    }

    MouseArea {
        id: mouse
        anchors.fill: parent
        hoverEnabled: true
        cursorShape: Qt.PointingHandCursor
        onClicked: root.clicked()
    }
}
