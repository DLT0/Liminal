import QtQuick
import QtQuick.Layouts
import Liminal 1.0

Rectangle {
    id: root

    property string label: ""
    property string iconName: "settings"
    property bool active: false

    signal clicked()

    height: 40
    radius: 8
    color: root.active
        ? Qt.rgba(Theme.accent.r, Theme.accent.g, Theme.accent.b, 0.12)
        : (navMouse.containsMouse ? Qt.rgba(1, 1, 1, 0.05) : "transparent")

    Behavior on color {
        ColorAnimation {
            duration: Theme.colorDuration
            easing.type: Easing.OutCubic
        }
    }

    RowLayout {
        anchors.fill: parent
        anchors.leftMargin: 12
        anchors.rightMargin: 12
        spacing: 10

        AppIcon {
            name: root.iconName
            font.pixelSize: 18
            color: root.active ? Theme.accent : Theme.textSecondary
        }

        Text {
            Layout.fillWidth: true
            text: root.label
            font.family: Theme.fontFamily
            font.pixelSize: Theme.bodySize
            font.weight: root.active ? Font.DemiBold : Font.Normal
            color: root.active ? Theme.textPrimary : Theme.textSecondary
            elide: Text.ElideRight
        }
    }

    MouseArea {
        id: navMouse
        anchors.fill: parent
        hoverEnabled: true
        cursorShape: Qt.PointingHandCursor
        onClicked: root.clicked()
    }
}
