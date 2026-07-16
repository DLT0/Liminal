import QtQuick
import QtQuick.Controls
import Liminal 1.0

// Card podcast: bìa 16:9 (đồng bộ với video), text block bên dưới.
// Kích thước do parent (PodcastSuggestionsSection) truyền qua anchors.fill.
Item {
    id: root

    property string title: ""
    property string subtitle: ""
    property string categoryLabel: ""
    property string imageSource: ""

    // Tiến độ nghe (0–100) — hiện thanh mỏng đáy cover
    property real progressPercent: 0

    // Trạng thái tải xuống
    property real downloadPercent: 0
    property string downloadStatus: "idle"   // idle | pending | downloading | done
    property bool isDownloading: false
    property bool audioOnly: true
    property string trackId: ""
    property bool clickEnabled: true

    signal clicked()
    signal downloadRequested()

    // ── Internals ──────────────────────────────────────────────────────────────
    readonly property bool inLibrary:    downloadStatus === "done"
    readonly property bool showProgress: progressPercent > 0 && progressPercent < 100

    readonly property string resolvedImageSource: {
        if (!imageSource) return ""
        if (imageSource.startsWith("http://") || imageSource.startsWith("https://")
                || imageSource.startsWith("file://"))
            return imageSource
        return "file://" + imageSource
    }

    // Tỷ lệ cover: luôn 16:9 — đồng bộ định dạng hình ảnh giữa audio và video
    readonly property real coverAspect: Theme.videoPosterAspect

    // ── Layout: cover (1:1) + text block ──────────────────────────────────────
    Column {
        width: parent.width
        spacing: 10

        // Cover art — tỷ lệ 16:9 cho video, 1:1 cho audio
        Item {
            id: artBlock
            width: parent.width
            height: Math.round(width / root.coverAspect)

            Rectangle {
                anchors.fill: parent
                clip: true
                color: Theme.cardBg

                readonly property real revealFraction: root.inLibrary
                    ? 1
                    : Math.max(0, Math.min(1, root.downloadPercent / 100))

                // Cover image (grayed out)
                Image {
                    id: grayThumb
                    anchors.fill: parent
                    source: root.resolvedImageSource
                    fillMode: Image.PreserveAspectCrop
                    asynchronous: true
                    cache: true
                    visible: root.imageSource !== ""
                    opacity: root.inLibrary ? 1.0 : 0.45
                    sourceSize.width:  Math.max(128, Math.round(artBlock.width))
                    sourceSize.height: Math.max(128, Math.round(artBlock.height))
                }

                // Colored reveal overlay
                Item {
                    anchors.bottom: parent.bottom
                    width: parent.width
                    height: parent.height * parent.revealFraction
                    clip: true
                    visible: root.imageSource !== "" && parent.revealFraction > 0 && !root.inLibrary

                    Image {
                        anchors.bottom: parent.bottom
                        width: parent.width
                        height: artBlock.height
                        source: root.resolvedImageSource
                        fillMode: Image.PreserveAspectCrop
                        asynchronous: true
                        cache: true
                        sourceSize.width:  Math.max(128, Math.round(artBlock.width))
                        sourceSize.height: Math.max(128, Math.round(artBlock.height))
                    }
                }

                // Placeholder icon khi không có ảnh
                Rectangle {
                    anchors.fill: parent
                    visible: root.imageSource === ""
                    color: Theme.bgElevated

                    AppIcon {
                        anchors.centerIn: parent
                        name: root.audioOnly ? "podcasts" : "videocam"
                        font.pixelSize: Math.max(24, Math.round(artBlock.width * 0.22))
                        color: Theme.textMuted
                        opacity: 0.6
                    }
                }

                // Thanh tiến độ nghe (mỏng ở đáy cover)
                Rectangle {
                    anchors.left: parent.left
                    anchors.right: parent.right
                    anchors.bottom: parent.bottom
                    height: 3
                    visible: root.showProgress
                    color: Qt.rgba(1, 1, 1, 0.12)
                    z: 4

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
                    z: 5

                    Behavior on opacity {
                        NumberAnimation { duration: 100 }
                    }
                }

            }

        }

        // Text block — title + subtitle (đồng nhất với SuggestionCard/VinylCard)
        Column {
            id: textBlock
            width: parent.width
            spacing: 4

            Text {
                width: parent.width
                text: root.title
                color: Theme.textPrimary
                font.family: Theme.fontFamily
                font.pixelSize: Theme.bodySize      // 13px — khớp SuggestionCard
                font.weight: Font.Medium
                wrapMode: Text.Wrap
                maximumLineCount: 2
                elide: Text.ElideRight
            }

            Text {
                width: parent.width
                text: {
                    var parts = []
                    if (root.subtitle) parts.push(root.subtitle)
                    if (root.categoryLabel) parts.push(root.categoryLabel)
                    return parts.join(" • ")
                }
                color: Theme.textSecondary        // đồng nhất với SuggestionCard
                font.family: Theme.fontFamily
                font.pixelSize: Theme.captionSize  // 11px — khớp SuggestionCard
                elide: Text.ElideRight
            }

            // Dòng trạng thái — chỉ hiển thị khi không hover (hover đã dùng overlay)
            Text {
                width: parent.width
                visible: root.inLibrary || root.isDownloading
                text: root.isDownloading
                    ? "Đang tải " + Math.round(root.downloadPercent) + "%"
                    : root.inLibrary ? "✓ Đã xem" : ""
                color: root.inLibrary ? Theme.accentStart : Theme.textMuted
                font.family: Theme.fontFamily
                font.pixelSize: Theme.captionSize
                elide: Text.ElideRight
            }
        }
    }

    signal contextMenuRequested(real x, real y)

    HoverHandler {
        id: hoverHandler
    }

    // Border — changes to accent on hover
    Rectangle {
        anchors.fill: parent
        color: "transparent"
        border.color: hoverHandler.hovered ? Theme.accentStart : Theme.cardBorder
        border.width: 1

        Behavior on border.color {
            ColorAnimation { duration: 100 }
        }
    }

    MouseArea {
        id: hoverMa
        anchors.fill: parent
        enabled: root.clickEnabled
        acceptedButtons: Qt.LeftButton | Qt.RightButton
        cursorShape: Qt.PointingHandCursor
        onClicked: function(mouse) {
            if (mouse.button === Qt.RightButton) {
                root.contextMenuRequested(mouse.x, mouse.y)
                return
            }
            if (root.isDownloading) return
            if (root.inLibrary || root.progressPercent > 0)
                root.clicked()
            else
                root.downloadRequested()
        }
    }
}
