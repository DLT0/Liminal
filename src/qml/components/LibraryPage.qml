import QtQuick
import QtQuick.Controls
import Liminal 1.0

Item {
    id: root
    clip: true

    property alias model: grid.model
    property string emptyTitle: "Thư viện trống"
    property string emptyMessage: "Tải media về hoặc thêm file vào playlist đã cấu hình."
    property bool useVinylStyle: false
    property bool useVideoStyle: false
    property bool embedCollectionDetail: true
    property bool widescreenPosters: false
    property bool showBackButton: false
    property string breadcrumb: ""
    property bool inCollectionView: false
    property bool allowCreateCollection: true
    property bool allowMoveToCollection: true
    property string bannerTitle: ""
    property string bannerSubtitle: ""
    property string bannerImage: ""
    property string bannerDescription: ""
    property bool hasPlayableTracks: false
    property bool isPlaying: false
    property bool showScrollBar: true
    property bool scrollEnabled: true
    property bool showShareAction: false
    property bool showPlaylistShare: false
    property bool showTrackShare: false
    property int gridColumns: Theme.gridColumns
    // Allows compact embedded library sections without changing full-page views.
    property int contentMargin: Theme.contentPadding
    property int horizontalContentMargin: contentMargin
    property int verticalContentMargin: contentMargin

    signal playRequested(int index)
    signal openCollectionRequested(int index)
    signal createFolderRequested()
    signal playAllRequested()
    signal shufflePlayRequested()
    signal seriesShareRequested()

    CreateFolderDialog {
        id: createFolderDialog
        parent: Overlay.overlay
        onFolderCreated: {
            if (contextMenu.itemPath)
                moveTargetsPopup.sourcePath = contextMenu.itemPath
        }
    }

    EditMediaDialog {
        id: editDialog
        parent: Overlay.overlay
    }

    MoveTargetsPopup {
        id: moveTargetsPopup
        parent: Overlay.overlay
        videoMode: root.useVideoStyle
        onCreateFolderRequested: createFolderDialog.openDialog(root.useVideoStyle)
        onTargetSelected: function(path) {
            backend.moveMediaToFolder(contextMenu.itemPath, path)
        }
    }

    function openMoveTargetsSubmenu(entryItem) {
        if (!contextMenu.itemPath)
            return
        moveTargetsPopup.sourcePath = contextMenu.itemPath
        if (entryItem) {
            var pt = entryItem.mapToItem(Overlay.overlay, entryItem.width, 0)
            contextMenu.moveSubmenuPos = Qt.point(pt.x, pt.y)
        }
        moveTargetsPopup.x = contextMenu.moveSubmenuPos.x
        moveTargetsPopup.y = contextMenu.moveSubmenuPos.y
        moveTargetsPopup.refreshTargets()
        moveTargetsPopup.open()
    }

    function openContextMenu(index, isCollection, title, artist, itemPath, anchorItem, x, y) {
        contextMenu.itemIndex = index
        contextMenu.isCollection = isCollection
        contextMenu.itemTitle = title
        contextMenu.itemArtist = artist
        contextMenu.itemPath = itemPath
        contextMenu.canMoveToCollection = root.useVideoStyle
            ? backend.mediaCanMoveToSeries(itemPath)
            : backend.mediaCanMoveToPlaylist(itemPath)
        if (!isCollection && contextMenu.canMoveToCollection)
            moveTargetsPopup.sourcePath = itemPath
        else
            moveTargetsPopup.sourcePath = ""
        contextMenu.popup(anchorItem, x, y)
    }

    function openEmptyContextMenu(anchorItem, x, y) {
        if (root.useVideoStyle) return
        emptyContextMenu.popup(anchorItem, x, y)
    }

    StyledMenu {
        id: emptyContextMenu
        StyledMenuItem {
            visible: root.allowCreateCollection
            iconName: "create_new_folder"
            text: root.useVideoStyle ? "Tạo thư mục mới" : "Tạo playlist mới"
            onTriggered: createFolderDialog.openDialog(root.useVideoStyle)
        }
    }

    StyledMenu {
        id: contextMenu
        property int itemIndex: -1
        property bool isCollection: false
        property string itemTitle: ""
        property string itemArtist: ""
        property string itemPath: ""
        property bool canMoveToCollection: true
        property point moveSubmenuPos: Qt.point(0, 0)
        readonly property bool showMoveToCollectionMenu: root.allowMoveToCollection
            && !contextMenu.isCollection
            && contextMenu.canMoveToCollection

        StyledMenuItem {
            iconName: contextMenu.isCollection ? "folder_open" : "play_arrow"
            text: contextMenu.isCollection ? (root.useVideoStyle ? "Mở thư mục" : "Mở playlist") : "Phát"
            font.weight: Font.Bold
            onTriggered: {
                if (contextMenu.isCollection)
                    root.openCollectionRequested(contextMenu.itemIndex)
                else if (root.useVideoStyle && !root.inCollectionView && !contextMenu.isCollection)
                    backend.playVideoMyMovie(contextMenu.itemIndex)
                else
                    root.playRequested(contextMenu.itemIndex)
            }
        }
        StyledMenuItem {
            id: moveToCollectionEntry
            visible: contextMenu.showMoveToCollectionMenu
            enabled: contextMenu.showMoveToCollectionMenu
            iconName: "drive_file_move"
            text: root.useVideoStyle ? "Phân loại vào phim bộ" : "Thêm vào playlist khác"
            showSubmenuArrow: true
            onHoveredChanged: {
                if (hovered)
                    openMoveTargetsSubmenu(moveToCollectionEntry)
            }
            onPressed: {
                // Lưu tọa độ trước khi menu đóng (onTriggered gọi sau khi menu đã đóng)
                var pt = moveToCollectionEntry.mapToItem(Overlay.overlay, moveToCollectionEntry.width, 0)
                contextMenu.moveSubmenuPos = Qt.point(pt.x, pt.y)
            }
            onTriggered: openMoveTargetsSubmenu(null)
        }
        StyledMenuItem {
            iconName: "image"
            text: "Đổi ảnh bìa"
            onTriggered: backend.pickMediaCoverByPath(contextMenu.itemPath)
        }
        StyledMenuItem {
            iconName: "edit"
            text: "Chỉnh sửa thông tin"
            onTriggered: editDialog.openFor(
                contextMenu.itemPath,
                contextMenu.itemTitle,
                contextMenu.itemArtist
            )
        }
        StyledMenuItem {
            visible: root.showShareAction && !contextMenu.isCollection && root.useVideoStyle
            iconName: "share"
            text: "Chia sẻ"
            onTriggered: shareBridge.createShareFromLibraryPath(contextMenu.itemPath)
        }
        StyledMenuItem {
            visible: root.showShareAction && !contextMenu.isCollection && root.useVinylStyle
            iconName: "share"
            text: "Chia sẻ"
            onTriggered: shareBridge.createShareFromMusicPath(contextMenu.itemPath)
        }
        StyledMenuItem {
            visible: root.showShareAction && contextMenu.isCollection && root.useVideoStyle
            iconName: "share"
            text: "Chia sẻ phim bộ"
            onTriggered: shareBridge.createShareFromSeriesPath(contextMenu.itemPath)
        }
        StyledMenuItem {
            visible: root.showShareAction && contextMenu.isCollection && root.useVinylStyle
                && !contextMenu.itemPath.startsWith("__liminal__:")
            iconName: "share"
            text: "Chia sẻ playlist"
            onTriggered: shareBridge.createShareFromPlaylistPath(contextMenu.itemPath)
        }
        StyledMenuSeparator {}
        StyledMenuItem {
            iconName: "delete"
            destructive: true
            text: "Xóa khỏi thư viện"
            onTriggered: backend.deleteMediaByPath(contextMenu.itemPath)
        }
    }

    // Collection detail (inside folder)
    CollectionDetailView {
        id: detailView
        anchors.fill: parent
        visible: root.inCollectionView && root.embedCollectionDetail
        model: grid.model
        bannerTitle: root.bannerTitle
        bannerSubtitle: root.bannerSubtitle
        bannerImage: root.bannerImage
        bannerDescription: root.bannerDescription
        hasPlayableTracks: root.hasPlayableTracks
        isPlaying: root.isPlaying
        useSeriesStyle: root.useVideoStyle && root.inCollectionView
        showPlaylistShare: root.showPlaylistShare && root.inCollectionView && root.useVinylStyle
        showTrackShare: root.showTrackShare && root.inCollectionView && root.useVinylStyle
        onPlayRequested: function(index) { root.playRequested(index) }
        onOpenCollectionRequested: function(index) { root.openCollectionRequested(index) }
        onPlayAllRequested: function() { root.playAllRequested() }
        onShufflePlayRequested: function() { root.shufflePlayRequested() }
        onPlaylistShareRequested: {
            if (backend.currentPlaylistFolderPath)
                shareBridge.createShareFromPlaylistPath(backend.currentPlaylistFolderPath)
        }
        onSeriesShareRequested: root.seriesShareRequested()
    }

    // Lobby grid
    Item {
        id: lobbyView
        anchors.fill: parent
        visible: !root.inCollectionView || !root.embedCollectionDetail

        Row {
            id: breadcrumbRow
            anchors.top: parent.top
            anchors.left: parent.left
            anchors.right: parent.right
            anchors.leftMargin: root.horizontalContentMargin
            anchors.rightMargin: root.horizontalContentMargin
            anchors.topMargin: root.verticalContentMargin
            anchors.bottomMargin: root.verticalContentMargin
            spacing: 10
            visible: root.showBackButton || root.breadcrumb !== ""
            height: visible ? 36 : 0

            IconButton {
                visible: root.showBackButton
                icon: "arrow_back"
                onClicked: backend.goBackLibrary()
            }

            Text {
                anchors.verticalCenter: parent.verticalCenter
                text: root.breadcrumb
                font.family: Theme.fontFamily
                font.pixelSize: Theme.bodySize
                color: Theme.textSecondary
                elide: Text.ElideRight
                width: parent.width - 48
            }
        }

        MouseArea {
            anchors.top: breadcrumbRow.bottom
            anchors.left: parent.left
            anchors.right: parent.right
            anchors.bottom: parent.bottom
            anchors.leftMargin: root.horizontalContentMargin
            anchors.rightMargin: root.horizontalContentMargin
            anchors.topMargin: root.verticalContentMargin
            anchors.bottomMargin: root.verticalContentMargin
            acceptedButtons: Qt.RightButton
            z: -1
            onClicked: function(mouse) {
                if (mouse.button === Qt.RightButton)
                    root.openEmptyContextMenu(lobbyView, mouse.x, mouse.y)
            }
        }

        GridView {
            id: grid
            anchors.top: breadcrumbRow.bottom
            anchors.left: parent.left
            anchors.right: parent.right
            anchors.bottom: parent.bottom
            anchors.leftMargin: root.horizontalContentMargin
            anchors.rightMargin: root.horizontalContentMargin
            anchors.topMargin: root.verticalContentMargin
            anchors.bottomMargin: root.verticalContentMargin
            clip: true
            visible: count > 0

            property int columns: root.gridColumns
            interactive: root.scrollEnabled
            cellWidth: Math.floor((width - (columns - 1) * Theme.cardGap) / columns)
            cellHeight: {
                var w = cellWidth
                if (root.useVideoStyle)
                    return Math.ceil(w / Theme.videoPosterAspect + 62) + 8
                if (root.widescreenPosters)
                    return Math.ceil(Math.max(w / Theme.videoPosterAspect, w * 0.82)) + 8
                if (root.useVinylStyle)
                    return Math.ceil(w + 52) + 8
                return w * 1.05 + 8
            }

            // Keep wheel scrolling reliable with both X11 and Wayland input
            // backends.  Some Linux Qt builds do not forward the native wheel
            // event to GridView's Flickable implementation consistently.
            WheelHandler {
                target: grid
                onWheel: function(event) {
                    var delta = event.pixelDelta.y
                    if (delta === 0)
                        delta = event.angleDelta.y / 2
                    if (delta === 0 || !grid.interactive)
                        return

                    var maximum = Math.max(0, grid.contentHeight - grid.height)
                    grid.contentY = Math.max(0, Math.min(maximum, grid.contentY - delta))
                    event.accepted = true
                }
            }

            delegate: Item {
                id: cell
                width: grid.cellWidth - Theme.cardGap
                height: grid.cellHeight - 8
                clip: true

                property bool isFolder: model.isCollection
                property bool showVinyl: !isFolder && root.useVinylStyle && model.audioOnly
                property bool showArtistFolder: isFolder && root.useVinylStyle
                property string itemPath: model.path

                TapHandler {
                    onTapped: {
                        if (isFolder)
                            root.openCollectionRequested(index)
                        else
                            root.playRequested(index)
                    }
                }

                MouseArea {
                    anchors.fill: parent
                    acceptedButtons: Qt.RightButton
                    z: -1
                    onClicked: function(mouse) {
                        root.openContextMenu(
                            index,
                            isFolder,
                            model.title,
                            model.artist,
                            itemPath,
                            cell,
                            mouse.x,
                            mouse.y
                        )
                    }
                }

                FolderCard {
                    anchors.fill: parent
                    visible: isFolder && !root.useVinylStyle && !root.useVideoStyle
                    title: model.title
                    subtitle: model.subtitle
                    imageSource: model.imageSource
                    accentColor: model.accentColor
                    onClicked: root.openCollectionRequested(index)
                    onContextMenuRequested: function(x, y) {
                        root.openContextMenu(index, true, model.title, model.artist, itemPath, cell, x, y)
                    }
                }

                SeriesCard {
                    anchors.top: parent.top
                    anchors.left: parent.left
                    anchors.right: parent.right
                    visible: isFolder && root.useVideoStyle
                    title: model.title
                    subtitle: model.subtitle
                    imageSource: model.imageSource
                    episodeCount: model.childCount || 0
                    accentColor: model.accentColor
                    onClicked: root.openCollectionRequested(index)
                    onContextMenuRequested: function(x, y) {
                        root.openContextMenu(index, true, model.title, model.artist, itemPath, cell, x, y)
                    }
                }

                ArtistCard {
                    anchors.top: parent.top
                    anchors.left: parent.left
                    anchors.right: parent.right
                    visible: showArtistFolder
                    title: model.title
                    subtitle: model.subtitle
                    trackCount: model.childCount || 0
                    trackThumbnails: model.trackThumbnails || []
                    accentColor: model.accentColor
                    onClicked: root.openCollectionRequested(index)
                    onContextMenuRequested: function(x, y) {
                        root.openContextMenu(index, true, model.title, model.artist, itemPath, cell, x, y)
                    }
                }

                VinylCard {
                    anchors.fill: parent
                    visible: showVinyl
                    clickEnabled: false
                    title: model.title
                    subtitle: model.subtitle
                    imageSource: model.imageSource
                    accentColor: model.accentColor
                }

                VideoCard {
                    anchors.top: parent.top
                    anchors.left: parent.left
                    anchors.right: parent.right
                    visible: !isFolder && root.useVideoStyle
                    clickEnabled: false
                    title: model.title
                    subtitle: model.subtitle
                    duration: model.duration || ""
                    imageSource: model.imageSource
                    accentColor: model.accentColor
                }

                MediaCard {
                    anchors.top: parent.top
                    anchors.left: parent.left
                    anchors.right: parent.right
                    visible: !isFolder && !showVinyl && !root.useVideoStyle
                    clickEnabled: false
                    widescreen: root.widescreenPosters
                    title: model.title
                    subtitle: model.subtitle
                    imageSource: model.imageSource
                    accentColor: model.accentColor
                }
            }

            ScrollBar.vertical: ScrollBar {
                policy: root.showScrollBar ? ScrollBar.AsNeeded : ScrollBar.AlwaysOff
            }
        }

        Item {
            anchors.centerIn: parent
            width: emptyColumn.width + 48
            height: emptyColumn.height + 32
            visible: grid.count === 0

            Column {
                id: emptyColumn
                anchors.centerIn: parent
                spacing: 8

            Text {
                anchors.horizontalCenter: parent.horizontalCenter
                text: root.emptyTitle
                font.family: Theme.fontFamily
                font.pixelSize: Theme.pageTitleSize
                font.weight: Font.Bold
                color: Theme.textPrimary
            }

            Text {
                anchors.horizontalCenter: parent.horizontalCenter
                text: root.emptyMessage
                font.family: Theme.fontFamily
                font.pixelSize: Theme.bodySize
                color: Theme.textMuted
                horizontalAlignment: Text.AlignHCenter
                width: Math.min(parent.width, 420)
                wrapMode: Text.WordWrap
            }

            Text {
                anchors.horizontalCenter: parent.horizontalCenter
                visible: root.allowCreateCollection
                text: root.useVideoStyle
                    ? "Chuột phải để tạo thư mục"
                    : "Chuột phải để tạo playlist"
                font.family: Theme.fontFamily
                font.pixelSize: Theme.captionSize
                color: Theme.textMuted
            }
            }
        }
    }
}
