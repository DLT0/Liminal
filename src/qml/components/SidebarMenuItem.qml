import QtQuick
import QtQuick.Controls
import Liminal 1.0

Rectangle {
    id: root

    property string icon: ""
    property string label: ""
    property bool active: false
    property bool keyboardFocused: false

    signal clicked()

    height: 40
    radius: 12
    color: "transparent"

    Rectangle {
        id: activeBg
        anchors.fill: parent
        radius: parent.radius
        opacity: root.active ? 1 : 0

        gradient: Gradient {
            GradientStop { position: 0; color: Theme.accentStart }
            GradientStop { position: 1; color: Theme.accentEnd }
        }

        border.color: "#26eab308"
        border.width: 1

        Behavior on opacity {
            NumberAnimation {
                duration: Theme.colorDuration
                easing.type: Easing.OutCubic
            }
        }
    }

    Row {
        anchors.fill: parent
        anchors.leftMargin: 14
        anchors.rightMargin: 14
        spacing: 10

        AppIcon {
            anchors.verticalCenter: parent.verticalCenter
            name: root.icon
            font.pixelSize: 20
            color: root.active ? Theme.textOnAccent : Theme.textSecondary

            Behavior on color {
                ColorAnimation {
                    duration: Theme.colorDuration
                    easing.type: Easing.OutCubic
                }
            }
        }

        Text {
            anchors.verticalCenter: parent.verticalCenter
            text: root.label
            font.family: Theme.fontFamily
            font.pixelSize: Theme.bodySize
            font.weight: root.active ? Font.DemiBold : Font.Normal
            color: root.active ? Theme.textOnAccent : Theme.textSecondary

            Behavior on color {
                ColorAnimation {
                    duration: Theme.colorDuration
                    easing.type: Easing.OutCubic
                }
            }
        }
    }

    Rectangle {
        anchors.fill: parent
        radius: parent.radius
        color: hoverMa.containsMouse && !root.active ? Theme.hoverOverlay : "transparent"

        Behavior on color {
            ColorAnimation {
                duration: Theme.colorDuration
                easing.type: Easing.OutCubic
            }
        }
    }

    Rectangle {
        anchors.fill: parent
        radius: parent.radius
        visible: root.keyboardFocused
        color: root.active
            ? Qt.rgba(1, 1, 1, 0.14)
            : "transparent"
        border.color: root.active ? "#CCFFFFFF" : Theme.accentStart
        border.width: Theme.focusRingWidth
        z: 5

        Behavior on border.color {
            ColorAnimation {
                duration: Theme.colorDuration
                easing.type: Easing.OutCubic
            }
        }
    }

    MouseArea {
        id: hoverMa
        anchors.fill: parent
        hoverEnabled: true
        cursorShape: Qt.PointingHandCursor
        onClicked: root.clicked()
    }
}
