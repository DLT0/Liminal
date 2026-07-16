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
    readonly property bool hovered: hoverHandler.hovered

    signal clicked()
    signal contextMenuRequested(real x, real y)

    HoverHandler {
        id: hoverHandler
    }


    width: implicitWidth
    height: folderBody.height + titleLabel.implicitHeight + subtitleLabel.implicitHeight + 12

    Item {
        id: folderBody
        width: parent.width
        height: width * 0.82

        // Folder back panel
        Rectangle {
            id: folderBack
            anchors.left: parent.left
            anchors.right: parent.right
            anchors.bottom: parent.bottom
            height: parent.height * 0.78
            radius: Theme.libraryCardRadius
            color: "#c9a227"
            border.color: "#a8841a"
            border.width: 1
            z: 0

            Rectangle {
                anchors.left: parent.left
                anchors.top: parent.top
                width: parent.width * 0.42
                height: parent.height * 0.18
                radius: Theme.libraryCardRadius
                color: "#d4ad2e"
                border.color: "#a8841a"
                border.width: 1
            }

            gradient: Gradient {
                orientation: Gradient.Vertical
                GradientStop { position: 0; color: "#e8c547" }
                GradientStop { position: 1; color: "#b8921f" }
            }
        }

        // Folder front panel (covers lower part of thumbnail)
        Rectangle {
            id: folderFront
            anchors.left: parent.left
            anchors.right: parent.right
            anchors.bottom: parent.bottom
            height: parent.height * 0.68
            radius: Theme.libraryCardRadius
            color: "#f0d060"
            border.color: root.hovered ? root.accentColor : "#c9a227"
            border.width: 1
            z: 2

            Behavior on border.color { ColorAnimation { duration: 100 } }

            gradient: Gradient {
                orientation: Gradient.Vertical
                GradientStop { position: 0; color: "#f5d96a" }
                GradientStop { position: 1; color: "#d4ad2e" }
            }

            Rectangle {
                anchors.left: parent.left
                anchors.right: parent.right
                anchors.bottom: parent.bottom
                height: parent.height * 0.5
                radius: Theme.libraryCardRadius
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
                    color: "#1a1400"
                    elide: Text.ElideRight
                }

                Text {
                    width: parent.width
                    text: root.subtitle
                    font.family: Theme.fontFamily
                    font.pixelSize: Theme.captionSize
                    color: "#3d3200"
                    elide: Text.ElideRight
                }
            }
        }

        // Preview thumbnail on top of folder back, bottom tucked under front flap
        Rectangle {
            id: thumbFrame
            anchors.right: folderBack.right
            anchors.rightMargin: parent.width * 0.1
            anchors.bottom: folderFront.top
            anchors.bottomMargin: -height * 0.22
            width: parent.width * 0.5
            height: width * 0.72
            radius: Theme.libraryCardRadius
            color: "#1a1a1a"
            border.color: "#ffffff55"
            border.width: 1.5
            clip: true
            z: 1
            visible: root.imageSource !== ""

            Image {
                anchors.fill: parent
                source: root.resolvedImageSource
                fillMode: Image.PreserveAspectCrop
                asynchronous: true
                cache: true
                sourceSize.width: Math.max(96, Math.round(thumbFrame.width))
                sourceSize.height: Math.max(96, Math.round(thumbFrame.height))
            }

            // Subtle shadow so thumbnail reads above the folder
            Rectangle {
                anchors.fill: parent
                radius: Theme.libraryCardRadius
                color: "transparent"
                border.color: "#00000040"
                border.width: 1
            }

            // Dark overlay on hover
            Rectangle {
                anchors.fill: parent
                radius: Theme.libraryCardRadius
                color: "#000000"
                opacity: root.hovered ? 0.08 : 0

                Behavior on opacity { NumberAnimation { duration: 100 } }
            }

            // Play button overlay
            Rectangle {
                anchors.centerIn: parent
                width: 36
                height: 36
                radius: width / 2
                color: root.accentColor
                opacity: root.hovered ? 1 : 0

                Behavior on opacity { NumberAnimation { duration: 100 } }

                AppIcon {
                    anchors.centerIn: parent
                    name: "play_arrow"
                    color: "#ffffff"
                    font.pixelSize: 18
                }
            }
        }

        Rectangle {
            anchors.fill: folderFront
            radius: Theme.libraryCardRadius
            color: "transparent"
            z: 3
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
        anchors.fill: folderBody
        acceptedButtons: Qt.LeftButton | Qt.RightButton
        cursorShape: Qt.PointingHandCursor
        z: 12
        onClicked: function(mouse) {
            if (mouse.button === Qt.LeftButton)
                root.clicked()
            else if (mouse.button === Qt.RightButton)
                root.contextMenuRequested(mouse.x, mouse.y)
        }
    }
}
