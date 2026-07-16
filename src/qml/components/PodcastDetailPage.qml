import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import Liminal 1.0

// Podcast chi tiết — giao diện kiểu "phim lẻ" với hero banner Netflix-style
Item {
    id: root
    clip: true

    property alias model: episodeList.model
    property string showTitle: ""
    property string showImage: ""
    property string showDescription: ""
    property string showAuthor: ""
    property int feedIndex: -1

    signal backClicked()
    signal episodeClicked(int index)
    signal downloadRequested(string feedUrl, string guid)

    readonly property string resolvedBannerImage: {
        if (!showImage)
            return ""
        if (showImage.startsWith("http://") || showImage.startsWith("https://") || showImage.startsWith("file://"))
            return showImage
        return "file://" + showImage
    }
    readonly property int heroHeight: Math.min(460, Math.max(340, Math.round(height * 0.55)))

    // ── Sticky header bar ─────────────────────────────────────────────────
    Rectangle {
        id: stickyBar
        anchors.top: parent.top
        anchors.left: parent.left
        anchors.right: parent.right
        height: 56
        z: 10
        visible: scrollView.contentY > root.heroHeight - 72
        color: Theme.bgBase
        border.color: Theme.border
        border.width: 1

        Row {
            anchors.fill: parent
            anchors.leftMargin: 12
            anchors.rightMargin: 20
            spacing: 8

            IconButton {
                anchors.verticalCenter: parent.verticalCenter
                icon: "arrow_back"
                onClicked: root.backClicked()
            }

            Text {
                anchors.verticalCenter: parent.verticalCenter
                width: parent.width - 96
                text: root.showTitle
                font.family: Theme.fontFamily
                font.pixelSize: 16
                font.weight: Font.Bold
                color: Theme.textPrimary
                elide: Text.ElideRight
            }
        }
    }

    Flickable {
        id: scrollView
        anchors.fill: parent
        clip: true
        boundsBehavior: Flickable.StopAtBounds
        contentWidth: width
        contentHeight: podcastHero.height + bodyColumn.implicitHeight
        interactive: contentHeight > height

        ScrollBar.vertical: ScrollBar { policy: ScrollBar.AsNeeded }

        WheelHandler {
            target: scrollView
            onWheel: function(event) {
                var delta = event.pixelDelta.y
                if (delta === 0)
                    delta = event.angleDelta.y / 2
                if (delta === 0 || !scrollView.interactive)
                    return
                var maximum = Math.max(0, scrollView.contentHeight - scrollView.height)
                scrollView.contentY = Math.max(0, Math.min(maximum,
                    scrollView.contentY - delta))
                event.accepted = true
            }
        }

        // ── Hero banner ───────────────────────────────────────────────────
        Item {
            id: podcastHero
            width: scrollView.width
            height: root.heroHeight

            Item {
                anchors.fill: parent
                clip: true

                Item {
                    width: parent.width
                    height: parent.height + 80
                    y: Math.min(0, -scrollView.contentY * 0.35)

                    Image {
                        anchors.fill: parent
                        source: root.resolvedBannerImage
                        fillMode: Image.PreserveAspectCrop
                        visible: root.showImage !== ""
                    }
                }
            }

            Rectangle {
                anchors.fill: parent
                visible: root.showImage === ""
                color: "#1a1a1a"
            }

            Rectangle {
                anchors.fill: parent
                gradient: Gradient {
                    GradientStop { position: 0.0; color: "#33000000" }
                    GradientStop { position: 0.55; color: "#99000000" }
                    GradientStop { position: 1.0; color: Theme.bgBase }
                }
            }

            Rectangle {
                anchors.fill: parent
                gradient: Gradient {
                    orientation: Gradient.Horizontal
                    GradientStop { position: 0.0; color: "#cc000000" }
                    GradientStop { position: 0.42; color: "#66000000" }
                    GradientStop { position: 0.75; color: "transparent" }
                }
            }

            IconButton {
                x: 20
                y: 20
                icon: "arrow_back"
                iconColor: "#ffffff"
                bordered: true
                width: 40
                height: 40
                onClicked: root.backClicked()
            }

            Column {
                anchors.left: parent.left
                anchors.right: parent.right
                anchors.bottom: parent.bottom
                anchors.margins: 32
                anchors.rightMargin: Math.max(32, scrollView.width * 0.35)
                spacing: 10

                Row {
                    spacing: 6
                    width: parent.width

                    Text {
                        text: "PODCAST"
                        font.family: Theme.fontFamily
                        font.pixelSize: Theme.captionSize
                        font.weight: Font.Bold
                        color: Theme.accentStart
                    }

                    Text {
                        visible: root.showAuthor.length > 0
                        text: "· " + root.showAuthor
                        font.family: Theme.fontFamily
                        font.pixelSize: Theme.captionSize
                        color: "#d6d6d6"
                    }
                }

                Text {
                    width: parent.width
                    text: root.showTitle
                    font.family: Theme.fontFamily
                    font.pixelSize: Math.min(48, Math.max(28, scrollView.width * 0.038))
                    font.weight: Font.Black
                    color: "#ffffff"
                    wrapMode: Text.Wrap
                    maximumLineCount: 3
                    elide: Text.ElideRight
                }
            }
        }

        // ── Body ──────────────────────────────────────────────────────────
        Column {
            id: bodyColumn
            width: scrollView.width
            y: podcastHero.height - 24
            spacing: 20
            topPadding: 0
            bottomPadding: 32

            // Action row
            Row {
                width: parent.width - 64
                x: 32
                spacing: 12

                Rectangle {
                    id: primaryPlayBtn
                    height: 44
                    width: playBtnRow.implicitWidth + 28
                    radius: 4
                    color: episodeList.count > 0 ? "#ffffff" : "#666666"

                    Row {
                        id: playBtnRow
                        anchors.centerIn: parent
                        spacing: 8

                        AppIcon {
                            anchors.verticalCenter: parent.verticalCenter
                            name: "play_arrow"
                            filled: true
                            font.pixelSize: 28
                            color: "#000000"
                        }

                        Text {
                            anchors.verticalCenter: parent.verticalCenter
                            text: "Phát tập mới nhất"
                            font.family: Theme.fontFamily
                            font.pixelSize: 16
                            font.weight: Font.Bold
                            color: "#000000"
                        }
                    }

                    MouseArea {
                        anchors.fill: parent
                        cursorShape: Qt.PointingHandCursor
                        enabled: episodeList.count > 0
                        onClicked: root.episodeClicked(0)
                    }
                }
            }

            // Description
            Column {
                width: parent.width - 64
                x: 32
                spacing: 8
                visible: root.showDescription.length > 0

                Text {
                    width: parent.width
                    text: root.showDescription
                    font.family: Theme.fontFamily
                    font.pixelSize: Theme.bodySize
                    color: Theme.textSecondary
                    wrapMode: Text.WordWrap
                    lineHeight: 1.35
                    maximumLineCount: 4
                    elide: Text.ElideRight
                }
            }

            // Episode count header
            Text {
                x: 32
                text: episodeList.count + " tập"
                font.family: Theme.fontFamily
                font.pixelSize: 18
                font.weight: Font.Bold
                color: Theme.textPrimary
            }

            // Episode list — vertical, 16:9 thumbnails như phim bộ
            ListView {
                id: episodeList
                width: parent.width
                height: contentHeight
                interactive: false
                spacing: 4

                delegate: Item {
                    id: episodeRow
                    required property int index
                    required property string title
                    required property string subtitle
                    required property string artist
                    required property string path
                    required property string imageSource
                    required property string duration
                    required property string downloadStatus
                    required property bool isDownloading
                    required property real downloadPercent
                    required property string podcastFeedUrl
                    required property string podcastGuid
                    required property real watchedPercent

                    width: episodeList.width
                    height: 108
                    clip: true

                    readonly property string resolvedRowImage: {
                        if (!imageSource)
                            return ""
                        if (imageSource.startsWith("http://") || imageSource.startsWith("https://") || imageSource.startsWith("file://"))
                            return imageSource
                        return "file://" + imageSource
                    }

                    readonly property string episodeTitle: {
                        if (title && title.length > 0)
                            return title
                        return "Tập " + (index + 1)
                    }

                    HoverHandler {
                        id: epHover
                        cursorShape: Qt.PointingHandCursor
                    }

                    Rectangle {
                        id: rowBg
                        anchors.fill: parent
                        anchors.leftMargin: 24
                        anchors.rightMargin: 24
                        radius: 6
                        color: epHover.hovered ? Theme.bgElevated : "transparent"
                        border.color: "transparent"
                        border.width: 1

                        Behavior on color {
                            ColorAnimation { duration: 100 }
                        }

                        TapHandler {
                            onTapped: {
                                console.log("[DEBUG PodcastDetailPage] tapped episode index=" + index + " title=" + title + " feedUrl=" + podcastFeedUrl + " guid=" + podcastGuid + " downloadStatus=" + downloadStatus)
                                if (downloadStatus === "done") {
                                    root.episodeClicked(index)
                                } else if (!isDownloading) {
                                    console.log("[DEBUG PodcastDetailPage] firing downloadRequested for guid=" + podcastGuid)
                                    root.downloadRequested(podcastFeedUrl, podcastGuid)
                                }
                            }
                        }

                        MouseArea {
                            anchors.fill: parent
                            acceptedButtons: Qt.RightButton
                            z: -1
                            onClicked: function(mouse) {
                                if (!isDownloading && downloadStatus !== "done") {
                                    root.downloadRequested(podcastFeedUrl, podcastGuid)
                                }
                            }
                        }

                        Row {
                            anchors.fill: parent
                            anchors.margins: 10
                            spacing: 16

                            // 16:9 thumbnail
                            Item {
                                width: 160
                                height: 88
                                anchors.verticalCenter: parent.verticalCenter

                                Rectangle {
                                    anchors.fill: parent
                                    radius: 4
                                    color: Theme.cardBg
                                    clip: true

                                    readonly property real revealFraction: downloadStatus === "done"
                                        ? 1
                                        : Math.max(0, Math.min(1, downloadPercent / 100))

                                    Image {
                                        id: grayThumb
                                        anchors.fill: parent
                                        source: resolvedRowImage
                                        fillMode: Image.PreserveAspectCrop
                                        visible: imageSource !== ""
                                        opacity: downloadStatus === "done" ? 1.0 : 0.45
                                    }

                                    Item {
                                        anchors.bottom: parent.bottom
                                        width: parent.width
                                        height: parent.height * parent.revealFraction
                                        clip: true
                                        visible: imageSource !== "" && parent.revealFraction > 0 && downloadStatus !== "done"

                                        Image {
                                            anchors.bottom: parent.bottom
                                            width: parent.parent.width
                                            height: parent.parent.height
                                            source: resolvedRowImage
                                            fillMode: Image.PreserveAspectCrop
                                        }
                                    }

                                    Rectangle {
                                        anchors.fill: parent
                                        visible: imageSource === ""
                                        color: Theme.bgElevated

                                        Text {
                                            anchors.centerIn: parent
                                            text: index + 1
                                            font.family: Theme.fontFamily
                                            font.pixelSize: 24
                                            font.weight: Font.Bold
                                            color: Theme.textMuted
                                        }
                                    }

                                }
                            }

                            Column {
                                anchors.verticalCenter: parent.verticalCenter
                                width: parent.width - 220
                                spacing: 6

                                Row {
                                    spacing: 8
                                    width: parent.width

                                    Text {
                                        text: (index + 1) + ". " + episodeTitle
                                        font.family: Theme.fontFamily
                                        font.pixelSize: 15
                                        font.weight: Font.Bold
                                        color: Theme.textPrimary
                                        elide: Text.ElideRight
                                        width: parent.width - (epDuration.visible ? epDuration.implicitWidth + 8 : 0)
                                    }

                                    Text {
                                        id: epDuration
                                        visible: duration.length > 0
                                        text: duration
                                        font.family: Theme.fontFamily
                                        font.pixelSize: Theme.captionSize
                                        color: Theme.textMuted
                                    }
                                }

                                Text {
                                    width: parent.width
                                    visible: subtitle.length > 0
                                    text: subtitle
                                    font.family: Theme.fontFamily
                                    font.pixelSize: Theme.captionSize
                                    color: Theme.textSecondary
                                    elide: Text.ElideRight
                                }

                                // Download status / action hint
                                Text {
                                    width: parent.width
                                    visible: downloadStatus !== "done" || isDownloading
                                    text: isDownloading
                                        ? ("Đang tải " + Math.round(downloadPercent) + "%")
                                        : (downloadStatus === "done" ? "" : "Nhấp để tải xuống")
                                    font.family: Theme.fontFamily
                                    font.pixelSize: Theme.captionSize
                                    color: isDownloading ? Theme.accentStart : Theme.textMuted
                                }

                                // Listened progress
                                Rectangle {
                                    width: parent.width
                                    height: 3
                                    radius: 2
                                    color: Theme.inputBg
                                    visible: watchedPercent > 0 && watchedPercent < 100 && !isDownloading

                                    Rectangle {
                                        width: parent.width * (watchedPercent / 100)
                                        height: parent.height
                                        radius: 2
                                        color: Theme.accentStart
                                    }
                                }
                            }
                        }
                    }
                }
            }
        }
    }
}
