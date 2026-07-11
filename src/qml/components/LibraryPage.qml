import QtQuick
import QtQuick.Controls
import Liminal 1.0

Item {
    id: root

    property alias model: grid.model
    property string emptyTitle: "Thư viện trống"
    property string emptyMessage: "Tải media về hoặc thêm file vào thư mục đã cấu hình."
    property bool useVinylStyle: false
    property bool showBackButton: false
    property string breadcrumb: ""

    signal playRequested(int index)
    signal openCollectionRequested(int index)

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

    Row {
        id: breadcrumbRow
        anchors.top: parent.top
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.margins: Theme.contentPadding
        spacing: 10
        visible: root.showBackButton || root.breadcrumb !== ""
        height: visible ? 36 : 0

        IconButton {
            visible: root.showBackButton
            icon: "arrow_back"
            onClicked: backend.goBackPlaylist()
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

    GridView {
        id: grid
        anchors.top: breadcrumbRow.bottom
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.bottom: parent.bottom
        anchors.margins: Theme.contentPadding
        clip: true
        visible: count > 0

        property int columns: Theme.gridColumns
        cellWidth: Math.floor((width - (columns - 1) * Theme.cardGap) / columns)
        cellHeight: cellWidth * 1.05 + 8

        delegate: Item {
            id: cell
            width: grid.cellWidth - Theme.cardGap
            height: grid.cellHeight - 8

            property bool showVinyl: root.useVinylStyle && model.audioOnly

            VinylCard {
                anchors.fill: parent
                visible: showVinyl
                title: model.title
                subtitle: model.subtitle
                imageSource: model.imageSource
                accentColor: model.accentColor
                onClicked: {
                    if (model.isCollection)
                        root.openCollectionRequested(index)
                    else
                        root.playRequested(index)
                }
                onContextMenuRequested: function(x, y) {
                    root.openContextMenu(index, model.isCollection, model.title, model.subtitle, cell, x, y)
                }
            }

            MediaCard {
                anchors.fill: parent
                visible: !showVinyl
                title: model.title
                subtitle: model.subtitle
                imageSource: model.imageSource
                accentColor: model.accentColor
                onClicked: {
                    if (model.isCollection)
                        root.openCollectionRequested(index)
                    else
                        root.playRequested(index)
                }
                onContextMenuRequested: function(x, y) {
                    root.openContextMenu(index, model.isCollection, model.title, model.subtitle, cell, x, y)
                }
            }
        }

        ScrollBar.vertical: ScrollBar { policy: ScrollBar.AsNeeded }
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
    }
}
