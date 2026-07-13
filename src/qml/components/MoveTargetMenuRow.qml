import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import Liminal 1.0

Item {
    id: root

    property string iconName: ""
    property string label: ""
    signal activated()

    implicitWidth: 204
    implicitHeight: visible && enabled ? 40 : 0
    clip: true

    HoverHandler { id: rowHover }

    TapHandler {
        enabled: root.enabled
        onTapped: root.activated()
    }

    Rectangle {
        anchors.fill: parent
        radius: 7
        color: rowHover.hovered && root.enabled ? Theme.hoverOverlay : "transparent"
        border.width: rowHover.hovered && root.enabled ? 1 : 0
        border.color: Theme.playBorder
    }

    RowLayout {
        anchors.fill: parent
        anchors.leftMargin: 12
        anchors.rightMargin: 12
        spacing: 10

        Item {
            visible: root.iconName !== ""
            Layout.preferredWidth: visible ? 20 : 0
            Layout.preferredHeight: 20
            Layout.alignment: Qt.AlignVCenter

            AppIcon {
                anchors.centerIn: parent
                name: root.iconName
                font.pixelSize: 18
                color: Theme.textSecondary
            }
        }

        Text {
            Layout.fillWidth: true
            Layout.alignment: Qt.AlignVCenter
            text: root.label
            font.family: Theme.fontFamily
            font.pixelSize: Theme.bodySize
            color: root.enabled ? Theme.textSecondary : Theme.textMuted
            verticalAlignment: Text.AlignVCenter
            elide: Text.ElideRight
        }
    }
}
