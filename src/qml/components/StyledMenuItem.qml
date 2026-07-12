import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import Liminal 1.0

MenuItem {
    id: control

    property string iconName: ""
    property bool destructive: false

    implicitWidth: 204
    implicitHeight: 40
    height: visible ? implicitHeight : 0
    clip: true
    leftPadding: 12
    rightPadding: 12
    spacing: 10

    arrow: AppIcon {
        name: "chevron_right"
        color: Theme.textMuted
        font.pixelSize: 18
        visible: control.subMenu !== null
    }

    indicator: Item {
        implicitWidth: 0
        implicitHeight: 0
    }

    contentItem: RowLayout {
        spacing: control.spacing

        Item {
            visible: control.iconName !== ""
            Layout.preferredWidth: visible ? 20 : 0
            Layout.preferredHeight: 20
            Layout.alignment: Qt.AlignVCenter

            AppIcon {
                anchors.centerIn: parent
                name: control.iconName
                font.pixelSize: 18
                color: control.destructive ? Theme.trafficRed : Theme.textSecondary
            }
        }

        Text {
            Layout.fillWidth: true
            Layout.alignment: Qt.AlignVCenter
            text: control.text
            font.family: Theme.fontFamily
            font.pixelSize: Theme.bodySize
            font.weight: control.highlighted && control.font.weight === Font.Normal
                        ? Font.DemiBold
                        : control.font.weight
            color: !control.enabled ? Theme.textMuted
                  : control.destructive ? Theme.trafficRed
                  : control.highlighted ? Theme.textPrimary : Theme.textSecondary
            verticalAlignment: Text.AlignVCenter
            elide: Text.ElideRight
        }
    }

    background: Rectangle {
        radius: 7
        color: control.highlighted ? Theme.hoverOverlay : "transparent"
        border.width: control.highlighted ? 1 : 0
        border.color: Theme.playBorder

        Behavior on color { ColorAnimation { duration: 100 } }
    }
}
