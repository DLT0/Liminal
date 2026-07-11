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
                        anchors.fill: parent
                        visible: backend.currentPage === 1
                        model: backend.playlistModel
                        emptyTitle: "Playlist trống"
                        emptyMessage: "Tải bài hát về thư mục Playlist hoặc thêm file vào thư mục đã cấu hình."
                        onPlayRequested: function(index) { backend.playMedia(index) }
                    }

                    LibraryPage {
                        anchors.fill: parent
                        visible: backend.currentPage === 2
                        model: backend.musicModel
                        emptyTitle: "Chưa có nhạc"
                        emptyMessage: "Thêm file nhạc vào thư mục Music đã cấu hình trong Settings."
                        onPlayRequested: function(index) { backend.playMedia(index) }
                    }

                    LibraryPage {
                        anchors.fill: parent
                        visible: backend.currentPage === 3
                        model: backend.videoModel
                        emptyTitle: "Chưa có video"
                        emptyMessage: "Thêm file video vào thư mục Videos đã cấu hình trong Settings."
                        onPlayRequested: function(index) { backend.playMedia(index) }
                    }

                    Download {
                        anchors.fill: parent
                        visible: backend.currentPage === 4
                    }


                    SettingsPage {
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
