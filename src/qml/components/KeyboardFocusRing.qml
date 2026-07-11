import QtQuick
import Liminal 1.0

Item {
    id: root

    property bool show: false
    property real ringRadius: Theme.cardRadius
    property int ringWidth: 2
    property color ringColor: Theme.accentStart
    property real glowOpacity: 0.28

    anchors.fill: parent
    visible: show
    opacity: show ? 1 : 0
    z: 200

    Behavior on opacity {
        NumberAnimation {
            duration: Theme.colorDuration
            easing.type: Easing.OutCubic
        }
    }

    Rectangle {
        anchors.fill: parent
        anchors.margins: -3
        radius: root.ringRadius + 3
        color: "transparent"
        border.color: Qt.rgba(
            root.ringColor.r,
            root.ringColor.g,
            root.ringColor.b,
            root.glowOpacity
        )
        border.width: 5
    }

    Rectangle {
        anchors.fill: parent
        radius: root.ringRadius
        color: "transparent"
        border.color: root.ringColor
        border.width: root.ringWidth
    }
}
