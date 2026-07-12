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
    visible: true
    title: "Liminal"
    color: "transparent"
    flags: uiConfig.customTitleBar
        ? (Qt.Window | Qt.FramelessWindowHint)
        : Qt.Window

    property string searchQuery: ""

    onVisibilityChanged: {
        if (visibility === Window.Minimized) {
            backend.minimizeToTray()
        }
    }

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

    RedeemShareDialog {
        id: redeemShareDialog
        parent: Overlay.overlay
        onAccepted: shareBridge.redeemCode(codeField.text)
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
            shareToast.text = message
            shareToast.open()
        }
        function onRedeemSuccess() {
            shareToast.text = "Đã thêm vào danh sách chia sẻ."
            shareToast.open()
        }
    }

    Connections {
        target: backend
        function onCurrentPageChanged() {
            contentHeader.pageTitle = backend.pageTitle
            contentHeader.currentPage = backend.currentPage
            contentHeader.updateForPage(backend.currentPage)
        }
    }

    Rectangle {
        id: windowBg
        anchors.fill: parent
        color: Theme.bgElevated
        radius: 16
        clip: true

        ColumnLayout {
            anchors.fill: parent
            spacing: 0

        TitleBar {
            id: titleBar
            Layout.fillWidth: true
            visible: uiConfig.customTitleBar

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
                visible: uiConfig.sidebarVisible
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

                        // Flickable's children live in its content item.  Give that item
                        // an explicit height so the two embedded LibraryPages cannot end up
                        // with a zero-height anchor binding.
                        Item {
                            id: musicContent
                            width: musicPage.width
                            height: backend.inCollectionView
                                ? musicPage.height
                                : backend.musicSearchActive
                                    ? musicSearchPage.y + musicSearchPage.height + Theme.contentPadding
                                    : musicSinglesPage.y + musicSinglesPage.height + Theme.contentPadding

                            readonly property int musicColumns: Theme.gridColumns
                            readonly property real musicCellWidth: Math.floor(
                                (width - 2 * Theme.contentPadding - (musicColumns - 1) * Theme.cardGap) / musicColumns
                            )
                            readonly property real musicCellHeight: musicCellWidth + 60
                            readonly property real albumsHeight: Math.max(
                                180,
                                Math.ceil((Number(backend.musicAlbumsModel.count) || 0) / musicColumns) * musicCellHeight + 16
                            )
                            readonly property real singlesHeight: Math.max(
                                180,
                                Math.ceil((Number(backend.musicSinglesModel.count) || 0) / musicColumns) * musicCellHeight + 16
                            )
                            readonly property real searchHeight: Math.max(
                                180,
                                Math.ceil((Number(backend.musicSearchModel.count) || 0) / musicColumns) * musicCellHeight + 16
                            )

                            Text {
                                id: albumsTitle
                                x: Theme.contentPadding
                                y: Theme.contentPadding
                                width: parent.width - 2 * Theme.contentPadding
                                text: "Playlist của tôi"
                                font.family: Theme.fontFamily
                                font.pixelSize: 24
                                font.weight: Font.Bold
                                color: Theme.textPrimary
                                visible: !backend.inCollectionView && !backend.musicSearchActive
                            }

                            LibraryPage {
                                id: musicAlbumsPage
                                objectName: "musicAlbumsPage"
                                x: 0
                                y: backend.inCollectionView ? 0 : albumsTitle.y + albumsTitle.height + 4
                                width: parent.width
                                height: backend.inCollectionView ? parent.height : musicContent.albumsHeight
                                visible: backend.inCollectionView || !backend.musicSearchActive
                                model: backend.musicAlbumsModel
                                useVinylStyle: true
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

                            Text {
                                id: singlesTitle
                                x: Theme.contentPadding
                                y: musicAlbumsPage.y + musicAlbumsPage.height + 8
                                width: parent.width - 2 * Theme.contentPadding
                                text: "Đĩa đơn"
                                font.family: Theme.fontFamily
                                font.pixelSize: 24
                                font.weight: Font.Bold
                                color: Theme.textPrimary
                                visible: !backend.inCollectionView && !backend.musicSearchActive
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
                        interactive: videoContent.height > videoPage.height

                        ScrollBar.vertical: ScrollBar { policy: ScrollBar.AsNeeded }

                        Item {
                            id: videoContent
                            width: videoPage.width
                            height: backend.inCollectionView
                                ? videoPage.height
                                : backend.videoSearchActive
                                    ? videoSearchPage.y + videoSearchPage.height + Theme.contentPadding
                                    : videoSeriesPage.y + videoSeriesPage.height + Theme.contentPadding

                            readonly property int videoColumns: Theme.gridColumns
                            readonly property real videoCellWidth: Math.floor(
                                (width - 2 * Theme.contentPadding - (videoColumns - 1) * Theme.cardGap) / videoColumns
                            )
                            readonly property real videoCellHeight: Math.ceil(Math.max(videoCellWidth / Theme.videoPosterAspect, videoCellWidth * 0.82)) + 8

                            readonly property real sharedHeight: Math.max(
                                180,
                                Math.ceil((Number(backend.videoSharedModel.count) || 0) / videoColumns) * videoCellHeight + 16
                            )
                            readonly property real seriesHeight: Math.max(
                                180,
                                Math.ceil((Number(backend.videoSeriesModel.count) || 0) / videoColumns) * videoCellHeight + 16
                            )
                            readonly property real myMoviesHeight: Math.max(
                                180,
                                Math.ceil((Number(backend.videoMyMoviesModel.count) || 0) / videoColumns) * videoCellHeight + 16
                            )
                            readonly property real searchHeight: Math.max(
                                180,
                                Math.ceil((Number(backend.videoSearchModel.count) || 0) / videoColumns) * videoCellHeight + 16
                            )


                            readonly property bool showShared: backend.videoSharedModel.count > 0

                            Text {
                                id: sharedTitle
                                x: Theme.contentPadding
                                y: Theme.contentPadding
                                width: parent.width - 2 * Theme.contentPadding
                                text: "Được chia sẻ với tôi"
                                font.family: Theme.fontFamily
                                font.pixelSize: 24
                                font.weight: Font.Bold
                                color: Theme.textPrimary
                                visible: !backend.inCollectionView && !backend.videoSearchActive && videoContent.showShared
                            }

                            SharedVideosSection {
                                id: videoSharedSection
                                objectName: "videoSharedSection"
                                x: 0
                                y: backend.inCollectionView ? 0 : sharedTitle.y + sharedTitle.height + 4
                                width: parent.width
                                height: backend.inCollectionView ? parent.height : videoContent.sharedHeight
                                visible: backend.inCollectionView || (!backend.videoSearchActive && videoContent.showShared)
                                gridColumns: videoContent.videoColumns
                                model: backend.videoSharedModel
                                onPlayRequested: function(index) { backend.playVideoShared(index) }
                                onDownloadRequested: function(index) { backend.downloadSharedItem(index) }
                                onDismissRequested: function(index) { backend.dismissSharedItem(index) }
                            }

                            Text {
                                id: myMoviesTitle
                                x: Theme.contentPadding
                                y: videoContent.showShared
                                    ? videoSharedSection.y + videoSharedSection.height + 8
                                    : Theme.contentPadding
                                width: parent.width - 2 * Theme.contentPadding
                                text: "Phim của tôi"
                                font.family: Theme.fontFamily
                                font.pixelSize: 24
                                font.weight: Font.Bold
                                color: Theme.textPrimary
                                visible: !backend.inCollectionView && !backend.videoSearchActive
                            }

                            LibraryPage {
                                id: videoMyMoviesPage
                                objectName: "videoMyMoviesPage"
                                x: 0
                                y: myMoviesTitle.y + myMoviesTitle.height + 4
                                width: parent.width
                                height: videoContent.myMoviesHeight
                                visible: !backend.inCollectionView && !backend.videoSearchActive
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
                                onPlayRequested: function(index) { backend.playVideoMyMovie(index) }
                            }

                            Text {
                                id: seriesTitle
                                x: Theme.contentPadding
                                y: videoMyMoviesPage.y + videoMyMoviesPage.height + 8
                                width: parent.width - 2 * Theme.contentPadding
                                text: "Phim bộ"
                                font.family: Theme.fontFamily
                                font.pixelSize: 24
                                font.weight: Font.Bold
                                color: Theme.textPrimary
                                visible: !backend.inCollectionView && !backend.videoSearchActive
                            }

                            LibraryPage {
                                id: videoSeriesPage
                                objectName: "videoSeriesPage"
                                x: 0
                                y: seriesTitle.y + seriesTitle.height + 4
                                width: parent.width
                                height: videoContent.seriesHeight
                                visible: !backend.inCollectionView && !backend.videoSearchActive
                                model: backend.videoSeriesModel
                                useVideoStyle: true
                                widescreenPosters: true
                                showScrollBar: false
                                scrollEnabled: false
                                verticalContentMargin: 8
                                gridColumns: videoContent.videoColumns
                                showBackButton: false
                                inCollectionView: false
                                isPlaying: backend.isPlaying
                                emptyTitle: "Chưa có phim bộ"
                                emptyMessage: "Tạo thư mục trong thư mục Videos để thêm phim bộ."
                                onPlayRequested: function(index) { backend.playMedia(index) }
                                onOpenCollectionRequested: function(index) { backend.openVideoSeries(index) }
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
                                onPlayRequested: function(index) { backend.playVideoSearch(index) }
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

                onPreviousClicked: backend.previous()
                onPlayClicked: backend.togglePause()
                onNextClicked: backend.next()
                onShuffleClicked: backend.toggleShuffle()
                onLoopClicked: backend.toggleLoop()
                onMuteClicked: backend.toggleMute()
                onVolumeAdjusted: function(v) { backend.setVolume(v) }
                onSeekRequested: function(pos) { backend.seekTo(pos) }
                onSettingsClicked: backend.setCurrentPage(5)
            }
        }
    }
}


}
