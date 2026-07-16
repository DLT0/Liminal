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
    property bool widescreen: false
    property bool clickEnabled: true
    readonly property bool hovered: hoverHandler.hovered

    signal clicked()

    readonly property real posterAspect: widescreen ? Theme.videoPosterAspect : 1

    HoverHandler {
        id: hoverHandler
    }


    width: implicitWidth
    height: poster.height + titleLabel.implicitHeight + subtitleLabel.implicitHeight + 12

    // Poster
    Item {
        id: poster
        width: parent.width
        height: width / posterAspect

        Rectangle {
            id: clipRect
            anchors.fill: parent
            radius: Theme.libraryCardRadius
            clip: true
            color: Theme.cardBg

            Image {
                anchors.fill: parent
                source: root.resolvedImageSource
                fillMode: Image.PreserveAspectCrop
                asynchronous: true
                cache: true
                sourceSize.width: Math.max(128, Math.round(poster.width))
                sourceSize.height: Math.max(128, Math.round(poster.height))
                visible: root.imageSource !== ""
            }

            // Placeholder flat color when no image
            Rectangle {
                anchors.fill: parent
                visible: root.imageSource === ""
                color: Theme.bgElevated

                Text {
                    anchors.centerIn: parent
                    text: root.title.length > 0 ? root.title.charAt(0).toUpperCase() : "?"
                    font.family: Theme.fontFamily
                    font.pixelSize: 42
                    font.weight: Font.Bold
                    color: "#50ffffff"
                }
            }

            // Bottom gradient overlay
            Rectangle {
                anchors.left: parent.left
                anchors.right: parent.right
                anchors.bottom: parent.bottom
                height: parent.height * 0.45

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
                    id: overlayTitle
                    width: parent.width
                    text: root.title
                    font.family: Theme.fontFamily
                    font.pixelSize: Theme.bodySize
                    font.weight: Font.Bold
                    color: Theme.textPrimary
                    elide: Text.ElideRight
                }

                Text {
                    id: overlaySubtitle
                    width: parent.width
                    text: root.subtitle
                    font.family: Theme.fontFamily
                    font.pixelSize: Theme.captionSize
                    color: Theme.textSecondary
                    elide: Text.ElideRight
                }
            }
        }

        Rectangle {
            anchors.fill: parent
            radius: Theme.libraryCardRadius
            color: "transparent"
            border.color: root.hovered ? root.accentColor : Theme.cardBorder
            border.width: 1

            Behavior on border.color { ColorAnimation { duration: 100 } }
        }

        Rectangle {
            anchors.fill: parent
            radius: Theme.libraryCardRadius
            color: root.hovered ? "#14ffffff" : "transparent"

            Behavior on color { ColorAnimation { duration: 100 } }
        }
    }

    // Labels below poster (hidden — info shown in overlay)
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
        anchors.fill: poster
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
