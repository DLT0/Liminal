import QtQuick
import QtQuick.Controls
import Liminal 1.0

Item {
    id: root

    property string title: ""
    property string subtitle: ""
    property string imageSource: ""
    property string resolvedImageSource: {
        if (!imageSource)
            return ""
        if (imageSource.startsWith("http://") || imageSource.startsWith("https://") || imageSource.startsWith("file://"))
            return imageSource
        return "file://" + imageSource
    }
    property color accentColor: Theme.accentEnd
    property bool clickEnabled: true

    signal clicked()

    HoverHandler {
        id: rootHover
    }

    width: implicitWidth
    height: vinylDisc.height + titleLabel.implicitHeight + subtitleLabel.implicitHeight + 12

    Item {
        id: vinylDisc
        width: parent.width
        height: width

        property real spinAngle: 0

        RotationAnimation on spinAngle {
            id: spinAnim
            running: rootHover.hovered
            from: 0
            to: 360
            direction: RotationAnimation.Clockwise
            duration: 2200
            loops: Animation.Infinite
            easing.type: Easing.Linear
        }

        // Outer vinyl disc (rotates)
        Item {
            id: rotator
            anchors.fill: parent
            rotation: vinylDisc.spinAngle
            transformOrigin: Item.Center

            Rectangle {
                id: disc
                anchors.fill: parent
                radius: width / 2
                color: "#0a0a0a"
                border.color: rootHover.hovered ? root.accentColor : "#1f1f1f"
                border.width: 2

                Behavior on border.color {
                    ColorAnimation { duration: 100 }
                }

                // Groove rings
                Repeater {
                    model: 6
                    Rectangle {
                        anchors.centerIn: parent
                        width: parent.width * (0.92 - index * 0.08)
                        height: width
                        radius: width / 2
                        color: "transparent"
                        border.color: "#151515"
                        border.width: 1
                    }
                }

                // Shine highlight
                Rectangle {
                    anchors.fill: parent
                    radius: width / 2
                    gradient: Gradient {
                        orientation: Gradient.Horizontal
                        GradientStop { position: 0.0; color: "#18ffffff" }
                        GradientStop { position: 0.35; color: "transparent" }
                        GradientStop { position: 1.0; color: "#08000000" }
                    }
                }
            }
        }

        // Center label with cover art (static, does not rotate)
        Rectangle {
            id: labelRing
            anchors.centerIn: parent
                width: parent.width * 0.38
                height: width
                radius: width / 2
                color: "#111111"
                border.color: "#2a2a2a"
                border.width: 2
                clip: true

                Image {
                    anchors.fill: parent
                    anchors.margins: 2
                    source: root.resolvedImageSource
                    fillMode: Image.PreserveAspectCrop
                    asynchronous: true
                    cache: true
                    sourceSize.width: Math.max(64, Math.round(labelRing.width))
                    sourceSize.height: Math.max(64, Math.round(labelRing.height))
                    visible: root.imageSource !== ""
                }

                Rectangle {
                    anchors.fill: parent
                    visible: root.imageSource === ""
                    color: Theme.bgElevated

                    Text {
                        anchors.centerIn: parent
                        text: root.title.length > 0 ? root.title.charAt(0).toUpperCase() : "♪"
                        font.family: Theme.fontFamily
                        font.pixelSize: parent.width * 0.35
                        font.weight: Font.Bold
                        color: "#60ffffff"
                    }
                }

                // Hover overlay on center label
                Rectangle {
                    anchors.fill: parent
                    radius: width / 2
                    color: root.accentColor
                    opacity: rootHover.hovered ? 0.08 : 0.0

                    Behavior on opacity {
                        NumberAnimation { duration: 100 }
                    }
                }

                // Spindle hole
                Rectangle {
                    anchors.centerIn: parent
                    width: parent.width * 0.14
                    height: width
                    radius: width / 2
                    color: "#050505"
                    border.color: "#333333"
                    border.width: 1
                }
            }

        // Static title overlay at bottom of disc area
        Rectangle {
            anchors.left: parent.left
            anchors.right: parent.right
            anchors.bottom: parent.bottom
            height: parent.height * 0.42
            radius: parent.width / 2
            gradient: Gradient {
                orientation: Gradient.Vertical
                GradientStop { position: 0; color: "transparent" }
                GradientStop { position: 1; color: "#cc000000" }
            }
        }

        Column {
            anchors.left: parent.left
            anchors.right: parent.right
            anchors.bottom: parent.bottom
            anchors.margins: 10
            spacing: 2

            Text {
                width: parent.width
                text: root.title
                font.family: Theme.fontFamily
                font.pixelSize: Theme.bodySize
                font.weight: Font.Bold
                color: Theme.textPrimary
                elide: Text.ElideRight
            }

            Text {
                width: parent.width
                text: root.subtitle
                font.family: Theme.fontFamily
                font.pixelSize: Theme.captionSize
                color: Theme.textSecondary
                elide: Text.ElideRight
            }
        }
    }

    Text {
        id: titleLabel
        visible: false
        text: root.title
    }

    Text {
        id: subtitleLabel
        visible: false
        text: root.subtitle
    }

    MouseArea {
        id: hoverMa
        anchors.fill: vinylDisc
        enabled: root.clickEnabled
        acceptedButtons: Qt.LeftButton | Qt.RightButton
        cursorShape: Qt.PointingHandCursor
        onClicked: function(mouse) {
            if (mouse.button === Qt.LeftButton)
                root.clicked()
            else if (mouse.button === Qt.RightButton)
                root.contextMenuRequested(mouse.x, mouse.y)
        }
    }

    signal contextMenuRequested(real x, real y)
}
