import QtQuick
import QtQuick.Controls
import Liminal 1.0

MenuItem {
    id: control

    property string iconName: ""
    property bool destructive: false

    implicitWidth: 204
    implicitHeight: 40
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
        implicitWidth: control.iconName === "" ? 0 : 20
        implicitHeight: 20
        AppIcon {
            anchors.centerIn: parent
            name: control.iconName
            font.pixelSize: 18
            color: control.destructive ? Theme.trafficRed : Theme.textSecondary
        }
    }

    contentItem: Text {
        leftPadding: control.indicator.width > 0 ? control.spacing : 0
        text: control.text
        font.family: Theme.fontFamily
        font.pixelSize: Theme.bodySize
        font.weight: control.highlighted ? Font.DemiBold : Font.Normal
        color: !control.enabled ? Theme.textMuted
              : control.destructive ? Theme.trafficRed
              : control.highlighted ? Theme.textPrimary : Theme.textSecondary
        verticalAlignment: Text.AlignVCenter
        elide: Text.ElideRight
    }

    background: Rectangle {
        radius: 7
        color: control.highlighted ? Theme.hoverOverlay : "transparent"
        border.width: control.highlighted ? 1 : 0
        border.color: Theme.playBorder

        Behavior on color { ColorAnimation { duration: 100 } }
    }
}
