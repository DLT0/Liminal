import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import Liminal 1.0

// Podcast playlist chi tiết — giao diện kiểu "phim bộ" với hero banner + danh sách tập dọc
Item {
    id: root
    clip: true

    property alias model: root.rawModel
    property var rawModel: null
    property string playlistTitle: ""
    property string playlistImage: ""
    property string statusMessage: ""

    property int selectedSeason: seasonsList.length > 1 ? seasonsList[0] : 0

    signal backClicked()
    signal episodeClicked(int index)
    signal downloadRequested(int index)
    signal aiSortRequested()

    // ── Helpers ───────────────────────────────────────────────────────────
    QtObject {
        id: helpers

        function formatDuration(seconds) {
            if (!seconds || seconds <= 0) return ""
            var h = Math.floor(seconds / 3600)
            var m = Math.floor((seconds % 3600) / 60)
            var s = Math.floor(seconds % 60)
            var mStr = m < 10 ? "0" + m : m
            var sStr = s < 10 ? "0" + s : s
            if (h > 0) {
                var hStr = h < 10 ? "0" + h : h
                return hStr + ":" + mStr + ":" + sStr
            }
            return mStr + ":" + sStr
        }
    }

    readonly property string resolvedBannerImage: {
        if (!playlistImage)
            return ""
        if (playlistImage.startsWith("http://") || playlistImage.startsWith("https://") || playlistImage.startsWith("file://"))
            return playlistImage
        return "file://" + playlistImage
    }
    readonly property int heroHeight: Math.min(500, Math.max(360, Math.round(height * 0.58)))

    // ── Seasons ───────────────────────────────────────────────────────────
    property var seasonsList: {
        var list = []
        var seen = {}
        var count = root.rawModel ? root.rawModel.count : 0
        for (var i = 0; i < count; i++) {
            var it = root.rawModel.item_at(i)
            if (it && it.season !== undefined) {
                var s = parseInt(it.season) || 0
                if (s > 0 && !seen[s]) {
                    seen[s] = true
                    list.push(s)
                }
            }
        }
        list.sort(function(a, b) { return a - b })
        return list
    }

    property string playlistDescription: {
        var count = root.rawModel ? root.rawModel.count : 0
        for (var i = 0; i < count; i++) {
            var it = root.rawModel.item_at(i)
            if (it && it.description) return it.description
        }
        return ""
    }

    property var filteredEpisodes: {
        var list = []
        var count = root.rawModel ? root.rawModel.count : 0
        for (var i = 0; i < count; i++) {
            var it = root.rawModel.item_at(i)
            if (it) {
                var itSeason = parseInt(it.season) || 1
                if (root.seasonsList.length > 1 && root.selectedSeason > 0) {
                    if (itSeason !== root.selectedSeason) continue
                }
                list.push({
                    title: it.title || "",
                    subtitle: it.subtitle || "",
                    image: it.image || "",
                    download_percent: it.download_percent || 0,
                    download_status: it.download_status || "idle",
                    is_downloading: it.is_downloading || false,
                    audio_only: it.audio_only !== undefined ? it.audio_only : true,
                    listened_position: it.listened_position || 0,
                    duration_seconds: it.duration_seconds || 0,
                    watched_percent: it.watched_percent || 0,
                    originalIndex: i
                })
            }
        }
        list.sort(function(a, b) {
            var epA = root.rawModel.item_at(a.originalIndex).episode || 0
            var epB = root.rawModel.item_at(b.originalIndex).episode || 0
            return epA - epB
        })
        return list
    }

    readonly property int episodeCount: root.rawModel ? root.rawModel.count : 0

    // ── Sticky header bar ─────────────────────────────────────────────────
    Rectangle {
        id: stickyBar
        anchors.top: parent.top
        anchors.left: parent.left
        anchors.right: parent.right
        height: 56
        z: 10
        visible: netflixScroll.contentY > root.heroHeight - 72
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
                text: root.playlistTitle
                font.family: Theme.fontFamily
                font.pixelSize: 16
                font.weight: Font.Bold
                color: Theme.textPrimary
                elide: Text.ElideRight
            }
        }
    }

    Flickable {
        id: netflixScroll
        anchors.fill: parent
        clip: true
        boundsBehavior: Flickable.StopAtBounds
        contentWidth: width
        contentHeight: netflixHero.height + netflixBody.implicitHeight
        interactive: contentHeight > height

        ScrollBar.vertical: ScrollBar { policy: ScrollBar.AsNeeded }

        WheelHandler {
            target: netflixScroll
            onWheel: function(event) {
                var delta = event.pixelDelta.y
                if (delta === 0)
                    delta = event.angleDelta.y / 2
                if (delta === 0 || !netflixScroll.interactive)
                    return
                var maximum = Math.max(0, netflixScroll.contentHeight - netflixScroll.height)
                netflixScroll.contentY = Math.max(0, Math.min(maximum,
                    netflixScroll.contentY - delta))
                event.accepted = true
            }
        }

        // ── Hero banner ───────────────────────────────────────────────────
        Item {
            id: netflixHero
            width: netflixScroll.width
            height: root.heroHeight

            Item {
                anchors.fill: parent
                clip: true

                Item {
                    width: parent.width
                    height: parent.height + 80
                    y: Math.min(0, -netflixScroll.contentY * 0.35)

                    Image {
                        anchors.fill: parent
                        source: root.resolvedBannerImage
                        fillMode: Image.PreserveAspectCrop
                        visible: root.playlistImage !== ""
                    }
                }
            }

            Rectangle {
                anchors.fill: parent
                visible: root.playlistImage === ""
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
                anchors.rightMargin: Math.max(32, netflixScroll.width * 0.35)
                spacing: 10

                Row {
                    spacing: 6
                    width: parent.width

                    Text {
                        text: "PODCAST PLAYLIST"
                        font.family: Theme.fontFamily
                        font.pixelSize: Theme.captionSize
                        font.weight: Font.Bold
                        color: Theme.accentStart
                    }
                }

                Text {
                    width: parent.width
                    text: root.playlistTitle
                    font.family: Theme.fontFamily
                    font.pixelSize: Math.min(52, Math.max(32, netflixScroll.width * 0.04))
                    font.weight: Font.Black
                    color: "#ffffff"
                    wrapMode: Text.Wrap
                    maximumLineCount: 3
                    elide: Text.ElideRight
                }

                Text {
                    width: parent.width
                    visible: root.episodeCount > 0
                    text: root.episodeCount + " tập"
                    font.family: Theme.fontFamily
                    font.pixelSize: Theme.bodySize
                    color: "#d6d6d6"
                    elide: Text.ElideRight
                }
            }
        }

        // ── Body ──────────────────────────────────────────────────────────
        Column {
            id: netflixBody
            width: netflixScroll.width
            y: netflixHero.height - 24
            spacing: 20
            topPadding: 0
            bottomPadding: 32

            // Action buttons
            Row {
                width: parent.width - 64
                x: 32
                spacing: 12

                Rectangle {
                    id: primaryPlayBtn
                    height: 44
                    width: playBtnRow.implicitWidth + 28
                    radius: 4
                    color: root.episodeCount > 0 ? "#ffffff" : "#666666"

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
                            text: "Phát"
                            font.family: Theme.fontFamily
                            font.pixelSize: 16
                            font.weight: Font.Bold
                            color: "#000000"
                        }
                    }

                    MouseArea {
                        anchors.fill: parent
                        cursorShape: Qt.PointingHandCursor
                        enabled: root.episodeCount > 0
                        onClicked: root.episodeClicked(0)
                    }
                }

                IconButton {
                    anchors.verticalCenter: parent.verticalCenter
                    icon: "shuffle"
                    iconSize: 22
                    iconColor: "#ffffff"
                    bordered: true
                    width: 44
                    height: 44
                    visible: root.episodeCount > 1
                    onClicked: {
                        // Play random episode
                        var idx = Math.floor(Math.random() * root.filteredEpisodes.length)
                        var origIdx = root.filteredEpisodes[idx].originalIndex
                        root.episodeClicked(origIdx)
                    }
                }

                IconButton {
                    anchors.verticalCenter: parent.verticalCenter
                    icon: "auto_fix"
                    iconSize: 22
                    iconColor: "#ffffff"
                    bordered: true
                    width: 44
                    height: 44
                    opacity: backend.podcastPlaylistAiSortLoading ? 0.45 : 1
                    enabled: !backend.podcastPlaylistAiSortLoading && root.episodeCount >= 2
                    onClicked: root.aiSortRequested()
                }
            }

            // Description
            Column {
                width: parent.width - 64
                x: 32
                spacing: 8
                visible: root.playlistDescription.length > 0

                Text {
                    width: parent.width
                    text: root.playlistDescription
                    font.family: Theme.fontFamily
                    font.pixelSize: Theme.bodySize
                    color: Theme.textSecondary
                    wrapMode: Text.WordWrap
                    maximumLineCount: 4
                    elide: Text.ElideRight
                }
            }

            // AI status message
            Text {
                x: 32
                visible: root.statusMessage !== ""
                text: root.statusMessage
                font.family: Theme.fontFamily
                font.pixelSize: Theme.captionSize
                color: Theme.accentStart
                wrapMode: Text.WordWrap
                width: parent.width - 64
            }

            // Season selector pills (≤ 6 seasons)
            Row {
                id: seasonRow
                x: 32
                width: parent.width - 64
                spacing: 8
                visible: root.seasonsList.length > 1 && root.seasonsList.length <= 6
                height: visible ? 36 : 0

                Repeater {
                    model: root.seasonsList

                    Rectangle {
                        required property int modelData
                        height: 32
                        width: seasonLabel.implicitWidth + 20
                        radius: 4
                        color: root.selectedSeason === modelData ? "#ffffff" : "#333333"
                        border.color: root.selectedSeason === modelData ? "#ffffff" : "#555555"
                        border.width: 1

                        Text {
                            id: seasonLabel
                            anchors.centerIn: parent
                            text: "Mùa " + parent.modelData
                            font.family: Theme.fontFamily
                            font.pixelSize: Theme.bodySize
                            font.weight: root.selectedSeason === parent.modelData ? Font.Bold : Font.Normal
                            color: root.selectedSeason === parent.modelData ? "#000000" : "#ffffff"
                        }

                        MouseArea {
                            anchors.fill: parent
                            cursorShape: Qt.PointingHandCursor
                            onClicked: root.selectedSeason = parent.modelData
                        }
                    }
                }
            }

            // Season dropdown (> 6 seasons)
            StyledComboBox {
                id: seasonCombo
                x: 32
                width: Math.min(220, parent.width - 64)
                visible: root.seasonsList.length > 6
                model: root.seasonsList.map(function(s) { return "Mùa " + s })
                currentIndex: {
                    var idx = root.seasonsList.indexOf(root.selectedSeason)
                    return idx >= 0 ? idx : 0
                }
                onActivated: function(index) {
                    if (index >= 0 && index < root.seasonsList.length)
                        root.selectedSeason = root.seasonsList[index]
                }
            }

            // Episode section header
            Text {
                x: 32
                text: root.seasonsList.length > 1 ? ("Tập · Mùa " + root.selectedSeason) : "Danh sách tập"
                font.family: Theme.fontFamily
                font.pixelSize: 18
                font.weight: Font.Bold
                color: Theme.textPrimary
            }

            // Episode list — vertical với 16:9 thumbnail như phim bộ
            ListView {
                id: episodeListView
                width: parent.width
                height: contentHeight
                interactive: false
                spacing: 4
                model: root.filteredEpisodes

                delegate: Item {
                    id: episodeRow
                    required property int index
                    required property var modelData

                    width: episodeListView.width
                    height: 108
                    clip: true

                    HoverHandler {
                        id: epHover
                        cursorShape: Qt.PointingHandCursor
                    }

                    readonly property string resolvedRowImage: {
                        var img = modelData.image || ""
                        if (!img) return ""
                        if (img.startsWith("http://") || img.startsWith("https://") || img.startsWith("file://"))
                            return img
                        return "file://" + img
                    }

                    readonly property int epNumber: {
                        var origIdx = modelData.originalIndex
                        var it = root.rawModel.item_at(origIdx)
                        return (it && it.episode > 0) ? it.episode : (index + 1)
                    }

                    readonly property string epTitle: {
                        return modelData.title || ("Tập " + epNumber)
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
                                if (modelData.download_status !== "done" && !modelData.is_downloading)
                                    root.downloadRequested(modelData.originalIndex)
                                else
                                    root.episodeClicked(modelData.originalIndex)
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

                                    readonly property real revealFraction: modelData.download_status === "done"
                                        ? 1
                                        : Math.max(0, Math.min(1, (modelData.download_percent || 0) / 100))

                                    Image {
                                        id: grayThumb
                                        anchors.fill: parent
                                        source: resolvedRowImage
                                        fillMode: Image.PreserveAspectCrop
                                        visible: modelData.image !== ""
                                        opacity: modelData.download_status === "done" ? 1.0 : 0.45
                                    }

                                    Item {
                                        anchors.bottom: parent.bottom
                                        width: parent.width
                                        height: parent.height * parent.revealFraction
                                        clip: true
                                        visible: modelData.image !== "" && parent.revealFraction > 0 && modelData.download_status !== "done"

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
                                        visible: modelData.image === ""
                                        color: Theme.bgElevated

                                        Text {
                                            anchors.centerIn: parent
                                            text: epNumber
                                            font.family: Theme.fontFamily
                                            font.pixelSize: 24
                                            font.weight: Font.Bold
                                            color: Theme.textMuted
                                        }
                                    }

                                    // Progress bar ở đáy thumbnail
                                    Rectangle {
                                        anchors.left: parent.left
                                        anchors.right: parent.right
                                        anchors.bottom: parent.bottom
                                        height: 3
                                        visible: (modelData.watched_percent || 0) > 0 && (modelData.watched_percent || 0) < 100
                                        color: Qt.rgba(1, 1, 1, 0.15)

                                        Rectangle {
                                            width: parent.width * ((modelData.watched_percent || 0) / 100)
                                            height: parent.height
                                            color: Theme.accentStart
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
                                        text: epNumber + ". " + epTitle
                                        font.family: Theme.fontFamily
                                        font.pixelSize: 15
                                        font.weight: Font.Bold
                                        color: Theme.textPrimary
                                        elide: Text.ElideRight
                                        width: parent.width - (epDuration.visible ? epDuration.implicitWidth + 8 : 0)
                                    }

                                    Text {
                                        id: epDuration
                                        visible: modelData.duration_seconds > 0
                                        text: helpers.formatDuration(modelData.duration_seconds)
                                        font.family: Theme.fontFamily
                                        font.pixelSize: Theme.captionSize
                                        color: Theme.textMuted
                                    }
                                }

                                Text {
                                    width: parent.width
                                    visible: (modelData.subtitle || "").length > 0
                                    text: modelData.subtitle || ""
                                    font.family: Theme.fontFamily
                                    font.pixelSize: Theme.captionSize
                                    color: Theme.textSecondary
                                    elide: Text.ElideRight
                                }

                                // Download / listened status
                                Text {
                                    width: parent.width
                                    visible: modelData.download_status !== "done" || modelData.is_downloading
                                    text: modelData.is_downloading
                                        ? ("Đang tải " + Math.round(modelData.download_percent || 0) + "%")
                                        : (modelData.download_status === "done" ? "Đã xem — nhấp để phát" : "Nhấp để xem")
                                    font.family: Theme.fontFamily
                                    font.pixelSize: Theme.captionSize
                                    color: modelData.download_status === "done" ? Theme.accentStart : Theme.textMuted
                                }
                            }
                        }
                    }
                }
            }
        }
    }
}
