import QtQuick
import QtQuick.Controls
import Liminal 1.0

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
    signal focusNextSectionRequested()
    signal focusPreviousSectionRequested()
    signal sidebarFocusRequested()
    signal searchFocusRequested()

    property int selectedIndex: -1
    readonly property bool hasKeyboardFocus: keyboardScope.activeFocus

    onInCollectionViewChanged: {
        if (inCollectionView && keyboardScope.activeFocus)
            Qt.callLater(function() { detailView.activateFocus() })
        else if (!inCollectionView)
            selectedIndex = -1
    }

    function activateFocus(selectLast) {
        if (root.inCollectionView) {
            detailView.activateFocus(selectLast)
            return
        }
        if (grid.count === 0) {
            keyboardScope.forceActiveFocus()
            selectedIndex = -1
            return
        }
        keyboardScope.forceActiveFocus()
        selectedIndex = selectLast ? grid.count - 1 : 0
        grid.positionViewAtIndex(selectedIndex, GridView.Visible)
    }

    function clearSelection() {
        selectedIndex = -1
    }

    function moveSelection(deltaRow, deltaCol) {
        if (grid.count === 0)
            return false

        var cols = grid.columns
        if (selectedIndex < 0)
            selectedIndex = 0

        var row = Math.floor(selectedIndex / cols)
        var col = selectedIndex % cols
        var newRow = row + deltaRow
        var newCol = col + deltaCol

        if (newCol < 0 || newCol >= cols)
            return false

        var newIndex = newRow * cols + newCol
        if (newIndex < 0) {
            focusPreviousSectionRequested()
            return true
        }
        if (newIndex >= grid.count) {
            focusNextSectionRequested()
            return true
        }

        selectedIndex = newIndex
        grid.positionViewAtIndex(newIndex, GridView.Visible)
        return true
    }

    function activateSelectedItem() {
        if (selectedIndex < 0 || selectedIndex >= grid.count)
            return
        grid.positionViewAtIndex(selectedIndex, GridView.Visible)
        var cell = grid.itemAtIndex(selectedIndex)
        if (!cell)
            return
        if (cell.isFolder)
            root.openCollectionRequested(selectedIndex)
        else
            root.playRequested(selectedIndex)
    }

    FocusScope {
        id: keyboardScope
        anchors.fill: parent
        focus: false

        Keys.onPressed: function(event) {
            if (root.inCollectionView)
                return

            switch (event.key) {
            case Qt.Key_Left:
                moveSelection(0, -1)
                event.accepted = true
                break
            case Qt.Key_Right:
                moveSelection(0, 1)
                event.accepted = true
                break
            case Qt.Key_Up:
                moveSelection(-1, 0)
                event.accepted = true
                break
            case Qt.Key_Down:
                moveSelection(1, 0)
                event.accepted = true
                break
            case Qt.Key_Return:
            case Qt.Key_Enter:
            case Qt.Key_Space:
                activateSelectedItem()
                event.accepted = true
                break
            case Qt.Key_Backtab:
                root.sidebarFocusRequested()
                event.accepted = true
                break
            case Qt.Key_Tab:
                root.searchFocusRequested()
                event.accepted = true
                break
            }
        }
    }

    CreateFolderDialog {
        id: createFolderDialog
        parent: Overlay.overlay
    }

    EditMediaDialog {
        id: editDialog
        parent: Overlay.overlay
    }

    ListModel {
        id: moveTargetsModel
    }

    function populateMoveTargets(sourcePath) {
        moveTargetsModel.clear()
        if (!sourcePath)
            return
        var folders = backend.foldersForMove(sourcePath)
        for (var i = 0; i < folders.length; i++)
            moveTargetsModel.append(folders[i])
    }

    function openContextMenu(index, isCollection, title, artist, itemPath, anchorItem, x, y) {
        contextMenu.itemIndex = index
        contextMenu.isCollection = isCollection
        contextMenu.itemTitle = title
        contextMenu.itemArtist = artist
        contextMenu.itemPath = itemPath
        if (!isCollection)
            populateMoveTargets(itemPath)
        else
            moveTargetsModel.clear()
        contextMenu.popup(anchorItem, x, y)
    }

    function openEmptyContextMenu(anchorItem, x, y) {
        emptyContextMenu.popup(anchorItem, x, y)
    }

    StyledMenu {
        id: emptyContextMenu
        StyledMenuItem {
            iconName: "create_new_folder"
            text: "Tạo thư mục mới"
            onTriggered: createFolderDialog.openDialog()
        }
    }

    StyledMenu {
        id: contextMenu
        property int itemIndex: -1
        property bool isCollection: false
        property string itemTitle: ""
        property string itemArtist: ""
        property string itemPath: ""

        StyledMenuItem {
            iconName: contextMenu.isCollection ? "folder_open" : "play_arrow"
            text: contextMenu.isCollection ? "Mở album / playlist" : "Phát"
            onTriggered: {
                if (contextMenu.isCollection)
                    root.openCollectionRequested(contextMenu.itemIndex)
                else
                    root.playRequested(contextMenu.itemIndex)
            }
        }
        StyledMenu {
            id: moveToFolderMenu
            title: "Chuyển vào thư mục"
            enabled: !contextMenu.isCollection && moveTargetsModel.count > 0

            Instantiator {
                model: moveTargetsModel
                delegate: StyledMenuItem {
                    iconName: "folder"
                    required property string title
                    required property string path
                    text: title
                    onTriggered: backend.moveMediaToFolder(contextMenu.itemPath, path)
                }
                onObjectAdded: function(index, object) { moveToFolderMenu.addItem(object) }
                onObjectRemoved: function(index, object) { moveToFolderMenu.removeItem(object) }
            }
        }
        StyledMenuItem {
            iconName: "image"
            text: "Đổi ảnh bìa"
            onTriggered: backend.pickMediaCover(contextMenu.itemIndex)
        }
        StyledMenuItem {
            iconName: "edit"
            text: "Chỉnh sửa thông tin"
            onTriggered: editDialog.openFor(
                contextMenu.itemIndex,
                contextMenu.itemTitle,
                contextMenu.itemArtist
            )
        }
        StyledMenuSeparator {}
        StyledMenuItem {
            iconName: "delete"
            destructive: true
            text: "Xóa khỏi thư viện"
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
        onPlayAllRequested: function() { root.playAllRequested() }
        onShufflePlayRequested: function() { root.shufflePlayRequested() }
        onSidebarFocusRequested: root.sidebarFocusRequested()
        onSearchFocusRequested: root.searchFocusRequested()
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

                property bool isFolder: model.isCollection
                property bool showVinyl: !isFolder && root.useVinylStyle && model.audioOnly
                property bool showArtistFolder: isFolder && root.useVinylStyle
                property string itemPath: model.path
                property bool keyboardSelected: root.hasKeyboardFocus && root.selectedIndex === index

                KeyboardFocusRing {
                    anchors.fill: parent
                    show: keyboardSelected
                    ringRadius: Theme.cardRadius
                    ringWidth: Theme.focusRingWidth
                }

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
                            model.subtitle,
                            itemPath,
                            cell,
                            mouse.x,
                            mouse.y
                        )
                    }
                }

                FolderCard {
                    anchors.fill: parent
                    visible: isFolder && !root.useVinylStyle
                    title: model.title
                    subtitle: model.subtitle
                    imageSource: model.imageSource
                    accentColor: model.accentColor
                    onClicked: root.openCollectionRequested(index)
                    onContextMenuRequested: function(x, y) {
                        root.openContextMenu(index, true, model.title, model.subtitle, itemPath, cell, x, y)
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
                        root.openContextMenu(index, true, model.title, model.subtitle, itemPath, cell, x, y)
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

            KeyboardFocusRing {
                anchors.fill: parent
                show: root.hasKeyboardFocus
                ringRadius: Theme.cardRadius
                ringWidth: Theme.focusRingWidth
                glowOpacity: 0.16
            }

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
                text: "Chuột phải để tạo thư mục · Super+Shift+N · Mũi tên để chọn · Enter để mở/phát"
                font.family: Theme.fontFamily
                font.pixelSize: Theme.captionSize
                color: Theme.textMuted
            }
            }
        }
    }
}
