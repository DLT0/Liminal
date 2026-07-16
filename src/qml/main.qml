import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import QtQuick.Window
import Liminal 1.0

import "components"

ApplicationWindow {
    id: root

    width: 1200
    height: 780
    minimumWidth: 1000
    minimumHeight: 680
    visible: false
    title: "Liminal"
    opacity: uiConfig.windowOpacity
    color: "transparent"
    flags: uiConfig.customTitleBar
        ? (Qt.Window | Qt.FramelessWindowHint)
        : Qt.Window

    property string searchQuery: ""
    property int visibilityBeforeFullScreen: Window.Windowed

    onClosing: function(close) {
        close.accepted = false
        backend.quitApp()
    }

    Shortcut {
        sequence: "Meta+Q"
        onActivated: backend.quitApp()
    }

    Shortcut {
        sequence: "Super+Q"
        onActivated: backend.quitApp()
    }

    Item {
        // oauthOverlay removed
    }

    ShareCreatedDialog {
        id: shareCreatedDialog
        parent: Overlay.overlay
    }

    ShareErrorDialog {
        id: shareErrorDialog
        parent: Overlay.overlay
    }

    ShareLoadingDialog {
        id: shareLoadingDialog
        parent: Overlay.overlay
    }

    RedeemShareDialog {
        id: redeemShareDialog
        parent: Overlay.overlay
        onAccepted: {
            if (!shareBridge.shareBusy)
                shareBridge.redeemCode(codeField.text)
        }
    }

    Popup {
        id: shareToast
        property string text: ""
        modal: false
        focus: false
        closePolicy: Popup.CloseOnEscape | Popup.CloseOnPressOutside
        anchors.centerIn: Overlay.overlay
        padding: 14
        background: Rectangle {
            radius: 10
            color: Theme.glassStrong
            border.color: Theme.glassStrongBorder
        }
        contentItem: Text {
            text: shareToast.text
            color: Theme.textPrimary
            font.family: Theme.fontFamily
            font.pixelSize: Theme.bodySize
        }
        Timer {
            id: shareToastTimer
            interval: 2800
            onTriggered: shareToast.close()
        }
        onOpened: shareToastTimer.restart()
    }

    Connections {
        target: shareBridge
        function onShareCreated(code) {
            shareCreatedDialog.showCode(code)
        }
        function onShareError(message) {
            if (message.indexOf("\n") >= 0 || message.length > 72) {
                shareErrorDialog.showError(message)
            } else {
                shareToast.text = message
                shareToast.open()
            }
        }
        function onRedeemSuccess(message) {
            shareToast.text = message
            shareToast.open()
        }
        function onShareBusyChanged() {
            if (shareBridge.shareBusy)
                shareLoadingDialog.open()
            else
                shareLoadingDialog.close()
        }
    }

    Connections {
        target: backend
        function onDebugToast(message) {
            shareToast.text = message
            shareToast.open()
        }
        function onSeriesAiSortError(message) {
            shareToast.text = message
            shareToast.open()
        }
        function onCurrentPageChanged() {
            contentHeader.pageTitle = backend.pageTitle
            contentHeader.currentPage = backend.currentPage
            contentHeader.updateForPage(backend.currentPage)
        }
        function onFullScreenChanged() {
            if (backend.isFullScreen) {
                root.visibilityBeforeFullScreen = root.visibility
                root.showFullScreen()
            } else if (root.visibilityBeforeFullScreen === Window.Maximized) {
                root.showMaximized()
            } else {
                root.showNormal()
            }
        }
    }

    Connections {
        target: uiConfig
        function onConfigChanged() {
            contentHeader.updateForPage(backend.currentPage)
        }
    }

    Rectangle {
        id: windowBg
        anchors.fill: parent
        color: backend.inFocusMode && mpvVideo.geometryMode
            ? "transparent"
            : Theme.bgElevated
        radius: backend.inFocusMode && mpvVideo.geometryMode ? 0 : 16
        clip: true

        ColumnLayout {
            anchors.fill: parent
            spacing: 0

        TitleBar {
            id: titleBar
            Layout.fillWidth: true
            visible: uiConfig.customTitleBar && root.visibility !== Window.FullScreen

            onCloseRequested: root.close()
            onMinimizeRequested: root.showMinimized()
            onMaximizeRequested: {
                root.visibility === Window.Maximized
                    ? root.showNormal()
                    : root.showMaximized()
            }
        }

        RowLayout {
            Layout.fillWidth: true
            Layout.fillHeight: true
            spacing: 0

            Sidebar {
                id: sidebar
                Layout.fillHeight: true
                visible: uiConfig.sidebarVisible && !backend.inFocusMode
                currentPage: backend.currentPage
                onPageSelected: function(page, again) {
                    backend.setCurrentPage(page, again === true)
                    contentHeader.pageTitle = backend.pageTitle
                    contentHeader.currentPage = page
                    contentHeader.updateForPage(page)
                }
                onSearchChanged: function(text) {
                    root.searchQuery = text
                    contentHeader.setSearchText(text)
                    backend.setSearchFilter(text)
                }
            }

            ColumnLayout {
                Layout.fillWidth: true
                Layout.fillHeight: true
                spacing: 0

                ContentHeader {
                    id: contentHeader
                    Layout.fillWidth: true
                    Layout.preferredHeight: 72
                    visible: !backend.inFocusMode
                    pageTitle: backend.pageTitle
                    currentPage: backend.currentPage

                    onSearchChanged: function(text) {
                        root.searchQuery = text
                        backend.setSearchFilter(text)
                    }
                    onSearchSubmitted: function(text) {
                        // Discover search removed
                    }
                    onRedeemShareClicked: redeemShareDialog.open()
                }

                Item {
                    Layout.fillWidth: true
                    Layout.fillHeight: true


                    Flickable {
                        id: musicPage
                        objectName: "musicPage"
                        anchors.fill: parent
                        visible: backend.currentPage === 2
                        clip: true
                        contentWidth: width
                        contentHeight: musicContent.height
                        interactive: musicContent.height > musicPage.height

                        ScrollBar.vertical: ScrollBar { policy: ScrollBar.AsNeeded }

                        // Qt can deliver mouse-wheel events differently on X11 and
                        // Wayland.  Handle both high-resolution (pixelDelta) and
                        // traditional wheel (angleDelta) events explicitly so the
                        // page also scrolls on Linux distributions using either
                        // input backend.
                        WheelHandler {
                            target: musicPage
                            onWheel: function(event) {
                                var delta = event.pixelDelta.y
                                if (delta === 0)
                                    delta = event.angleDelta.y / 2
                                if (delta === 0 || !musicPage.interactive)
                                    return

                                var maximum = Math.max(0, musicPage.contentHeight - musicPage.height)
                                musicPage.contentY = Math.max(0, Math.min(maximum,
                                    musicPage.contentY - delta))
                                event.accepted = true
                            }
                        }

                        // Flickable's children live in its content item.  Give that item
                        // an explicit height so the two embedded LibraryPages cannot end up
                        // with a zero-height anchor binding.
                        Item {
                            id: musicContent
                            width: musicPage.width
                            height: backend.inCollectionView || backend.inSharedPlaylistView
                                ? musicPage.height
                                : backend.musicSearchActive
                                    ? musicSearchPage.y + musicSearchPage.height + Theme.contentPadding
                                    : musicSinglesPage.y + musicSinglesPage.height + Theme.contentPadding

                            readonly property int musicColumns: Theme.gridColumns
                            readonly property real musicCellWidth: Math.floor(
                                (width - 2 * Theme.contentPadding - (musicColumns - 1) * Theme.cardGap) / musicColumns
                            )
                            readonly property real musicCellHeight: Math.ceil(musicCellWidth + 52) + 8
                            readonly property real albumsHeight: Math.max(
                                180,
                                Math.ceil((Number(backend.musicAlbumsModel.count) || 0) / musicColumns)
                                    * musicCellHeight + 16
                            )
                            readonly property real singlesHeight: Math.max(
                                180,
                                Math.ceil((Number(backend.musicSinglesModel.count) || 0) / musicColumns)
                                    * musicCellHeight + 16
                            )
                            readonly property real searchHeight: Math.max(
                                180,
                                Math.ceil((Number(backend.musicSearchModel.count) || 0) / musicColumns)
                                    * musicCellHeight + 16
                            )
                            readonly property real sharedHeight: Math.max(
                                180,
                                Math.ceil((Number(backend.musicSharedModel.count) || 0) / musicColumns)
                                    * musicCellHeight + 16
                            )
                            readonly property bool showShared: backend.musicSharedModel.count > 0
                            readonly property bool inMusicDetail: backend.inMusicDetailView

                            SectionHeader {
                                id: musicSharedTitle
                                x: Theme.contentPadding
                                y: Theme.contentPadding
                                width: parent.width - 2 * Theme.contentPadding
                                text: "Được chia sẻ với tôi"
                                visible: !musicContent.inMusicDetail && !backend.musicSearchActive && musicContent.showShared
                            }

                            SharedVideosSection {
                                id: musicSharedSection
                                objectName: "musicSharedSection"
                                x: 0
                                y: musicSharedTitle.y + musicSharedTitle.height + 4
                                width: parent.width
                                height: musicContent.sharedHeight
                                visible: !musicContent.inMusicDetail && !backend.musicSearchActive && musicContent.showShared
                                gridColumns: musicContent.musicColumns
                                emptyTitle: "Chưa có playlist chia sẻ"
                                emptyMessage: "Nhập mã chia sẻ từ bạn bè để nghe playlist hoặc đĩa đơn tại đây."
                                model: backend.musicSharedModel
                                onPlayRequested: function(index) { backend.playMusicShared(index) }
                                onDownloadRequested: function(index) { backend.downloadMusicSharedItem(index) }
                                onDismissRequested: function(index) { backend.dismissMusicSharedItem(index) }
                            }

                            CollectionDetailView {
                                id: sharedPlaylistDetailView
                                objectName: "sharedPlaylistDetailView"
                                z: 20
                                x: 0
                                y: 0
                                width: parent.width
                                height: parent.height
                                visible: backend.inSharedPlaylistView
                                model: backend.musicModel
                                showDownloadState: true
                                bannerTitle: backend.collectionBannerTitle
                                bannerSubtitle: backend.collectionBannerSubtitle
                                bannerImage: backend.collectionBannerImage
                                hasPlayableTracks: backend.collectionHasPlayableTracks
                                isPlaying: backend.isPlaying
                                onPlayRequested: function(index) { backend.playSharedPlaylistTrack(index) }
                                onDownloadEpisodeRequested: function(index) { backend.downloadSharedPlaylistTrack(index) }
                                onPlayAllRequested: backend.togglePlayCollection()
                                onShufflePlayRequested: backend.playCollectionShuffled()
                            }

                            SectionHeader {
                                id: albumsTitle
                                x: Theme.contentPadding
                                y: musicContent.showShared
                                    ? musicSharedSection.y + musicSharedSection.height + 8
                                    : Theme.contentPadding
                                width: parent.width - 2 * Theme.contentPadding
                                text: "Playlist của tôi"
                                visible: !musicContent.inMusicDetail && !backend.musicSearchActive
                            }

                            LibraryPage {
                                id: musicAlbumsPage
                                objectName: "musicAlbumsPage"
                                x: 0
                                y: backend.inCollectionView ? 0 : albumsTitle.y + albumsTitle.height + 4
                                width: parent.width
                                height: backend.inCollectionView ? parent.height : musicContent.albumsHeight
                                visible: (backend.inCollectionView || !backend.musicSearchActive) && !backend.inSharedPlaylistView
                                model: backend.musicAlbumsModel
                                useVinylStyle: true
                                showShareAction: true
                                showPlaylistShare: backend.inCollectionView
                                    && backend.currentPlaylistFolderPath.length > 0
                                    && !backend.currentPlaylistFolderPath.startsWith("__liminal__:")
                                showTrackShare: backend.inCollectionView
                                    && backend.currentPlaylistFolderPath.length > 0
                                    && !backend.currentPlaylistFolderPath.startsWith("__liminal__:")
                                showScrollBar: false
                                scrollEnabled: false
                                verticalContentMargin: 8
                                gridColumns: musicContent.musicColumns
                                showBackButton: backend.libraryCanGoBack
                                breadcrumb: backend.libraryBreadcrumb
                                inCollectionView: backend.inCollectionView
                                bannerTitle: backend.collectionBannerTitle
                                bannerSubtitle: backend.collectionBannerSubtitle
                                bannerImage: backend.collectionBannerImage
                                hasPlayableTracks: backend.collectionHasPlayableTracks
                                isPlaying: backend.isPlaying
                                emptyTitle: "Chưa có playlist"
                                emptyMessage: "Tạo playlist trong Music để hiển thị tại đây."
                                onPlayRequested: function(index) { backend.playMedia(index) }
                                onOpenCollectionRequested: function(index) { backend.openMusicAlbum(index) }
                                onPlayAllRequested: backend.togglePlayCollection()
                                onShufflePlayRequested: backend.playCollectionShuffled()
                            }

                            SectionHeader {
                                id: singlesTitle
                                x: Theme.contentPadding
                                y: musicAlbumsPage.y + musicAlbumsPage.height + 8
                                width: parent.width - 2 * Theme.contentPadding
                                text: "Đĩa đơn"
                                visible: !musicContent.inMusicDetail && !backend.musicSearchActive
                            }

                            LibraryPage {
                                id: musicSearchPage
                                objectName: "musicSearchPage"
                                x: 0
                                y: Theme.contentPadding
                                width: parent.width
                                height: musicContent.searchHeight
                                visible: backend.musicSearchActive
                                model: backend.musicSearchModel
                                useVinylStyle: true
                                showScrollBar: false
                                scrollEnabled: false
                                verticalContentMargin: 8
                                gridColumns: musicContent.musicColumns
                                showBackButton: false
                                inCollectionView: false
                                isPlaying: backend.isPlaying
                                emptyTitle: "Không tìm thấy bài hát"
                                emptyMessage: "Thử từ khóa khác hoặc kiểm tra thư viện nhạc."
                                onPlayRequested: function(index) { backend.playMusicSearch(index) }
                            }

                            LibraryPage {
                                id: musicSinglesPage
                                objectName: "musicSinglesPage"
                                x: 0
                                y: singlesTitle.y + singlesTitle.height + 4
                                width: parent.width
                                height: musicContent.singlesHeight
                                visible: !backend.inCollectionView && !backend.musicSearchActive
                                model: backend.musicSinglesModel
                                useVinylStyle: true
                                showShareAction: true
                                showScrollBar: false
                                scrollEnabled: false
                                verticalContentMargin: 8
                                gridColumns: musicContent.musicColumns
                                showBackButton: false
                                inCollectionView: false
                                isPlaying: backend.isPlaying
                                emptyTitle: "Chưa có đĩa đơn"
                                emptyMessage: "Thêm file nhạc trực tiếp vào Music."
                                onPlayRequested: function(index) { backend.playMusicSingle(index) }
                            }
                        }
                    }

                    Flickable {
                        id: videoPage
                        objectName: "videoPage"
                        anchors.fill: parent
                        visible: backend.currentPage === 3
                        clip: true
                        contentWidth: width
                        contentHeight: videoContent.height
                        interactive: !videoContent.inVideoDetail && videoContent.height > videoPage.height

                        Connections {
                            target: backend
                            function onLibraryNavigationChanged() {
                                if (backend.inVideoDetailView)
                                    videoPage.contentY = 0
                            }
                        }

                        ScrollBar.vertical: ScrollBar { policy: ScrollBar.AsNeeded }

                        WheelHandler {
                            target: videoPage
                            onWheel: function(event) {
                                var delta = event.pixelDelta.y
                                if (delta === 0)
                                    delta = event.angleDelta.y / 2
                                if (delta === 0 || !videoPage.interactive)
                                    return

                                var maximum = Math.max(0, videoPage.contentHeight - videoPage.height)
                                videoPage.contentY = Math.max(0, Math.min(maximum,
                                    videoPage.contentY - delta))
                                event.accepted = true
                            }
                        }

                        Item {
                            id: videoContent
                            width: videoPage.width
                            readonly property bool inVideoDetail: backend.inVideoDetailView
                            height: videoContent.inVideoDetail
                                ? videoPage.height
                                : backend.videoSearchActive
                                    ? videoSearchPage.y + videoSearchPage.height + Theme.contentPadding
                                    : (videoContent.showSeries
                                        ? videoSeriesPage.y + videoSeriesPage.height + Theme.contentPadding
                                        : videoMyMoviesPage.y + videoMyMoviesPage.height + Theme.contentPadding)

                            readonly property int videoColumns: Theme.gridColumns
                            readonly property real videoCellWidth: Math.floor(
                                (width - 2 * Theme.contentPadding - (videoColumns - 1) * Theme.cardGap) / videoColumns
                            )
                            readonly property real videoCellHeight: Math.ceil(videoCellWidth / Theme.videoPosterAspect + 62) + 8

                            readonly property real sharedHeight: Math.max(
                                180,
                                Math.ceil((Number(backend.videoSharedModel.count) || 0) / videoColumns)
                                    * videoCellHeight + 16
                            )
                            // Chiều cao khối đề xuất (sections + Đề xuất + Shorts) — theo implicitHeight
                            readonly property real seriesHeight: videoContent.showSeries
                                ? Math.max(
                                    180,
                                    Math.ceil((Number(backend.videoSeriesModel.count) || 0) / videoColumns)
                                        * videoCellHeight + 16
                                  )
                                : 0
                            readonly property real myMoviesHeight: Math.max(
                                180,
                                Math.ceil((Number(backend.videoMyMoviesModel.count) || 0) / videoColumns)
                                    * videoCellHeight + 16
                            )
                            readonly property bool showSeries: backend.videoSeriesModel.count > 0
                            readonly property real searchHeight: Math.max(
                                180,
                                Math.ceil((Number(backend.videoSearchModel.count) || 0) / videoColumns)
                                    * videoCellHeight + 16
                            )


                            readonly property bool showShared: backend.videoSharedModel.count > 0

                            // ── Helpers: lọc playlist có video ──────────────────────
                            property var videoPlaylists: []

                            function refreshVideoPlaylists() {
                                var allPlaylists = backend.getPlaylists() || []
                                var model = backend.videoSuggestionsModel
                                var count = Number(model ? model.count : 0) || 0
                                var playlistItems = {}

                                for (var i = 0; i < count; i++) {
                                    var it = _videoItemAt(model, i)
                                    var plId = (it && (it.playlist_id || it.playlistId)) || ""
                                    plId = plId.toString().trim()
                                    if (!plId) continue
                                    if (!playlistItems[plId]) playlistItems[plId] = []
                                    playlistItems[plId].push(i)
                                }

                                var playlistMeta = {}
                                for (var p = 0; p < allPlaylists.length; p++) {
                                    var pl = allPlaylists[p]
                                    if (pl && pl.id) playlistMeta[pl.id] = pl
                                }

                                var out = []
                                for (var pid in playlistItems) {
                                    var meta = playlistMeta[pid]
                                    out.push({
                                        id: pid,
                                        label: (meta && meta.label) ? meta.label : pid,
                                        thumbnail: (meta && meta.thumbnail) ? meta.thumbnail : "",
                                        itemCount: playlistItems[pid].length,
                                        indices: playlistItems[pid]
                                    })
                                }
                                videoPlaylists = out
                            }

                            function _videoItemAt(model, i) {
                                if (!model) return null
                                if (typeof model.itemAt === "function") return model.itemAt(i)
                                if (typeof model.item_at === "function") return model.item_at(i)
                                return null
                            }

                            Connections {
                                target: backend
                                function onSuggestionsChanged() { videoContent.refreshVideoPlaylists() }
                            }

                            Component.onCompleted: refreshVideoPlaylists()

                            SectionHeader {
                                id: sharedTitle
                                x: Theme.contentPadding
                                y: Theme.contentPadding
                                width: parent.width - 2 * Theme.contentPadding
                                text: "Được chia sẻ với tôi"
                                visible: !videoContent.inVideoDetail && !backend.videoSearchActive && videoContent.showShared
                            }

                            SharedVideosSection {
                                id: videoSharedSection
                                objectName: "videoSharedSection"
                                x: 0
                                y: sharedTitle.y + sharedTitle.height + 4
                                width: parent.width
                                height: videoContent.sharedHeight
                                visible: !videoContent.inVideoDetail && !backend.videoSearchActive && videoContent.showShared
                                gridColumns: videoContent.videoColumns
                                model: backend.videoSharedModel
                                onPlayRequested: function(index) { console.log("[DEBUG main.qml] sharedVideo playRequested index=" + index); backend.playVideoShared(index) }
                                onDownloadRequested: function(index) { console.log("[DEBUG main.qml] sharedVideo downloadRequested index=" + index); backend.downloadSharedItem(index) }
                                onDismissRequested: function(index) { backend.dismissSharedItem(index) }
                            }

                            CollectionDetailView {
                                id: sharedSeriesDetailView
                                objectName: "sharedSeriesDetailView"
                                z: 20
                                x: 0
                                y: 0
                                width: parent.width
                                height: parent.height
                                visible: backend.inSharedSeriesView
                                model: backend.videoModel
                                useSeriesStyle: true
                                showDownloadState: true
                                bannerTitle: backend.collectionBannerTitle
                                bannerSubtitle: backend.collectionBannerSubtitle
                                bannerImage: backend.collectionBannerImage
                                bannerDescription: backend.collectionBannerDescription
                                hasPlayableTracks: backend.collectionHasPlayableTracks
                                isPlaying: backend.isPlaying
                                onPlayRequested: function(index) { backend.playSharedSeriesEpisode(index) }
                                onDownloadEpisodeRequested: function(index) { backend.downloadSharedSeriesEpisode(index) }
                                onPlayAllRequested: backend.togglePlayCollection()
                            }

                            CollectionDetailView {
                                id: movieDetailView
                                objectName: "movieDetailView"
                                z: 20
                                x: 0
                                y: 0
                                width: parent.width
                                height: parent.height
                                visible: backend.inMovieDetailView
                                useMovieStyle: true
                                showDownloadState: backend.movieDetailIsShared
                                bannerTitle: backend.collectionBannerTitle
                                bannerSubtitle: backend.collectionBannerSubtitle
                                bannerImage: backend.collectionBannerImage
                                bannerDescription: backend.collectionBannerDescription
                                hasPlayableTracks: backend.collectionHasPlayableTracks
                                isPlaying: backend.isPlaying
                                onPlayAllRequested: backend.playMovieDetail()
                            }

                            // ── Playlist video (mỗi playlist = 1 section) ─────────────────
                            Column {
                                id: videoPlaylistColumn
                                x: 0
                                y: videoContent.showShared
                                    ? videoSharedSection.y + videoSharedSection.height + 8
                                    : Theme.contentPadding
                                width: parent.width
                                visible: !videoContent.inVideoDetail && !backend.videoSearchActive

                                Repeater {
                                    model: videoContent.videoPlaylists
                                    delegate: Column {
                                        width: videoPlaylistColumn.width
                                        visible: modelData.itemCount > 0

                                        SectionHeader {
                                            width: parent.width - 2 * Theme.contentPadding
                                            x: Theme.contentPadding
                                            text: modelData.label
                                        }

                                        Item { width: 1; height: 8 }

                                        SuggestionsSection {
                                            width: parent.width
                                            // Lấy item từ model gốc theo index đã lưu
                                            arrayModel: {
                                                var list = []
                                                var model = backend.videoSuggestionsModel
                                                var indices = modelData.indices || []
                                                for (var i = 0; i < indices.length; i++) {
                                                    var it = videoContent._videoItemAt(model, indices[i])
                                                    if (!it) continue
                                                    list.push({
                                                        title: it.title || "",
                                                        subtitle: it.subtitle || "",
                                                        categoryLabel: it.category_label || it.categoryLabel || "",
                                                        imageSource: it.image || it.imageSource || "",
                                                        downloadPercent: it.download_percent !== undefined ? it.download_percent : (it.downloadPercent || 0),
                                                        downloadStatus: it.download_status || it.downloadStatus || "pending",
                                                        isDownloading: it.is_downloading !== undefined ? it.is_downloading : !!it.isDownloading,
                                                        audioOnly: it.audio_only !== undefined ? it.audio_only : (it.audioOnly !== undefined ? it.audioOnly : false),
                                                        originalIndex: indices[i]
                                                    })
                                                }
                                                return list
                                            }
                                            gridColumns: videoContent.videoColumns
                                            emptyMinHeight: 0
                                            onDownloadRequested: function(origIdx) { backend.downloadVideoSuggestion(origIdx) }
                                        }

                                        Item { width: 1; height: Theme.sectionSpacing }
                                    }
                                }
                            }

                            SectionHeader {
                                id: myMoviesTitle
                                x: Theme.contentPadding
                                y: videoPlaylistColumn.y + videoPlaylistColumn.implicitHeight + 8
                                width: parent.width - 2 * Theme.contentPadding
                                text: "Phim của tôi"
                                visible: !videoContent.inVideoDetail && !backend.videoSearchActive
                            }

                            LibraryPage {
                                id: videoMyMoviesPage
                                objectName: "videoMyMoviesPage"
                                x: 0
                                y: myMoviesTitle.y + myMoviesTitle.height + 4
                                width: parent.width
                                height: videoContent.myMoviesHeight
                                visible: !videoContent.inVideoDetail && !backend.videoSearchActive
                                model: backend.videoMyMoviesModel
                                useVideoStyle: true
                                allowCreateCollection: false
                                widescreenPosters: true
                                showScrollBar: false
                                scrollEnabled: false
                                verticalContentMargin: 8
                                gridColumns: videoContent.videoColumns
                                showShareAction: true
                                showBackButton: false
                                inCollectionView: false
                                isPlaying: backend.isPlaying
                                emptyTitle: "Chưa có phim nào"
                                emptyMessage: "Thêm phim vào thư mục Videos."
                                onPlayRequested: function(index) { console.log("[DEBUG main.qml] videoMyMoviesPage playRequested index=" + index); backend.openVideoMyMovie(index) }
                            }

                            SectionHeader {
                                id: seriesTitle
                                x: Theme.contentPadding
                                y: videoMyMoviesPage.y + videoMyMoviesPage.height + 8
                                width: parent.width - 2 * Theme.contentPadding
                                text: "Phim bộ"
                                visible: videoContent.showSeries
                                    && !videoContent.inVideoDetail
                                    && !backend.videoSearchActive
                            }

                            LibraryPage {
                                id: videoSeriesPage
                                objectName: "videoSeriesPage"
                                x: 0
                                y: backend.inCollectionView ? 0 : seriesTitle.y + seriesTitle.height + 4
                                width: parent.width
                                height: backend.inCollectionView ? parent.height : videoContent.seriesHeight
                                visible: (videoContent.showSeries && !videoContent.inVideoDetail && !backend.videoSearchActive)
                                    || (videoContent.inVideoDetail && backend.inCollectionView)
                                model: backend.inCollectionView ? backend.videoModel : backend.videoSeriesModel
                                useVideoStyle: true
                                widescreenPosters: true
                                showScrollBar: false
                                scrollEnabled: false
                                verticalContentMargin: 8
                                gridColumns: videoContent.videoColumns
                                showShareAction: true
                                showBackButton: backend.inCollectionView
                                breadcrumb: backend.libraryBreadcrumb
                                embedCollectionDetail: true
                                inCollectionView: backend.inCollectionView
                                bannerTitle: backend.collectionBannerTitle
                                bannerSubtitle: backend.collectionBannerSubtitle
                                bannerImage: backend.collectionBannerImage
                                bannerDescription: backend.collectionBannerDescription
                                hasPlayableTracks: backend.collectionHasPlayableTracks
                                isPlaying: backend.isPlaying
                                emptyTitle: "Chưa có phim bộ"
                                emptyMessage: "Tạo thư mục trong thư mục Videos để thêm phim bộ."
                                onPlayRequested: function(index) { console.log("[DEBUG main.qml] videoSeriesPage playRequested index=" + index + " inCollectionView=" + backend.inCollectionView); backend.playMedia(index) }
                                onOpenCollectionRequested: function(index) { backend.openVideoSeries(index) }
                                onPlayAllRequested: backend.togglePlayCollection()
                                onShufflePlayRequested: backend.playCollectionShuffled()
                                onSeriesShareRequested: {
                                    if (backend.currentSeriesFolderPath)
                                        shareBridge.createShareFromSeriesPath(backend.currentSeriesFolderPath)
                                }
                            }

                            LibraryPage {
                                id: videoSearchPage
                                objectName: "videoSearchPage"
                                x: 0
                                y: Theme.contentPadding
                                width: parent.width
                                height: videoContent.searchHeight
                                visible: backend.videoSearchActive
                                model: backend.videoSearchModel
                                useVideoStyle: true
                                widescreenPosters: true
                                showScrollBar: false
                                scrollEnabled: false
                                verticalContentMargin: 8
                                gridColumns: videoContent.videoColumns
                                showBackButton: false
                                inCollectionView: false
                                isPlaying: backend.isPlaying
                                emptyTitle: "Không tìm thấy video"
                                emptyMessage: "Thử từ khóa khác."
                                onPlayRequested: function(index) { console.log("[DEBUG main.qml] videoSearch playRequested index=" + index); backend.playVideoSearch(index) }
                            }
                        }
                    }

                    Download {
                        id: downloadPage
                        anchors.fill: parent
                        visible: backend.currentPage === 4
                    }


                    SettingsPage {
                        id: settingsPage
                        anchors.fill: parent
                        visible: backend.currentPage === 5
                        mediaRoot: backend.mediaRoot
                        musicDir: backend.musicDir
                        videoDir: backend.videoDir
                        uiConfigPath: uiConfig.configPath
                        ytDlpUpdateStatus: backend.ytDlpUpdateStatus

                        onPickMediaRoot: backend.pickMediaRoot()
                        onOpenUiConfigDir: backend.openUiConfigDir()
                        onUpdateYtDlpRequested: backend.updateYtDlp()
                    }

                    Item {
                        id: podcastPage
                        anchors.fill: parent
                        visible: backend.currentPage === 6

                        PodcastPage {
                            id: podcastContent
                            anchors.fill: parent
                            // PodcastPage tự xử lý internal navigation:
                            // main view / category detail (grid) / playlist detail (series)
                            visible: !backend.inPodcastDetail
                        }

                        PodcastDetailPage {
                            id: podcastDetail
                            anchors.fill: parent
                            visible: backend.inPodcastDetail
                            model: backend.podcastEpisodeModel
                            showTitle: backend.podcastShowTitle
                            showImage: backend.podcastShowImage
                            showDescription: backend.podcastShowDescription
                            showAuthor: backend.podcastShowAuthor

                            onBackClicked: backend.closePodcastDetail()
                            onEpisodeClicked: function(index) { backend.playPodcastEpisode(index) }
                            onDownloadRequested: function(feedUrl, guid) { console.log("[DEBUG main.qml] PodcastDetailPage downloadRequested feedUrl=" + feedUrl + " guid=" + guid); backend.downloadPodcastEpisode(feedUrl, guid) }
                        }
                    }

                    Item {
                        id: bookPage
                        anchors.fill: parent
                        visible: backend.currentPage === 7

                        property bool readerOpen: false
                        property string readerPath: ""
                        property string readerTitle: ""
                        property var readerData: ({})

                        // Book grid view (when reader is closed)
                        LibraryPage {
                            id: bookLibraryPage
                            anchors.fill: parent
                            visible: !bookPage.readerOpen
                            model: backend.bookModel
                            useVinylStyle: false
                            widescreenPosters: false
                            showScrollBar: true
                            inCollectionView: false
                            isPlaying: backend.isPlaying
                            emptyTitle: "Chưa có sách"
                            emptyMessage: "Thêm file sách (PDF, EPUB, TXT) vào thư mục Books."
                            onPlayRequested: function(index) {
                                // Open book reader
                                var data = backend.openBook(index)
                                bookPage.readerData = data
                                bookPage.readerTitle = data.title || ""
                                bookPage.readerPath = data.path || ""
                                bookPage.readerOpen = true
                            }
                            onOpenCollectionRequested: function(index) { backend.openCollection(index) }
                        }

                        // Book reader view (when a book is open)
                        BookReader {
                            id: bookReader
                            anchors.fill: parent
                            visible: bookPage.readerOpen
                            bookPath: bookPage.readerPath
                            bookTitle: bookPage.readerTitle || ""
                            bookAuthor: bookPage.readerData.author || ""
                            chapters: bookPage.readerData.chapters || []
                            onCloseRequested: {
                                bookPage.readerOpen = false
                            }
                        }
                    }
                }
            }
        }

        Item {
            id: playerBarSlot
            Layout.fillWidth: true
            Layout.preferredHeight: backend.playerBarVisible ? Theme.playerBarHeight : 0
            clip: true

            Behavior on Layout.preferredHeight {
                NumberAnimation {
                    duration: 300
                    easing.type: Easing.InOutCubic
                }
            }

            PlayerBar {
                id: playerBar
                anchors.left: parent.left
                anchors.right: parent.right
                height: Theme.playerBarHeight
                y: backend.playerBarVisible ? 0 : height

                Behavior on y {
                    NumberAnimation {
                        duration: 300
                        easing.type: Easing.InOutCubic
                    }
                }

                trackTitle: backend.trackTitle
                trackArtist: backend.trackArtist
                trackThumbnail: backend.trackThumbnail
                isPlaying: backend.isPlaying
                hasMedia: backend.hasMedia
                volumeLevel: backend.volume
                muted: backend.muted
                position: backend.position
                duration: backend.duration
                shuffleOn: backend.shuffleOn
                loopMode: backend.loopMode
                isPodcast: backend.isPodcastMedia
                playbackSpeed: backend.podcastPlaybackSpeed

                onPreviousClicked: backend.previous()
                onPlayClicked: backend.togglePause()
                onNextClicked: backend.next()
                onShuffleClicked: backend.toggleShuffle()
                onLoopClicked: backend.toggleLoop()
                onMuteClicked: backend.toggleMute()
                onVolumeAdjusted: function(v) { backend.setVolume(v) }
                onSeekRequested: function(pos) { backend.seekTo(pos) }
                onSettingsClicked: backend.setCurrentPage(5)
                onSkipBackClicked: backend.seekPodcastRelative(-15)
                onSkipForwardClicked: backend.seekPodcastRelative(30)
                onSpeedChanged: function(speed) { backend.setPodcastPlaybackSpeed(speed) }
            }
        }

    }

    FocusModeScreen {
        id: focusModeScreen
        anchors.fill: parent
    }

    Connections {
        target: focusModeScreen
        function onVideoPlaybackStateChanged(isPlaying) {
            backend.onVideoPlaybackStateChanged(isPlaying)
        }
        function onVideoPositionChanged(positionMs) {
            backend.onVideoPositionChanged(positionMs)
        }
        function onVideoDurationChanged(durationMs) {
            backend.onVideoDurationChanged(durationMs)
        }
    }
}
}
