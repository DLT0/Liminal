import QtQuick
import QtQuick.Controls
import Liminal 1.0

Item {
    id: root

    property alias model: grid.model
    property int gridColumns: Theme.gridColumns
    property int horizontalContentMargin: Theme.contentPadding
    property int verticalContentMargin: 8
    property string emptyTitle: "Chưa có phim chia sẻ"
    property string emptyMessage: "Nhập mã chia sẻ từ bạn bè để xem tại đây."

    signal playRequested(int index)
    signal downloadRequested(int index)
    signal dismissRequested(int index)

    readonly property real cellWidth: Math.floor(
        (width - 2 * horizontalContentMargin - (gridColumns - 1) * Theme.cardGap) / gridColumns
    )
    readonly property real cellHeight: Math.ceil(cellWidth / Theme.videoPosterAspect + 82) + 8

    function openContextMenu(index, anchorItem, x, y) {
        contextMenu.itemIndex = index
        contextMenu.popup(anchorItem, x, y)
    }

    StyledMenu {
        id: contextMenu
        property int itemIndex: -1

        StyledMenuItem {
            iconName: "delete"
            text: "Xóa khỏi danh sách chia sẻ"
            onTriggered: root.dismissRequested(contextMenu.itemIndex)
        }
    }

    GridView {
        id: grid
        anchors.fill: parent
        anchors.leftMargin: horizontalContentMargin
        anchors.rightMargin: horizontalContentMargin
        anchors.topMargin: verticalContentMargin
        anchors.bottomMargin: verticalContentMargin
        clip: true
        visible: count > 0
        interactive: false

        property int columns: root.gridColumns
        cellWidth: root.cellWidth
        cellHeight: root.cellHeight

        delegate: Item {
            width: grid.cellWidth - Theme.cardGap
            height: grid.cellHeight - 8

            SharedVideoCard {
                anchors.fill: parent
                title: model.title
                subtitle: model.subtitle
                imageSource: model.imageSource
                downloadPercent: model.downloadPercent
                downloadStatus: model.downloadStatus
                isDownloading: model.isDownloading
                onPlayRequested: root.playRequested(index)
                onDownloadRequested: root.downloadRequested(index)
                onContextMenuRequested: function(x, y) {
                    root.openContextMenu(index, parent, x, y)
                }
            }
        }
    }

    Column {
        anchors.centerIn: parent
        spacing: 8
        visible: grid.count === 0
        width: parent.width - 2 * horizontalContentMargin

        Text {
            anchors.horizontalCenter: parent.horizontalCenter
            text: root.emptyTitle
            color: Theme.textPrimary
            font.family: Theme.fontFamily
            font.pixelSize: 18
            font.weight: Font.DemiBold
        }

        Text {
            anchors.horizontalCenter: parent.horizontalCenter
            width: parent.width
            horizontalAlignment: Text.AlignHCenter
            wrapMode: Text.Wrap
            text: root.emptyMessage
            color: Theme.textSecondary
            font.family: Theme.fontFamily
            font.pixelSize: Theme.bodySize
        }
    }
}
