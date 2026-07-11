import QtQuick
import QtQuick.Controls
import Liminal 1.0

Menu {
    id: root

    implicitWidth: Math.max(220, contentItem.implicitWidth + 16)
    topPadding: 8
    bottomPadding: 8
    leftPadding: 8
    rightPadding: 8

    delegate: StyledMenuItem {}

    enter: Transition {
        ParallelAnimation {
            NumberAnimation { property: "opacity"; from: 0; to: 1; duration: 120 }
            NumberAnimation { property: "scale"; from: 0.97; to: 1; duration: 140; easing.type: Easing.OutCubic }
        }
    }

    exit: Transition {
        NumberAnimation { property: "opacity"; from: 1; to: 0; duration: 90 }
    }

    background: Rectangle {
        implicitWidth: 220
        color: Theme.glassStrong
        radius: 10
        border.width: 1
        border.color: Theme.glassStrongBorder

        Rectangle {
            anchors.fill: parent
            anchors.margins: 1
            radius: 9
            color: "transparent"
            border.width: 1
            border.color: "#08ffffff"
        }
    }
}
