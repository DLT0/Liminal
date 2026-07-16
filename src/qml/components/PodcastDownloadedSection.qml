import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import Liminal 1.0

Item {
    id: root

    property alias model: repeater.model
    property int gridColumns: Math.max(2, Math.floor(width / (180 + Theme.cardGap)))
    property alias columns: root.gridColumns
    
    // Tỷ lệ 16:9 cho thumbnail YouTube — giống PodcastSuggestionsSection
    readonly property real cellWidth:  Math.floor((width - (gridColumns - 1) * Theme.cardGap) / gridColumns)
    readonly property real coverHeight: Math.round(cellWidth / Theme.videoPosterAspect)
    readonly property real cellHeight:  coverHeight + 82 + 8

    property int horizontalContentMargin: 0
    property int verticalContentMargin: 0
    property string emptyTitle: "Chưa có podcast nào đã xem"
    property string emptyMessage: "Các tập bạn đã xem sẽ xuất hiện ở đây"

    signal playRequested(int index)

    readonly property int itemCount: repeater.count || 0

    // Chiều cao tự động tính toán chính xác theo số lượng hàng
    implicitHeight: itemCount > 0
        ? Math.ceil(itemCount / columns) * cellHeight + 8
        : Theme.emptyStateMinHeight

    GridView {
        id: repeater
        anchors.fill: parent
        clip: true
        visible: root.itemCount > 0
        interactive: false

        cellWidth: root.cellWidth + Theme.cardGap
        cellHeight: root.cellHeight

        delegate: Item {
            width: root.cellWidth
            height: root.cellHeight - 8

            PodcastCard {
                anchors.fill: parent
                title: model.title
                subtitle: model.subtitle
                categoryLabel: model.categoryLabel || ""
                imageSource: model.imageSource
                progressPercent: Number(model.watchedPercent) || 0
                downloadStatus: "done"
                
                onClicked: root.playRequested(index)
                onContextMenuRequested: function(x, y) {
                    root.openContextMenu(index, model.path, parent, x, y)
                }
            }
        }
    }

    function openContextMenu(index, itemPath, anchorItem, x, y) {
        contextMenu.index = index
        contextMenu.itemPath = itemPath
        contextMenu.popup(anchorItem, x, y)
    }

    StyledMenu {
        id: contextMenu
        property int index: -1
        property string itemPath: ""

        StyledMenuItem {
            text: "Phát"
            iconName: "play_arrow"
            onTriggered: {
                if (contextMenu.index >= 0) {
                    root.playRequested(contextMenu.index)
                }
            }
        }

        StyledMenuSeparator {}

        StyledMenuItem {
            text: "Xóa khỏi lịch sử"
            iconName: "delete"
            destructive: true
            onTriggered: {
                if (contextMenu.itemPath) {
                    backend.deleteMediaByPath(contextMenu.itemPath)
                }
            }
        }
    }

    // Empty state khi rỗng
    Item {
        id: emptyState
        anchors.fill: parent
        visible: root.itemCount === 0

        ColumnLayout {
            anchors.centerIn: parent
            width: Math.min(parent.width, 420)
            spacing: 10

            AppIcon {
                Layout.alignment: Qt.AlignHCenter
                name: "podcasts"
                font.pixelSize: 40
                color: Theme.textMuted
                opacity: 0.55
            }

            Text {
                Layout.fillWidth: true
                horizontalAlignment: Text.AlignHCenter
                text: root.emptyTitle
                color: Theme.textPrimary
                font.family: Theme.fontFamily
                font.pixelSize: 18
                font.weight: Font.DemiBold
            }

            Text {
                Layout.fillWidth: true
                horizontalAlignment: Text.AlignHCenter
                wrapMode: Text.Wrap
                text: root.emptyMessage
                color: Theme.textMuted
                font.family: Theme.fontFamily
                font.pixelSize: Theme.bodySize
            }
        }
    }
}
