import QtQuick
import QtQuick.Controls
import Liminal 1.0

// Card tập podcast đã tải: cover vuông, tên tập, show, progress nghe dở.
Item {
    id: root

    property string title: ""
    property string subtitle: ""
    property string imageSource: ""
    property real progressPercent: 0
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
    readonly property bool showProgress: progressPercent > 0 && progressPercent < 100

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
                anchors.fill: parent
                radius: Theme.podcastCardRadius
                clip: true
                color: Theme.cardBg

                Image {
                    anchors.fill: parent
                    source: root.resolvedImageSource
                    fillMode: Image.PreserveAspectCrop
                    asynchronous: true
                    cache: true
                    visible: root.imageSource !== ""
                }

                Rectangle {
                    anchors.fill: parent
                    visible: root.imageSource === ""
                    color: Theme.bgElevated

                    AppIcon {
                        anchors.centerIn: parent
                        name: "podcasts"
                        font.pixelSize: 28
                        color: Theme.textMuted
                    }
                }

                // Progress nghe dở — thanh mỏng đáy cover
                Rectangle {
                    anchors.left: parent.left
                    anchors.right: parent.right
                    anchors.bottom: parent.bottom
                    height: 3
                    visible: root.showProgress
                    color: Qt.rgba(1, 1, 1, 0.15)

                    Rectangle {
                        width: parent.width * Math.max(0, Math.min(1, root.progressPercent / 100))
                        height: parent.height
                        color: Theme.accentStart
                    }
                }

                // White overlay on hover
                Rectangle {
                    anchors.fill: parent
                    color: "#FFFFFF"
                    opacity: hoverHandler.hovered ? 0.08 : 0

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
        }
    }

    HoverHandler {
        id: hoverHandler
    }

    MouseArea {
        id: hoverMa
        anchors.fill: parent
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
}
