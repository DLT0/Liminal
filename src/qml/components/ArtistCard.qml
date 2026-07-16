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
    property color accentColor: Theme.accentEnd

    signal clicked()
    signal contextMenuRequested(real x, real y)

    readonly property bool hovered: hoverHandler.hovered

    HoverHandler {
        id: hoverHandler
    }

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


    width: implicitWidth
    height: artBlock.height + textBlock.implicitHeight

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
                    anchors.fill: parent
                    radius: Theme.libraryCardRadius
                    color: root.hovered ? "#14ffffff" : "transparent"

                    Behavior on color { ColorAnimation { duration: 100 } }
                }

                AppIcon {
                    anchors.centerIn: parent
                    name: "play_arrow"
                    font.pixelSize: 36
                    color: Theme.textPrimary
                    opacity: root.hovered ? 1.0 : 0.0

                    Behavior on opacity {
                        NumberAnimation { duration: 100 }
                    }
                }


            }

            Rectangle {
                anchors.fill: parent
                radius: Theme.libraryCardRadius
                color: "transparent"
                border.color: root.hovered ? root.accentColor : Theme.cardBorder
                border.width: 2

                Behavior on border.color { ColorAnimation { duration: 100 } }
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


    MouseArea {
        anchors.fill: parent
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
