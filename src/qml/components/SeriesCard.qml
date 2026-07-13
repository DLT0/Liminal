import QtQuick
import QtQuick.Controls
import Liminal 1.0

// Netflix-style series tile: 16:9 poster, episode badge, title below.
Item {
    id: root

    property string title: ""
    property string subtitle: ""
    property string imageSource: ""
    property int episodeCount: 0
    property color accentColor: Theme.accentEnd
    property bool clickEnabled: true

    signal clicked()
    signal contextMenuRequested(real x, real y)

    readonly property string resolvedImageSource: {
        if (!imageSource)
            return ""
        if (imageSource.startsWith("http://") || imageSource.startsWith("https://") || imageSource.startsWith("file://"))
            return imageSource
        return "file://" + imageSource
    }
    readonly property real cardScale: hoverMa.containsMouse ? Theme.hoverScale : 1.0
    readonly property string badgeText: {
        if (root.episodeCount > 0)
            return root.episodeCount + " tập"
        if (root.subtitle.length > 0)
            return root.subtitle
        return "Phim bộ"
    }

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
                anchors.fill: parent
                radius: 4
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
                    color: Theme.bgElevated

                    AppIcon {
                        anchors.centerIn: parent
                        name: "video_library"
                        font.pixelSize: 32
                        color: Theme.textMuted
                    }
                }

                Rectangle {
                    anchors.fill: parent
                    gradient: Gradient {
                        orientation: Gradient.Vertical
                        GradientStop { position: 0.55; color: "transparent" }
                        GradientStop { position: 1.0; color: "#cc000000" }
                    }
                }

                Rectangle {
                    anchors.left: parent.left
                    anchors.top: parent.top
                    anchors.margins: 8
                    radius: 3
                    color: "#000000"
                    opacity: 0.72
                    width: badgeLabel.implicitWidth + 12
                    height: badgeLabel.implicitHeight + 6

                    Text {
                        id: badgeLabel
                        anchors.centerIn: parent
                        text: root.badgeText
                        color: "#ffffff"
                        font.family: Theme.fontFamily
                        font.pixelSize: Theme.captionSize
                        font.weight: Font.Medium
                    }
                }

                Rectangle {
                    anchors.fill: parent
                    color: "#66000000"
                    opacity: hoverMa.containsMouse ? 1 : 0

                    Behavior on opacity {
                        NumberAnimation { duration: 150 }
                    }

                    AppIcon {
                        anchors.centerIn: parent
                        name: "play_arrow"
                        filled: true
                        font.pixelSize: 44
                        color: "#ffffff"
                    }
                }
            }

            Rectangle {
                anchors.fill: parent
                radius: 4
                color: "transparent"
                border.color: hoverMa.containsMouse ? "#ffffff" : Theme.cardBorder
                border.width: hoverMa.containsMouse ? 2 : 1

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
                visible: root.subtitle.length > 0 && root.episodeCount > 0
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
