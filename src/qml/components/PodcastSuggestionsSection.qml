import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import Liminal 1.0

// Grid section podcast dùng PodcastCard.
// cellWidth tính từ chiều rộng thực tế — không hardcode 180px.
// cellHeight dùng tỷ lệ 16:9 để thumbnail YouTube hiển thị đúng.
Item {
    id: root

    property alias model: grid.model
    property var arrayModel: null
    property int gridColumns: Math.max(2, Math.floor(width / (180 + Theme.cardGap)))

    // Grid cố định cellHeight theo tỷ lệ 16:9 — YouTube thumbnail hiển thị đúng tỷ lệ,
    // cover audio (1:1) sẽ center-crop vào khung 16:9 (giống Spotify/Apple Podcasts)
    readonly property real cellWidth:  Math.floor(width / gridColumns)
    readonly property real coverHeight: Math.round(cellWidth / Theme.videoPosterAspect)
    readonly property real cellHeight:  coverHeight + 82 + 8

    property string emptyTitle:   "Chưa có đề xuất"
    property string emptyMessage: "Podcast đề xuất sẽ xuất hiện tại đây."
    property string emptyIcon:    "podcasts"
    property int    emptyMinHeight: Theme.emptyStateMinHeight

    signal downloadRequested(int originalIndex)

    readonly property int itemCount: arrayModel !== null ? (arrayModel.length || 0) : (grid.count || 0)

    implicitHeight: itemCount > 0
        ? Math.ceil(itemCount / gridColumns) * cellHeight + 8
        : emptyMinHeight

    // ── Grid ──────────────────────────────────────────────────────────────────
    GridView {
        id: grid
        anchors.fill: parent
        clip: true
        visible: root.itemCount > 0
        interactive: false

        cellWidth:  root.cellWidth
        cellHeight: root.cellHeight

        model: root.arrayModel !== null ? root.arrayModel : undefined

        delegate: Item {
            width:  root.cellWidth - Theme.cardGap
            height: root.cellHeight - 8

            PodcastCard {
                anchors.fill: parent
                title:          root.arrayModel !== null ? modelData.title          : model.title
                subtitle:       root.arrayModel !== null ? modelData.subtitle       : model.subtitle
                categoryLabel:  root.arrayModel !== null ? (modelData.categoryLabel || "") : (model.categoryLabel || "")
                imageSource:    root.arrayModel !== null ? modelData.imageSource    : model.imageSource
                downloadPercent: root.arrayModel !== null
                    ? (modelData.downloadPercent !== undefined ? modelData.downloadPercent : (modelData.download_percent || 0))
                    : (model.download_percent !== undefined ? model.download_percent : (model.downloadPercent || 0))
                downloadStatus: root.arrayModel !== null
                    ? (modelData.downloadStatus !== undefined ? modelData.downloadStatus : (modelData.download_status || "idle"))
                    : (model.download_status !== undefined ? model.download_status : (model.downloadStatus || "idle"))
                isDownloading: root.arrayModel !== null
                    ? (modelData.isDownloading !== undefined ? modelData.isDownloading : (modelData.is_downloading || false))
                    : (model.is_downloading !== undefined ? model.is_downloading : (model.isDownloading || false))
                trackId: root.arrayModel !== null
                    ? (modelData.trackId !== undefined ? modelData.trackId : (modelData.track_id || ""))
                    : (model.trackId !== undefined ? model.trackId : (model.track_id || ""))
                audioOnly:      root.arrayModel !== null
                    ? (modelData.audioOnly !== undefined ? modelData.audioOnly : true)
                    : (model.audioOnly !== undefined ? model.audioOnly : true)

                onDownloadRequested: {
                    backend.downloadPodcastSuggestionById(trackId)
                }

                onClicked: {
                    backend.playPodcastSuggestionById(trackId)
                }

                onContextMenuRequested: function(x, y) {
                    var path = ""
                    var isDl = false
                    if (root.arrayModel !== null) {
                        path = modelData.localPath || ""
                        isDl = modelData.downloadStatus === "done"
                    } else {
                        path = model.localPath || model.path || ""
                        isDl = model.downloadStatus === "done"
                    }
                    root.openContextMenu(trackId, path, isDl, parent, x, y)
                }
            }
        }
    }

    function openContextMenu(trackId, itemPath, isDownloaded, anchorItem, x, y) {
        contextMenu.trackId = trackId
        contextMenu.itemPath = itemPath
        contextMenu.isDownloaded = isDownloaded
        contextMenu.popup(anchorItem, x, y)
    }

    StyledMenu {
        id: contextMenu
        property string trackId: ""
        property string itemPath: ""
        property bool isDownloaded: false

        StyledMenuItem {
            text: contextMenu.isDownloaded ? "Phát" : "Xem ngay"
            iconName: "play_arrow"
            onTriggered: {
                if (contextMenu.trackId !== "") {
                    backend.playPodcastSuggestionById(contextMenu.trackId)
                }
            }
        }

        StyledMenuSeparator {
            visible: contextMenu.isDownloaded
        }

        StyledMenuItem {
            text: "Xóa khỏi lịch sử"
            iconName: "delete"
            destructive: true
            visible: contextMenu.isDownloaded
            onTriggered: {
                if (contextMenu.itemPath) {
                    backend.deleteMediaByPath(contextMenu.itemPath)
                }
            }
        }
    }

    // ── Empty state ───────────────────────────────────────────────────────────
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
