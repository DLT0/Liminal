import QtQuick
import QtQuick.Controls
import Liminal 1.0

// Shared video card: gray thumbnail until downloaded, color reveal from bottom during progress.
Item {
    id: root

    property string title: ""
    property string subtitle: ""
    property string imageSource: ""
    property real downloadPercent: 0
    property string downloadStatus: "pending"
    property bool isDownloading: false
    property bool isSeries: false
    property bool inLibrary: downloadStatus === "done" && !isSeries

    property bool hovered: false

    signal playRequested()
    signal downloadRequested()
    signal contextMenuRequested(real x, real y)

    readonly property string resolvedImageSource: {
        if (!imageSource)
            return ""
        if (imageSource.startsWith("http://") || imageSource.startsWith("https://") || imageSource.startsWith("file://"))
            return imageSource
        return "file://" + imageSource
    }
    readonly property real revealFraction: (inLibrary || isSeries)
        ? (isSeries ? Math.max(0, Math.min(1, downloadPercent / 100)) : 1)
        : Math.max(0, Math.min(1, downloadPercent / 100))

    width: implicitWidth
    height: thumbBlock.height + textBlock.implicitHeight

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
                border.color: root.hovered ? Theme.accentStart : "transparent"
                border.width: 2

                Behavior on border.color {
                    NumberAnimation { duration: 100 }
                }

                Item {
                    anchors.fill: parent

                    Image {
                        id: grayThumb
                        anchors.fill: parent
                        source: root.resolvedImageSource
                        fillMode: Image.PreserveAspectCrop
                        asynchronous: true
                        cache: true
                        visible: root.imageSource !== ""
                        opacity: 0.45
                    }

                    Item {
                        anchors.bottom: parent.bottom
                        width: parent.width
                        height: parent.height * root.revealFraction
                        clip: true
                        visible: root.imageSource !== "" && root.revealFraction > 0

                        Image {
                            anchors.bottom: parent.bottom
                            width: parent.width
                            height: thumbBlock.height
                            source: root.resolvedImageSource
                            fillMode: Image.PreserveAspectCrop
                            asynchronous: true
                            cache: true
                        }
                    }

                    Rectangle {
                        anchors.fill: parent
                        visible: root.imageSource === "" || grayThumb.status !== Image.Ready
                        color: Theme.bgElevated

                        AppIcon {
                            anchors.centerIn: parent
                            name: "videocam"
                            font.pixelSize: 28
                            color: Theme.textMuted
                        }
                    }

                    Rectangle {
                        anchors.left: parent.left
                        anchors.right: parent.right
                        anchors.bottom: parent.bottom
                        height: 3
                        visible: root.isDownloading && !root.inLibrary
                        color: Theme.accentStart
                        opacity: 0.9
                    }
                }

                Rectangle {
                    anchors.fill: parent
                    color: "#000000"
                    opacity: root.hovered ? 0.08 : 0
                    radius: Theme.libraryCardRadius

                    Behavior on opacity {
                        NumberAnimation { duration: 100 }
                    }
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

            Text {
                width: parent.width
                visible: !root.inLibrary && !root.isSeries
                text: root.isDownloading
                    ? ("Đang tải " + Math.round(root.downloadPercent) + "%")
                    : "Nhấp đúp để tải"
                color: Theme.textMuted
                font.family: Theme.fontFamily
                font.pixelSize: Theme.captionSize
                elide: Text.ElideRight
            }
            Text {
                width: parent.width
                visible: root.isSeries
                text: root.isDownloading
                    ? ("Đang tải " + Math.round(root.downloadPercent) + "%")
                    : "Nhấp để chọn tập"
                color: Theme.textMuted
                font.family: Theme.fontFamily
                font.pixelSize: Theme.captionSize
                elide: Text.ElideRight
            }
        }
    }

    TapHandler {
        gesturePolicy: TapHandler.DragWithinBounds
        onTapped: {
            if (root.isSeries || root.inLibrary)
                root.playRequested()
        }
        onDoubleTapped: {
            if (!root.isSeries)
                root.downloadRequested()
        }
    }

    MouseArea {
        id: hoverMa
        anchors.fill: parent
        acceptedButtons: Qt.RightButton
        onClicked: function(mouse) {
            if (mouse.button === Qt.RightButton)
                root.contextMenuRequested(mouse.x, mouse.y)
        }
    }

    HoverHandler {
        id: hoverHandler
        onHoveredChanged: root.hovered = hovered
    }
}
