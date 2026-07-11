import QtQuick
import QtQuick.Controls
import Liminal 1.0

Item {
    id: root

    property alias model: grid.model
    property string emptyTitle: "Thư viện trống"
    property string emptyMessage: "Tải media về hoặc thêm file vào thư mục đã cấu hình."

    signal playRequested(int index)

    GridView {
        id: grid
        anchors.fill: parent
        anchors.margins: Theme.contentPadding
        clip: true
        visible: count > 0

        property int columns: Theme.gridColumns
        cellWidth: Math.floor((width - (columns - 1) * Theme.cardGap) / columns)
        cellHeight: cellWidth * 1.05 + 8

        delegate: MediaCard {
            width: grid.cellWidth - Theme.cardGap
            title: model.title
            subtitle: model.subtitle
            imageSource: model.imageSource
            accentColor: model.accentColor
            onClicked: root.playRequested(index)
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
