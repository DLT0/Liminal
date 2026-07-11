import QtQuick
import QtQuick.Controls
import Liminal 1.0

// Video grid card: 16:9 thumbnail, title + channel below (never overlaid on the image).
Item {
    id: root

    property string title: ""
    property string subtitle: ""
    property string duration: ""
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
    signal contextMenuRequested(real x, real y)

    readonly property bool showDuration: duration.length > 0 && duration !== "--:--"
    readonly property real cardScale: hoverMa.containsMouse ? Theme.hoverScale : 1.0

    width: implicitWidth
    height: thumbBlock.height + textBlock.implicitHeight

    scale: cardScale
    transformOrigin: Item.Center

    Behavior on scale {
        NumberAnimation {
            duration: Theme.hoverDuration
            easing.type: Easing.OutCubic
        }
    }

    Column {
        width: parent.width
        spacing: 10

        Item {
            id: thumbBlock
            width: parent.width
            height: width / Theme.videoPosterAspect

            Rectangle {
                id: clipRect
                anchors.fill: parent
                radius: Theme.libraryCardRadius
                clip: true
                color: Theme.cardBg

                Image {
                    id: thumb
                    anchors.fill: parent
                    source: root.resolvedImageSource
                    fillMode: Image.PreserveAspectCrop
                    asynchronous: true
                    cache: true
                    visible: root.imageSource !== ""
                }

                Rectangle {
                    anchors.fill: parent
                    visible: root.imageSource === "" || thumb.status !== Image.Ready
                    color: Theme.cardBg

                    gradient: Gradient {
                        orientation: Gradient.Vertical
                        GradientStop { position: 0; color: Qt.lighter(root.accentColor, 1.3) }
                        GradientStop { position: 1; color: Qt.darker(root.accentColor, 1.4) }
                    }

                    AppIcon {
                        anchors.centerIn: parent
                        name: "videocam"
                        font.pixelSize: 28
                        color: Theme.textMuted
                    }
                }

                Rectangle {
                    visible: root.showDuration
                    anchors.right: parent.right
                    anchors.bottom: parent.bottom
                    anchors.margins: 6
                    radius: 4
                    color: "#000000"
                    opacity: 0.75
                    width: durationText.implicitWidth + 10
                    height: durationText.implicitHeight + 4

                    Text {
                        id: durationText
                        anchors.centerIn: parent
                        text: root.duration
                        color: Theme.textPrimary
                        font.family: Theme.fontFamily
                        font.pixelSize: Theme.captionSize
                    }
                }
            }

            Rectangle {
                anchors.fill: parent
                radius: Theme.libraryCardRadius
                color: "transparent"
                border.color: hoverMa.containsMouse ? Theme.accentStart : Theme.cardBorder
                border.width: 1

                Behavior on border.color {
                    ColorAnimation { duration: Theme.colorDuration }
                }
            }
        }

        Column {
            id: textBlock
            width: parent.width
            spacing: 4

            Text {
                width: parent.width
                text: root.title
                color: Theme.textPrimary
                font.family: Theme.fontFamily
                font.pixelSize: Theme.bodySize
                font.weight: Font.Medium
                wrapMode: Text.Wrap
                maximumLineCount: 2
                elide: Text.ElideRight
            }

            Text {
                width: parent.width
                visible: root.subtitle.length > 0
                text: root.subtitle
                color: Theme.textSecondary
                font.family: Theme.fontFamily
                font.pixelSize: Theme.captionSize
                elide: Text.ElideRight
            }
        }
    }

    MouseArea {
        id: hoverMa
        anchors.fill: parent
        enabled: root.clickEnabled
        hoverEnabled: true
        acceptedButtons: Qt.LeftButton | Qt.RightButton
        cursorShape: Qt.PointingHandCursor
        onClicked: function(mouse) {
            if (mouse.button === Qt.LeftButton)
                root.clicked()
            else if (mouse.button === Qt.RightButton)
                root.contextMenuRequested(mouse.x, mouse.y)
        }
    }
}
