import QtQuick
import QtQuick.Controls
import Liminal 1.0

// Album/artist folder card: 2x2 cover collage, title + track count below the art.
Item {
    id: root

    property string title: ""
    property string subtitle: ""
    property int trackCount: 0
    property var trackThumbnails: []
    property string mediaPath: ""
    property color accentColor: Theme.accentEnd
    property bool dropActive: false
    property real dropScale: 1.0

    signal clicked()
    signal contextMenuRequested(real x, real y)
    signal itemDropped(string sourcePath)

    function resolvedThumbnail(index) {
        if (index < 0 || index >= trackThumbnails.length)
            return ""
        var src = trackThumbnails[index]
        if (!src)
            return ""
        if (src.startsWith("http://") || src.startsWith("https://") || src.startsWith("file://"))
            return src
        return "file://" + src
    }

    readonly property string trackCountLabel: {
        if (subtitle.length > 0)
            return subtitle
        if (trackCount <= 0)
            return ""
        return trackCount + " bài"
    }

    readonly property real cardScale: (hoverHandler.hovered || dropActive) ? Theme.hoverScale : 1.0

    width: implicitWidth
    height: artBlock.height + textBlock.implicitHeight

    scale: cardScale * dropScale
    transformOrigin: Item.Center

    Behavior on scale {
        NumberAnimation {
            duration: Theme.hoverDuration
            easing.type: Easing.OutCubic
        }
    }

    Behavior on dropScale {
        NumberAnimation {
            duration: 200
            easing.type: Easing.OutBack
        }
    }

    Column {
        width: parent.width
        spacing: 10

        Item {
            id: artBlock
            width: parent.width
            height: width

            Rectangle {
                id: clipRect
                anchors.fill: parent
                radius: Theme.libraryCardRadius
                clip: true
                color: Theme.cardBg

                Grid {
                    anchors.fill: parent
                    columns: 2
                    rows: 2
                    spacing: 1

                    Repeater {
                        model: 4

                        Item {
                            width: (artBlock.width - 1) / 2
                            height: (artBlock.width - 1) / 2

                            Image {
                                anchors.fill: parent
                                source: root.resolvedThumbnail(index)
                                fillMode: Image.PreserveAspectCrop
                                asynchronous: true
                                cache: true
                                visible: source !== ""
                            }

                            Rectangle {
                                anchors.fill: parent
                                visible: root.resolvedThumbnail(index) === ""
                                color: Theme.cardBg
                            }
                        }
                    }
                }

                Rectangle {
                    anchors.left: parent.left
                    anchors.right: parent.right
                    anchors.bottom: parent.bottom
                    height: 48
                    gradient: Gradient {
                        GradientStop { position: 0.0; color: "#00000000" }
                        GradientStop { position: 1.0; color: "#66000000" }
                    }
                }

                Rectangle {
                    width: Theme.playButtonSize * 0.75
                    height: width
                    radius: width / 2
                    anchors.right: parent.right
                    anchors.bottom: parent.bottom
                    anchors.margins: 10
                    opacity: hoverHandler.hovered ? 1.0 : 0.0
                    visible: opacity > 0

                    Behavior on opacity {
                        NumberAnimation { duration: Theme.colorDuration }
                    }

                    gradient: Gradient {
                        orientation: Gradient.Horizontal
                        GradientStop { position: 0.0; color: Theme.accentStart }
                        GradientStop { position: 1.0; color: Theme.accentEnd }
                    }

                    AppIcon {
                        anchors.centerIn: parent
                        name: "play_arrow"
                        filled: true
                        font.pixelSize: 22
                        color: Theme.textOnAccent
                    }
                }
            }

            Rectangle {
                anchors.fill: parent
                radius: Theme.libraryCardRadius
                color: root.dropActive ? Theme.hoverOverlay : "transparent"
                border.color: root.dropActive ? Theme.accentStart : (hoverHandler.hovered ? Theme.accentStart : Theme.cardBorder)
                border.width: root.dropActive ? 2 : 1

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
                elide: Text.ElideRight
            }

            Text {
                width: parent.width
                visible: root.trackCountLabel.length > 0
                text: root.trackCountLabel
                color: Theme.textSecondary
                font.family: Theme.fontFamily
                font.pixelSize: Theme.captionSize
                elide: Text.ElideRight
            }
        }
    }

    HoverHandler {
        id: hoverHandler
        acceptedDevices: PointerDevice.Mouse | PointerDevice.TouchScreen
    }

    MouseArea {
        anchors.fill: parent
        acceptedButtons: Qt.RightButton
        z: 1
        onClicked: function(mouse) {
            root.contextMenuRequested(mouse.x, mouse.y)
        }
    }
}
