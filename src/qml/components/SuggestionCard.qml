import QtQuick
import QtQuick.Controls
import Liminal 1.0

Item {
    id: root

    property string title: ""
    property string subtitle: ""
    property string imageSource: ""
    property string categoryLabel: ""
    property real downloadPercent: 0
    property string downloadStatus: "pending"
    property bool isDownloading: false
    property bool audioOnly: false

    readonly property bool inLibrary: downloadStatus === "done"
    readonly property string resolvedImageSource: {
        if (!imageSource)
            return ""
        if (imageSource.startsWith("http://") || imageSource.startsWith("https://") || imageSource.startsWith("file://"))
            return imageSource
        return "file://" + imageSource
    }
    readonly property real revealFraction: inLibrary
        ? 1
        : Math.max(0, Math.min(1, downloadPercent / 100))

    signal downloadRequested()

    width: implicitWidth
    height: thumbBlock.height + textBlock.implicitHeight

    HoverHandler {
        id: hoverHandler
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
                radius: Theme.libraryCardRadius
                clip: true
                color: Theme.cardBg
                border.color: hoverHandler.hovered ? Theme.accentStart : Theme.cardBg
                border.width: 2

                Behavior on border.color {
                    ColorAnimation { duration: 100 }
                }

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
                    id: hoverOverlay
                    anchors.fill: parent
                    opacity: hoverHandler.hovered ? 0.08 : 0
                    color: "black"
                    radius: Theme.libraryCardRadius

                    Behavior on opacity {
                        NumberAnimation { duration: 100 }
                    }
                }

                Rectangle {
                    anchors.fill: parent
                    visible: root.imageSource === "" || grayThumb.status !== Image.Ready
                    color: Theme.bgElevated

                    AppIcon {
                        anchors.centerIn: parent
                        name: root.audioOnly ? "podcasts" : "videocam"
                        font.pixelSize: 28
                        color: Theme.textMuted
                    }
                }

                Rectangle {
                    anchors.left: parent.left
                    anchors.top: parent.top
                    anchors.margins: 8
                    visible: root.categoryLabel.length > 0
                    radius: 6
                    color: Qt.rgba(0, 0, 0, 0.55)
                    width: categoryText.implicitWidth + 12
                    height: categoryText.implicitHeight + 6

                    Text {
                        id: categoryText
                        anchors.centerIn: parent
                        text: root.categoryLabel
                        color: Theme.textPrimary
                        font.family: Theme.fontFamily
                        font.pixelSize: Theme.captionSize
                        font.weight: Font.Medium
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
                text: root.inLibrary
                    ? "Chạm để phát"
                    : (root.isDownloading
                        ? ("Đang tải " + Math.round(root.downloadPercent) + "%")
                        : "Chạm để tải về")
                color: root.inLibrary ? Theme.accentStart : Theme.textMuted
                font.family: Theme.fontFamily
                font.pixelSize: Theme.captionSize
            }
        }
    }

    MouseArea {
        id: hoverMa
        anchors.fill: parent
        cursorShape: Qt.PointingHandCursor
        onClicked: {
            if (root.isDownloading)
                return
            root.downloadRequested()
        }
    }
}
