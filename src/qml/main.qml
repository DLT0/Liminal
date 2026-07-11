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
    color: Theme.bgTop

    property string searchQuery: ""

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

    Binding { target: Theme; property: "themeIndex"; value: backend.themeIndex }

    Connections {
        target: backend
        function onCurrentPageChanged() {
            contentHeader.pageTitle = backend.pageTitle
            contentHeader.currentPage = backend.currentPage
            contentHeader.updateForPage(backend.currentPage)
        }
    }

    Rectangle {
        anchors.fill: parent
        gradient: Gradient {
            GradientStop { position: 0;   color: Theme.bgTop }
            GradientStop { position: 0.6; color: Theme.bgMid }
            GradientStop { position: 1;   color: Theme.bgBottom }
        }

        // Subtle accent shimmer top-right
        Rectangle {
            anchors.fill: parent
            gradient: Gradient {
                orientation: Gradient.Horizontal
                GradientStop { position: 0.5; color: "transparent" }
                GradientStop { position: 1;   color: Theme.shimmerRight }
            }
        }

        // Subtle accent shimmer left
        Rectangle {
            anchors.fill: parent
            gradient: Gradient {
                orientation: Gradient.Horizontal
                GradientStop { position: 0;   color: Theme.shimmerLeft }
                GradientStop { position: 0.4; color: "transparent" }
            }
        }
    }

    ColumnLayout {
        anchors.fill: parent
        spacing: 0

        RowLayout {
            Layout.fillWidth: true
            Layout.fillHeight: true
            spacing: 0

            Sidebar {
                id: sidebar
                Layout.fillHeight: true
                currentPage: backend.currentPage
                onPageSelected: function(page) {
                    backend.setCurrentPage(page)
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
                }

                Item {
                    Layout.fillWidth: true
                    Layout.fillHeight: true


                    LibraryPage {
                        id: playlistPage
                        anchors.fill: parent
                        visible: backend.currentPage === 1
                        model: backend.playlistModel
                        useVinylStyle: true
                        showBackButton: backend.libraryCanGoBack
                        breadcrumb: backend.libraryBreadcrumb
                        inCollectionView: backend.inCollectionView
                        bannerTitle: backend.collectionBannerTitle
                        bannerSubtitle: backend.collectionBannerSubtitle
                        bannerImage: backend.collectionBannerImage
                        hasPlayableTracks: backend.collectionHasPlayableTracks
                        isPlaying: backend.isPlaying
                        emptyTitle: "Playlist trống"
                        emptyMessage: "Tải bài hát về thư mục Playlist hoặc thêm file / thư mục album vào thư mục đã cấu hình."
                        onPlayRequested: function(index) { backend.playMedia(index) }
                        onOpenCollectionRequested: function(index) { backend.openCollection(index) }
                        onPlayAllRequested: backend.togglePlayCollection()
                        onShufflePlayRequested: backend.playCollectionShuffled()
                    }

                    Flickable {
                        id: musicPage
                        objectName: "musicPage"
                        anchors.fill: parent
                        visible: backend.currentPage === 2
                        clip: true
                        contentWidth: width
                        contentHeight: musicContent.height

                        ScrollBar.vertical: ScrollBar { policy: ScrollBar.AsNeeded }

                        // Flickable's children live in its content item.  Give that item
                        // an explicit height so the two embedded LibraryPages cannot end up
                        // with a zero-height anchor binding.
                        Item {
                            id: musicContent
                            width: musicPage.width
                            height: backend.inCollectionView
                                ? musicPage.height
                                : musicSinglesPage.y + musicSinglesPage.height + Theme.contentPadding

                            readonly property int musicColumns: 5
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

                            Text {
                                id: albumsTitle
                                x: Theme.contentPadding
                                y: Theme.contentPadding
                                width: parent.width - 2 * Theme.contentPadding
                                text: "Album của tôi"
                                font.family: Theme.fontFamily
                                font.pixelSize: 24
                                font.weight: Font.Bold
                                color: Theme.textPrimary
                                visible: !backend.inCollectionView
                            }

                            LibraryPage {
                                id: musicAlbumsPage
                                objectName: "musicAlbumsPage"
                                x: 0
                                y: backend.inCollectionView ? 0 : albumsTitle.y + albumsTitle.height + 4
                                width: parent.width
                                height: backend.inCollectionView ? parent.height : musicContent.albumsHeight
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
                                emptyTitle: "Chưa có album"
                                emptyMessage: "Tạo thư mục album trong thư mục Music để hiển thị tại đây."
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
                                visible: !backend.inCollectionView
                            }

                            LibraryPage {
                                id: musicSinglesPage
                                objectName: "musicSinglesPage"
                                x: 0
                                y: singlesTitle.y + singlesTitle.height + 4
                                width: parent.width
                                height: musicContent.singlesHeight
                                visible: !backend.inCollectionView
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
                                emptyMessage: "Thêm file nhạc trực tiếp vào thư mục Music."
                                onPlayRequested: function(index) { backend.playMusicSingle(index) }
                            }
                        }
                    }

                    LibraryPage {
                        id: videoPage
                        anchors.fill: parent
                        visible: backend.currentPage === 3
                        model: backend.videoModel
                        useVinylStyle: false
                        useVideoStyle: true
                        widescreenPosters: true
                        showBackButton: backend.libraryCanGoBack
                        breadcrumb: backend.libraryBreadcrumb
                        inCollectionView: backend.inCollectionView
                        bannerTitle: backend.collectionBannerTitle
                        bannerSubtitle: backend.collectionBannerSubtitle
                        bannerImage: backend.collectionBannerImage
                        hasPlayableTracks: backend.collectionHasPlayableTracks
                        isPlaying: backend.isPlaying
                        emptyTitle: "Chưa có video"
                        emptyMessage: "Thêm file video vào thư mục Videos đã cấu hình trong Settings."
                        onPlayRequested: function(index) { backend.playMedia(index) }
                        onOpenCollectionRequested: function(index) { backend.openCollection(index) }
                        onPlayAllRequested: backend.togglePlayCollection()
                        onShufflePlayRequested: backend.playCollectionShuffled()
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
                        playlistDir: backend.playlistDir
                        themeIndex: backend.themeIndex
                        ytDlpUpdateStatus: backend.ytDlpUpdateStatus

                        onPickMediaRoot: backend.pickMediaRoot()
                        onThemeSelected: function(index) { backend.setThemeIndex(index) }
                        onUpdateYtDlpRequested: backend.updateYtDlp()
                    }
                }
            }
        }

        PlayerBar {
            Layout.fillWidth: true
            visible: backend.playerBarVisible
            trackTitle: backend.trackTitle
            trackArtist: backend.trackArtist
            isPlaying: backend.isPlaying
            hasMedia: backend.hasMedia
            volumeLevel: backend.volume
            muted: backend.muted
            position: backend.position
            duration: backend.duration
            shuffleOn: backend.shuffleOn
            loopOn: backend.loopOn

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
