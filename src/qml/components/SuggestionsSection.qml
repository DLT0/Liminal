import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import Liminal 1.0

// SuggestionsSection dùng SuggestionCard — dùng chung cho Video và Shorts.
// Với Podcast hãy dùng PodcastSuggestionsSection.
Item {
    id: root

    property alias model: grid.model
    property var arrayModel: null
    property int gridColumns: Theme.gridColumns
    property alias columns: root.gridColumns

    readonly property real cellWidth:  Math.floor((width - (gridColumns - 1) * Theme.cardGap) / gridColumns)
    readonly property real cellHeight: Math.round(cellWidth / Theme.videoPosterAspect) + 72

    property string emptyTitle: "Chưa có đề xuất"
    property string emptyMessage: "Nội dung đề xuất sẽ xuất hiện tại đây."
    property string emptyIcon: "videocam"
    property int emptyMinHeight: Theme.emptyStateMinHeight

    signal downloadRequested(int originalIndex)

    readonly property int itemCount: arrayModel !== null ? (arrayModel.length || 0) : (grid.count || 0)

    implicitHeight: itemCount > 0
        ? Math.ceil(itemCount / gridColumns) * cellHeight + 8
        : emptyMinHeight

    GridView {
        id: grid
        anchors.fill: parent
        clip: true
        visible: root.itemCount > 0
        interactive: false

        cellWidth: root.cellWidth + Theme.cardGap
        cellHeight: root.cellHeight

        model: root.arrayModel !== null ? root.arrayModel : undefined

        delegate: Item {
            width: root.cellWidth
            height: root.cellHeight - 8

            SuggestionCard {
                anchors.fill: parent
                title:          root.arrayModel !== null ? modelData.title          : model.title
                subtitle:       root.arrayModel !== null ? modelData.subtitle       : model.subtitle
                categoryLabel:  root.arrayModel !== null ? (modelData.categoryLabel || "") : (model.categoryLabel || "")
                imageSource:    root.arrayModel !== null ? modelData.imageSource    : model.imageSource
                downloadPercent: root.arrayModel !== null
                    ? (modelData.downloadPercent !== undefined ? modelData.downloadPercent : (modelData.download_percent || 0))
                    : (model.download_percent !== undefined ? model.download_percent : (model.downloadPercent || 0))
                downloadStatus: root.arrayModel !== null
                    ? (modelData.downloadStatus !== undefined ? modelData.downloadStatus : (modelData.download_status || "pending"))
                    : (model.download_status !== undefined ? model.download_status : (model.downloadStatus || "pending"))
                isDownloading: root.arrayModel !== null
                    ? (modelData.isDownloading !== undefined ? modelData.isDownloading : (modelData.is_downloading || false))
                    : (model.is_downloading !== undefined ? model.is_downloading : (model.isDownloading || false))
                audioOnly:      root.arrayModel !== null
                    ? (modelData.audioOnly !== undefined ? modelData.audioOnly : false)
                    : (model.audioOnly !== undefined ? model.audioOnly : false)

                onDownloadRequested: {
                    var i = root.arrayModel !== null ? modelData.originalIndex : index
                    root.downloadRequested(i)
                }
            }
        }
    }

    Item {
        anchors.fill: parent
        visible: root.itemCount === 0

        ColumnLayout {
            anchors.centerIn: parent
            width: Math.min(parent.width, 420)
            spacing: 10

            AppIcon {
                Layout.alignment: Qt.AlignHCenter
                name: root.emptyIcon
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
