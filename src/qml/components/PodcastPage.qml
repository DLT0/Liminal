import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import Liminal 1.0

Item {
    id: root
    clip: true

    // ── Backend sync ──────────────────────────────────────────────────────────
    Connections {
        target: backend
        function onCurrentPageChanged() {
            if (backend.currentPage === 6)
                shareBridge.refreshSuggestions()
        }
    }

    Component.onCompleted: shareBridge.refreshSuggestions()

    // ── Internal navigation state ─────────────────────────────────────────────
    property string viewState: "main"       // "main" | "category_detail" | "playlist_detail" | "suggestions_full"
    property string viewingId: ""
    property string viewingTitle: ""

    // ── Helpers ───────────────────────────────────────────────────────────────
    QtObject {
        id: helpers

        function cardFromModelItem(it, i) {
            if (!it) return null
            return {
                title:          it.title          || "",
                subtitle:       it.subtitle       || "",
                categoryLabel:  it.category_label || it.categoryLabel || "",
                category:       it.category       || "",
                tags:           it.tags           || [],
                imageSource:    it.image          || it.imageSource   || "",
                downloadPercent: it.download_percent !== undefined
                    ? it.download_percent : (it.downloadPercent || 0),
                downloadStatus: it.download_status || it.downloadStatus || "pending",
                isDownloading:  it.is_downloading !== undefined
                    ? it.is_downloading : !!it.isDownloading,
                audioOnly:      it.audio_only !== undefined
                    ? it.audio_only
                    : (it.audioOnly !== undefined ? it.audioOnly : true),
                localPath:      it.local_path || it.localPath || "",
                trackId:        it.track_id || it.trackId || it.id || "",
                originalIndex:  i
            }
        }

        // Item không thuộc playlist nào + chưa tải về → hiển thị trong "Đề xuất chung"
        function ungroupedSuggestions(model) {
            var list = [], count = Number(model ? model.count : 0) || 0
            for (var i = 0; i < count; i++) {
                var it = model ? (typeof model.item_at === "function" ? model.item_at(i) : model.itemAt(i)) : null
                if (!it) continue
                // Bỏ qua item đã tải
                var local = it.local_path || it.localPath || ""
                if (local && local.toString().trim() !== "") continue
                // Bỏ qua item thuộc playlist (đã có section riêng)
                var plId = it.playlist_id || it.playlistId || ""
                if (plId && plId.toString().trim() !== "") continue
                var card = cardFromModelItem(it, i)
                if (card) list.push(card)
            }
            return list
        }

        // Toàn bộ đề xuất, đã tải trước, chưa tải sau
        function allSuggestionsSorted(model) {
            var list = [], count = Number(model ? model.count : 0) || 0
            for (var i = 0; i < count; i++) {
                var it = model ? (typeof model.item_at === "function" ? model.item_at(i) : model.itemAt(i)) : null
                if (!it) continue
                var card = cardFromModelItem(it, i)
                if (card) list.push(card)
            }
            list.sort(function(a, b) {
                var aDl = a.localPath && a.localPath.toString().trim() !== "" ? 1 : 0
                var bDl = b.localPath && b.localPath.toString().trim() !== "" ? 1 : 0
                return bDl - aDl
            })
            return list
        }
    }

    // ── Computed ──────────────────────────────────────────────────────────────
    readonly property var suggModel:       backend.podcastSuggestionsModel
    readonly property var dlModel:         backend.podcastDownloadedModel
    readonly property int gridCols:        Math.max(2, Math.floor((width - 2 * Theme.contentPadding) / (180 + Theme.cardGap)))

    // ── Navigation ────────────────────────────────────────────────────────────
    function handleChipClick(categoryId) {
        var id = categoryId ? categoryId.toString().toLowerCase().trim() : ""
        if (id === "" || id === "all") {
            backend.setPodcastCategoryFilter("all")
            return
        }
        if (id === "playlists") {
            backend.setPodcastCategoryFilter("playlists")
            return
        }
        var cats = backend.podcastCategories || []
        var label = id
        for (var c = 0; c < cats.length; c++) {
            if (cats[c] && cats[c].id && cats[c].id.toString().toLowerCase().trim() === id) {
                label = cats[c].label || cats[c].id
                break
            }
        }
        viewState = "category_detail"
        viewingId = id
        viewingTitle = label
        backend.openPodcastCategoryDetail(id)
    }

    function openPlaylistDetail(playlistId) {
        backend.openPodcastPlaylistDetail(playlistId)
        viewState = "playlist_detail"
        viewingId = playlistId
    }

    function goBackToMain() {
        if (viewState === "playlist_detail") backend.closePodcastPlaylist()
        else if (viewState === "category_detail") backend.closePodcastCategoryDetail()
        viewState = "main"
        viewingId = ""
        viewingTitle = ""
    }

    // ── Category detail overlay ───────────────────────────────────────────────
    Loader {
        id: categoryDetailLoader
        anchors.fill: parent
        active: viewState === "category_detail"
        sourceComponent: PodcastCategoryDetailPage {
            anchors.fill: parent
            categoryTitle: root.viewingTitle
            model: {
                var list = []
                var rows = backend.getItemsByCategory(root.viewingId)
                for (var i = 0; i < rows.length; i++) {
                    var card = helpers.cardFromModelItem(rows[i], i)
                    if (card) list.push(card)
                }
                return list
            }
            gridColumns: root.gridCols
            onBackClicked: root.goBackToMain()
        }
    }

    // ── Playlist detail overlay ───────────────────────────────────────────────
    Loader {
        id: playlistDetailLoader
        anchors.fill: parent
        active: viewState === "playlist_detail"
        sourceComponent: PodcastPlaylistDetailPage {
            anchors.fill: parent
            model: backend.podcastPlaylistModel
            playlistTitle: backend.podcastPlaylistTitle
            playlistImage: backend.podcastPlaylistImage
            statusMessage: playlistStatusMsg

            property string playlistStatusMsg: ""

            onBackClicked: root.goBackToMain()
            onEpisodeClicked: function(index) { backend.playPodcastPlaylistEpisode(index) }
            onDownloadRequested: function(index) { backend.downloadPodcastPlaylistEpisode(index) }
            onAiSortRequested: backend.requestAiPodcastPlaylistSort()

            Connections {
                target: backend
                function onPodcastPlaylistAiSortFinished() {
                    playlistDetailLoader.item.playlistStatusMsg = "Đã sắp xếp và lưu thứ tự tập"
                }
                function onPodcastPlaylistAiSortError(message) {
                    playlistDetailLoader.item.playlistStatusMsg = message || "AI sắp xếp thất bại"
                }
            }
        }
    }

    // ── Full suggestions overlay ──────────────────────────────────────────────
    Loader {
        id: suggestionsFullLoader
        anchors.fill: parent
        active: viewState === "suggestions_full"
        sourceComponent: PodcastCategoryDetailPage {
            anchors.fill: parent
            categoryTitle: "Tất cả đề xuất"
            model: root.suggModel ? helpers.allSuggestionsSorted(root.suggModel) : []
            gridColumns: root.gridCols
            onBackClicked: root.goBackToMain()
        }
    }

    // ══════════════════════════════════════════════════════════════════════════
    // MAIN VIEW
    // ══════════════════════════════════════════════════════════════════════════
    Flickable {
        id: flick
        anchors.fill: parent
        visible: viewState === "main"
        contentWidth: width
        contentHeight: col.implicitHeight + Theme.contentPadding
        clip: true
        boundsBehavior: Flickable.StopAtBounds
        ScrollBar.vertical: ScrollBar { policy: ScrollBar.AsNeeded }
        interactive: contentHeight > height

        WheelHandler {
            target: flick
            onWheel: function(ev) {
                if (!flick.interactive) return
                var max   = Math.max(0, flick.contentHeight - flick.height)
                var delta = ev.pixelDelta.y !== 0 ? ev.pixelDelta.y : ev.angleDelta.y / 2
                flick.contentY = Math.max(0, Math.min(max, flick.contentY - delta))
                ev.accepted = true
            }
        }

        ColumnLayout {
            id: col
            width: parent.width
            spacing: 0

            // ── Header text + Category chips ──────────────────────────────────
            Text {
                text: "Khám phá podcast theo chủ đề bạn quan tâm."
                wrapMode: Text.Wrap
                font.family: Theme.fontFamily
                font.pixelSize: Theme.bodySize
                color: Theme.textMuted
                Layout.fillWidth: true
                Layout.leftMargin: Theme.contentPadding
                Layout.rightMargin: Theme.contentPadding
                Layout.topMargin: Theme.contentPadding
            }

            Item { Layout.preferredHeight: 12 }

            CategoryChipBar {
                Layout.fillWidth: true
                Layout.leftMargin: Theme.contentPadding
                Layout.rightMargin: Theme.contentPadding
                categories: backend.podcastCategoriesWithCounts
                selectedId: backend.podcastCategoryFilter
                onCategorySelected: function(id) { root.handleChipClick(id) }
            }

            Item { Layout.preferredHeight: Theme.sectionSpacing }

            // ══════════════════════════════════════════════════════════════════
            // TAB: ALL
            // ══════════════════════════════════════════════════════════════════
            // ── 1. Đã xem gần đây ───────────────────────────────────────────
            ColumnLayout {
                Layout.fillWidth: true
                spacing: 0
                visible: backend.podcastCategoryFilter === "all"
                    && (Number(root.dlModel ? root.dlModel.count : 0) || 0) > 0

                SectionHeader {
                    text: "Đã xem gần đây"
                    Layout.fillWidth: true
                    Layout.leftMargin: Theme.contentPadding
                    Layout.rightMargin: Theme.contentPadding
                }

                Item { Layout.preferredHeight: 8 }

                PodcastDownloadedSection {
                    Layout.fillWidth: true
                    Layout.leftMargin: Theme.contentPadding
                    Layout.rightMargin: Theme.contentPadding
                    model: root.dlModel
                    gridColumns: root.gridCols
                    onPlayRequested: function(i) { backend.playDownloadedPodcastEpisode(i) }
                }
            }

            // ── 2. Đề xuất (ungrouped + items từ playlist nhỏ <3 video, trộn ngẫu nhiên) ──
            ColumnLayout {
                id: suggestionsBlock
                Layout.fillWidth: true
                spacing: 0
                visible: backend.podcastCategoryFilter === "all"
                    && suggestionsSection.itemCount > 0

                readonly property var allSuggestions: {
                    var list = helpers.ungroupedSuggestions(root.suggModel) || []
                    var scattered = backend.scatteredSuggestions || []
                    for (var s = 0; s < scattered.length; s++)
                        list.push(scattered[s])
                    return list
                }
                readonly property bool hasMore: allSuggestions.length > root.gridCols

                // Header: title + nút "Xem thêm" cùng hàng
                RowLayout {
                    Layout.fillWidth: true
                    Layout.leftMargin: Theme.contentPadding
                    Layout.rightMargin: Theme.contentPadding
                    spacing: 12

                    Text {
                        Layout.fillWidth: true
                        text: "Đề xuất"
                        font.family: Theme.fontFamily
                        font.pixelSize: 24
                        font.weight: Font.Bold
                        color: Theme.textPrimary
                        elide: Text.ElideRight
                    }

                    Rectangle {
                        Layout.preferredWidth: xemThemSuggestText.implicitWidth + 20
                        Layout.preferredHeight: 26
                        visible: suggestionsBlock.hasMore
                        radius: 6
                        color: Theme.bgElevated
                        border.color: xemThemSuggestHover.hovered ? Theme.accentStart : Theme.cardBorder
                        border.width: 1

                        Behavior on border.color { ColorAnimation { duration: 100 } }

                        Text {
                            id: xemThemSuggestText
                            anchors.centerIn: parent
                            text: "Xem thêm"
                            font.family: Theme.fontFamily
                            font.pixelSize: Theme.captionSize
                            font.weight: Font.Medium
                            color: Theme.accentStart
                        }

                        HoverHandler {
                            id: xemThemSuggestHover
                        }

                        MouseArea {
                            anchors.fill: parent
                            cursorShape: Qt.PointingHandCursor
                            onClicked: {
                                root.viewState = "suggestions_full"
                            }
                        }
                    }
                }

                Item { Layout.preferredHeight: 8 }

                PodcastSuggestionsSection {
                    id: suggestionsSection
                    Layout.fillWidth: true
                    Layout.leftMargin: Theme.contentPadding
                    Layout.rightMargin: Theme.contentPadding
                    arrayModel: {
                        var all = suggestionsBlock.allSuggestions
                        if (suggestionsBlock.hasMore)
                            return all.slice(0, root.gridCols)
                        return all
                    }
                    gridColumns: root.gridCols
                    emptyTitle: "Chưa có đề xuất"
                    emptyMessage: "Podcast đề xuất sẽ xuất hiện tại đây."
                    emptyIcon: "podcasts"
                    onDownloadRequested: function(i) { backend.downloadPodcastSuggestion(i) }
                }
            }

            // ── 3. Playlist (>=3 video) — mỗi playlist là 1 section với header + grid tập ──
            Repeater {
                model: backend.playlistSections

                delegate: ColumnLayout {
                    Layout.fillWidth: true
                    spacing: 0
                    visible: modelData && modelData.items && modelData.items.length > 0

                    readonly property var allItems: {
                        var raw = modelData.items || []
                        var mapped = []
                        for (var i = 0; i < raw.length; i++) {
                            var card = helpers.cardFromModelItem(raw[i], i)
                            if (card) mapped.push(card)
                        }
                        return mapped
                    }
                    readonly property bool hasMore: allItems.length > root.gridCols

                    // Header: title + nút "Xem thêm" cùng hàng
                    RowLayout {
                        Layout.fillWidth: true
                        Layout.leftMargin: Theme.contentPadding
                        Layout.rightMargin: Theme.contentPadding
                        spacing: 12

                        Text {
                            id: playlistTitle
                            Layout.fillWidth: true
                            text: modelData.label || ""
                            font.family: Theme.fontFamily
                            font.pixelSize: 24
                            font.weight: Font.Bold
                            color: Theme.textPrimary
                            elide: Text.ElideRight
                        }

                        Rectangle {
                            id: xemThemBtn
                            Layout.preferredWidth: xemThemText.implicitWidth + 20
                            Layout.preferredHeight: 26
                            visible: hasMore
                            radius: 6
                            color: Theme.bgElevated
                            border.color: xemThemHover.hovered ? Theme.accentStart : Theme.cardBorder
                            border.width: 1

                            Behavior on border.color { ColorAnimation { duration: 100 } }

                            Text {
                                id: xemThemText
                                anchors.centerIn: parent
                                text: "+" + allItems.length + " tập"
                                font.family: Theme.fontFamily
                                font.pixelSize: Theme.captionSize
                                font.weight: Font.Medium
                                color: Theme.accentStart
                            }

                            HoverHandler {
                                id: xemThemHover
                            }

                            MouseArea {
                                anchors.fill: parent
                                cursorShape: Qt.PointingHandCursor
                                onClicked: {
                                    if (modelData && modelData.id)
                                        root.openPlaylistDetail(modelData.id)
                                }
                            }
                        }
                    }

                    Item { Layout.preferredHeight: 8 }

                    PodcastSuggestionsSection {
                        Layout.fillWidth: true
                        Layout.leftMargin: Theme.contentPadding
                        Layout.rightMargin: Theme.contentPadding
                        arrayModel: {
                            var items = []
                            var raw = modelData.items || []
                            var limit = Math.min(raw.length, root.gridCols)
                            for (var i = 0; i < limit; i++) {
                                var card = helpers.cardFromModelItem(raw[i], i)
                                if (card) items.push(card)
                            }
                            return items
                        }
                        gridColumns: root.gridCols
                        onDownloadRequested: function(i) {
                            backend.downloadPodcastSuggestion(i)
                        }
                    }

                }
            }

            ColumnLayout {
                Layout.fillWidth: true
                spacing: 0
                visible: backend.podcastCategoryFilter === "all"
                    && (Number(backend.shortsSuggestionsModel ? backend.shortsSuggestionsModel.count : 0) || 0) > 0

                SectionHeader {
                    text: "Shorts"
                    Layout.fillWidth: true
                    Layout.leftMargin: Theme.contentPadding
                    Layout.rightMargin: Theme.contentPadding
                }

                Item { Layout.preferredHeight: 8 }

                SuggestionsSection {
                    Layout.fillWidth: true
                    Layout.leftMargin: Theme.contentPadding
                    Layout.rightMargin: Theme.contentPadding
                    model: backend.shortsSuggestionsModel
                    gridColumns: root.gridCols
                    emptyMinHeight: 0
                    onDownloadRequested: function(i) { backend.downloadShortsSuggestion(i) }
                }

                Item { Layout.preferredHeight: Theme.sectionSpacing }
            }

            // ══════════════════════════════════════════════════════════════════
            // TAB: PLAYLISTS — grid view of all playlists
            // ══════════════════════════════════════════════════════════════════
            ColumnLayout {
                Layout.fillWidth: true
                Layout.leftMargin: Theme.contentPadding
                Layout.rightMargin: Theme.contentPadding
                spacing: 12
                visible: backend.podcastCategoryFilter === "playlists"

                SectionHeader {
                    text: "Danh sách phát của Collaborator"
                    Layout.fillWidth: true
                    horizontalMargin: 0
                }

                Item {
                    Layout.fillWidth: true
                    Layout.preferredHeight: Math.ceil(playlistGrid.count / root.gridCols) * (200 + Theme.cardGap) + 16

                    GridView {
                        id: playlistGrid
                        anchors.fill: parent
                        interactive: false
                        cellWidth: Math.floor(parent.width / root.gridCols)
                        cellHeight: 200 + Theme.cardGap
                        model: backend.playlists

                        delegate: Item {
                            width: playlistGrid.cellWidth - Theme.cardGap
                            height: 200

                            Rectangle {
                                id: playlistCard
                                anchors.fill: parent
                                radius: 12
                                color: Theme.cardBg
                                border.color: playlistCardHover.hovered ? Theme.accentStart : Theme.cardBorder
                                border.width: 1
                                clip: true

                                Behavior on border.color { ColorAnimation { duration: 100 } }

                                ColumnLayout {
                                    anchors.fill: parent
                                    spacing: 8
                                    anchors.margins: 12

                                    Rectangle {
                                        Layout.fillWidth: true
                                        Layout.preferredHeight: 110
                                        radius: 8
                                        color: Theme.bgElevated
                                        clip: true

                                        Image {
                                            anchors.fill: parent
                                            source: modelData.thumbnail || ""
                                            fillMode: Image.PreserveAspectCrop
                                            asynchronous: true
                                            visible: modelData.thumbnail !== ""
                                        }

                                        AppIcon {
                                            anchors.centerIn: parent
                                            name: "queue_music"
                                            font.pixelSize: 36
                                            color: Theme.textMuted
                                            opacity: 0.35
                                            visible: modelData.thumbnail === ""
                                        }
                                    }

                                    Text {
                                        text: modelData.label || "Playlist"
                                        font.family: Theme.fontFamily
                                        font.pixelSize: Theme.bodySize
                                        font.weight: Font.Bold
                                        color: Theme.textPrimary
                                        elide: Text.ElideRight
                                        Layout.fillWidth: true
                                    }

                                    Text {
                                        text: modelData.itemCount + " tập"
                                        font.family: Theme.fontFamily
                                        font.pixelSize: Theme.captionSize
                                        color: Theme.textMuted
                                        Layout.fillWidth: true
                                    }
                                }

                                HoverHandler {
                                    id: playlistCardHover
                                }

                                MouseArea {
                                    anchors.fill: parent
                                    cursorShape: Qt.PointingHandCursor
                                    onClicked: root.openPlaylistDetail(modelData.id)
                                }
                            }
                        }
                    }
                }
            }
        }
    }
}
