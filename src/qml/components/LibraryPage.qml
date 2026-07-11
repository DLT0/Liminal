import QtQuick
import QtQuick.Controls
import Liminal 1.0
import "DragDrop.js" as DragDrop

Item {
    id: root

    property alias model: grid.model
    property string emptyTitle: "Thư viện trống"
    property string emptyMessage: "Tải media về hoặc thêm file vào thư mục đã cấu hình."
    property bool useVinylStyle: false
    property bool useVideoStyle: false
    property bool widescreenPosters: false
    property bool showBackButton: false
    property string breadcrumb: ""
    property bool inCollectionView: false
    property string bannerTitle: ""
    property string bannerSubtitle: ""
    property string bannerImage: ""
    property bool hasPlayableTracks: false
    property bool isPlaying: false
    property bool showScrollBar: true
    property bool scrollEnabled: true
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

    CreateFolderDialog {
        id: createFolderDialog
        parent: Overlay.overlay
    }

    EditMediaDialog {
        id: editDialog
        parent: Overlay.overlay
    }

    function openContextMenu(index, isCollection, title, artist, anchorItem, x, y) {
        contextMenu.itemIndex = index
        contextMenu.isCollection = isCollection
        contextMenu.itemTitle = title
        contextMenu.itemArtist = artist
        contextMenu.popup(anchorItem, x, y)
    }

    function openEmptyContextMenu(anchorItem, x, y) {
        emptyContextMenu.popup(anchorItem, x, y)
    }

    Menu {
        id: emptyContextMenu
        MenuItem {
            text: "Tạo thư mục mới"
            onTriggered: createFolderDialog.openDialog()
        }
    }

    Menu {
        id: contextMenu
        property int itemIndex: -1
        property bool isCollection: false
        property string itemTitle: ""
        property string itemArtist: ""

        MenuItem {
            text: contextMenu.isCollection ? "Mở album / playlist" : "Phát"
            onTriggered: {
                if (contextMenu.isCollection)
                    root.openCollectionRequested(contextMenu.itemIndex)
                else
                    root.playRequested(contextMenu.itemIndex)
            }
        }
        MenuItem {
            text: "Đổi ảnh bìa"
            onTriggered: backend.pickMediaCover(contextMenu.itemIndex)
        }
        MenuItem {
            text: "Sửa tên / tác giả"
            onTriggered: editDialog.openFor(
                contextMenu.itemIndex,
                contextMenu.itemTitle,
                contextMenu.itemArtist
            )
        }
        MenuSeparator {}
        MenuItem {
            text: "Xóa"
            onTriggered: backend.deleteMediaAt(contextMenu.itemIndex)
        }
    }

    // Collection detail (inside folder)
    CollectionDetailView {
        id: detailView
        anchors.fill: parent
        visible: root.inCollectionView
        model: grid.model
        bannerTitle: root.bannerTitle
        bannerSubtitle: root.bannerSubtitle
        bannerImage: root.bannerImage
        hasPlayableTracks: root.hasPlayableTracks
        isPlaying: root.isPlaying
        onPlayRequested: function(index) { root.playRequested(index) }
        onOpenCollectionRequested: function(index) { root.openCollectionRequested(index) }
        onReorderRequested: function(fromIdx, toIdx) { backend.reorderCollectionItems(fromIdx, toIdx) }
        onPlayAllRequested: function() { root.playAllRequested() }
        onShufflePlayRequested: function() { root.shufflePlayRequested() }
    }

    // Lobby grid
    Item {
        id: lobbyView
        anchors.fill: parent
        visible: !root.inCollectionView

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

            property bool fileDragActive: false
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

            delegate: Item {
                id: cell
                width: grid.cellWidth - Theme.cardGap
                height: grid.cellHeight - 8
                opacity: cardDragHandler.active ? 0.38 : 1.0

                property bool isFolder: model.isCollection
                property bool showVinyl: !isFolder && root.useVinylStyle && model.audioOnly
                property bool showArtistFolder: isFolder && root.useVinylStyle
                property string itemPath: model.path
                property string enteringDragPath: ""

                Behavior on opacity {
                    NumberAnimation { duration: 140; easing.type: Easing.OutCubic }
                }

                Drag.active: cardDragHandler.active
                Drag.source: cell
                Drag.dragType: Drag.Automatic
                Drag.supportedActions: Qt.MoveAction
                Drag.keys: ["liminal/media"]
                Drag.mimeData: { "text/plain": itemPath }
                Drag.hotSpot.x: width / 2
                Drag.hotSpot.y: height / 2

                DragHandler {
                    id: cardDragHandler
                    enabled: !isFolder
                    dragThreshold: 8
                    onActiveChanged: grid.fileDragActive = active
                }

                DropArea {
                    id: folderDropArea
                    anchors.fill: parent
                    enabled: isFolder
                    z: grid.fileDragActive ? 50 : -10
                    keys: ["liminal/media"]

                    onEntered: function(drag) {
                        enteringDragPath = DragDrop.readMimePath(drag)
                    }
                    onExited: enteringDragPath = ""
                    onDropped: function(drop) {
                        DragDrop.acceptDrop(drop)
                        var src = DragDrop.readMimePath(drop) || enteringDragPath
                        enteringDragPath = ""
                        if (src && src !== itemPath)
                            backend.moveMediaByPath(src, itemPath)
                    }
                }

                readonly property bool folderDropHighlight: isFolder
                        && folderDropArea.containsDrag
                        && enteringDragPath !== ""
                        && enteringDragPath !== itemPath

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
                        root.openContextMenu(index, isFolder, model.title, model.subtitle, cell, mouse.x, mouse.y)
                    }
                }

                FolderCard {
                    anchors.fill: parent
                    visible: isFolder && !root.useVinylStyle
                    title: model.title
                    subtitle: model.subtitle
                    imageSource: model.imageSource
                    mediaPath: itemPath
                    accentColor: model.accentColor
                    dropActive: folderDropHighlight
                    dropScale: folderDropHighlight ? 1.07 : 1.0
                    onClicked: root.openCollectionRequested(index)
                    onContextMenuRequested: function(x, y) {
                        root.openContextMenu(index, true, model.title, model.subtitle, cell, x, y)
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
                    mediaPath: itemPath
                    accentColor: model.accentColor
                    dropActive: folderDropHighlight
                    dropScale: folderDropHighlight ? 1.07 : 1.0
                    onClicked: root.openCollectionRequested(index)
                    onContextMenuRequested: function(x, y) {
                        root.openContextMenu(index, true, model.title, model.subtitle, cell, x, y)
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

        Column {
            anchors.centerIn: parent
            spacing: 8
            visible: grid.count === 0

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
                text: "Chuột phải để tạo thư mục · Super+Shift+N"
                font.family: Theme.fontFamily
                font.pixelSize: Theme.captionSize
                color: Theme.textMuted
            }
        }
    }
}
