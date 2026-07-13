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
        color: Theme.bgTop

        Rectangle {
            anchors.bottom: parent.bottom
            width: parent.width
            height: 1
            color: Theme.glassBorder
            opacity: 0.55
        }
    }

    // Drag region — empty titlebar area moves the window
    MouseArea {
        anchors.fill: parent
        z: 0
        cursorShape: Qt.SizeAllCursor
        acceptedButtons: Qt.LeftButton
        propagateComposedEvents: false

        onPressed: {
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
                { color: Theme.trafficRed, hover: "×", action: "close" },
                { color: Theme.trafficYellow, hover: "−", action: "minimize" },
                { color: Theme.trafficGreen, hover: "□", action: "maximize" }
            ]

            delegate: Item {
                width: 12
                height: 12

                property bool hovered: false

                Rectangle {
                    id: light
                    anchors.fill: parent
                    radius: 6
                    color: modelData.color
                    border.color: Qt.darker(modelData.color, 1.15)
                    border.width: 1
                    scale: parent.hovered ? 1.05 : 1.0

                    Behavior on scale {
                        NumberAnimation { duration: 120; easing.type: Easing.OutQuad }
                    }
                }

                Text {
                    anchors.centerIn: parent
                    text: modelData.hover
                    font.pixelSize: 9
                    font.weight: Font.Bold
                    color: Qt.rgba(0, 0, 0, 0.55)
                    opacity: parent.hovered ? 1.0 : 0.0

                    Behavior on opacity {
                        NumberAnimation { duration: 100 }
                    }
                }

                MouseArea {
                    anchors.fill: parent
                    hoverEnabled: true
                    cursorShape: Qt.PointingHandCursor
                    onEntered: parent.hovered = true
                    onExited: parent.hovered = false
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
        text: root.Window.window ? root.Window.window.title : "Liminal"
        font.family: Theme.fontFamily
        font.pixelSize: 13
        font.weight: Font.DemiBold
        color: Theme.textSecondary
    }
}
