import QtQuick
import QtQuick.Controls
import Liminal 1.0

Rectangle {
    id: root

    property string icon: ""
    property string label: ""
    property bool active: false

    signal clicked()
    signal doubleClicked()

    height: 40
    radius: 12
    color: "transparent"
    border.width: root.active ? 1 : 0
    border.color: root.active ? Theme.accent : "transparent"

    Row {
        anchors.fill: parent
        anchors.leftMargin: 14
        anchors.rightMargin: 14
        spacing: 10

        AppIcon {
            anchors.verticalCenter: parent.verticalCenter
            name: root.icon
            font.pixelSize: 20
            color: root.active ? Theme.accent : Theme.textPrimary
        }

        Text {
            anchors.verticalCenter: parent.verticalCenter
            text: root.label
            font.family: Theme.fontFamily
            font.pixelSize: Theme.bodySize
            font.weight: root.active ? Font.DemiBold : Font.Normal
            color: root.active ? Theme.accent : Theme.textPrimary
            elide: Text.ElideRight
        }
    }

    Timer {
        id: singleClickDelay
        interval: 220
        onTriggered: root.clicked()
    }

    MouseArea {
        anchors.fill: parent
        cursorShape: Qt.PointingHandCursor
        onClicked: singleClickDelay.restart()
        onDoubleClicked: {
            singleClickDelay.stop()
            root.doubleClicked()
        }
    }
}
