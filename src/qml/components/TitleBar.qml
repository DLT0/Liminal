import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import QtQuick.Window
import Liminal 1.0

Item {
    id: root
    height: Theme.titleBarHeight

    signal closeRequested()
    signal minimizeRequested()
    signal maximizeRequested()

    Rectangle {
        anchors.fill: parent
        color: "#66000000"
    }

    // Drag region (behind buttons; empty titlebar area moves window)
    MouseArea {
        anchors.fill: parent
        z: 0
        cursorShape: Qt.SizeAllCursor
        acceptedButtons: Qt.LeftButton
        propagateComposedEvents: false

        onPressed: (mouse) => {
            const win = root.Window.window
            if (win)
                win.startSystemMove()
        }

        onDoubleClicked: {
            const win = root.Window.window
            if (!win)
                return
            win.visibility === Window.Maximized
                ? win.showNormal()
                : win.showMaximized()
        }
    }

    // macOS traffic lights (left)
    Row {
        z: 1
        anchors.left: parent.left
        anchors.leftMargin: 14
        anchors.verticalCenter: parent.verticalCenter
        spacing: 8

        Repeater {
            model: [
                { color: Theme.trafficRed, action: "close" },
                { color: Theme.trafficYellow, action: "minimize" },
                { color: Theme.trafficGreen, action: "maximize" }
            ]

            delegate: Rectangle {
                width: 12
                height: 12
                radius: 6
                color: modelData.color
                border.color: Qt.darker(modelData.color, 1.15)
                border.width: 1

                MouseArea {
                    anchors.fill: parent
                    cursorShape: Qt.PointingHandCursor
                    onClicked: {
                        if (modelData.action === "close")
                            root.closeRequested()
                        else if (modelData.action === "minimize")
                            root.minimizeRequested()
                        else
                            root.maximizeRequested()
                    }
                }
            }
        }
    }

    // App title (center)
    Text {
        z: 1
        anchors.centerIn: parent
        text: "Liminal"
        font.family: Theme.fontFamily
        font.pixelSize: 14
        font.weight: Font.DemiBold
        color: Theme.textPrimary
    }

    // Window controls (right)
    Row {
        z: 1
        anchors.right: parent.right
        anchors.rightMargin: 12
        anchors.verticalCenter: parent.verticalCenter
        spacing: 4

        Repeater {
            model: [
                { icon: "remove", action: "minimize" },
                { icon: "check_box_outline_blank", action: "maximize" },
                { icon: "close", action: "close" }
            ]

            delegate: IconButton {
                icon: modelData.icon
                iconSize: 18
                width: 28
                height: 28
                radius: 6

                onClicked: {
                    if (modelData.action === "close")
                        root.closeRequested()
                    else if (modelData.action === "minimize")
                        root.minimizeRequested()
                    else
                        root.maximizeRequested()
                }
            }
        }
    }
}
