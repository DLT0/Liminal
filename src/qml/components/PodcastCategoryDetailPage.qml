import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import Liminal 1.0

// Category tab = filter theo thể loại (nhiều-nhiều)
// Playlist tab = collection cố định do collaborator tạo (1-1 với item)
// Hiển thị grid podcast (giống PodcastSuggestionsSection) — KHÔNG phải dạng phim bộ/season.
// Dùng khi user chọn 1 category tab (vd "Công nghệ", "Giáo dục").
Item {
    id: root
    clip: true

    property alias model: gridView.model
    property string categoryTitle: ""
    property int gridColumns: Math.max(2, Math.floor((width - 2 * Theme.contentPadding) / (180 + Theme.cardGap)))

    signal backClicked()

    readonly property int itemCount: gridView.count || 0

    // Grid sizing — đồng bộ với PodcastSuggestionsSection
    readonly property real cellW:  Math.floor((width - 2 * Theme.contentPadding) / gridColumns)
    readonly property real coverH: Math.round(cellW / Theme.videoPosterAspect)
    readonly property real cellH:  coverH + 82 + 8

    ColumnLayout {
        anchors.fill: parent
        spacing: 0

        // ── Header ──────────────────────────────────────────────────────────
        Item {
            Layout.fillWidth: true
            Layout.preferredHeight: 48

            RowLayout {
                anchors.left: parent.left
                anchors.right: parent.right
                anchors.leftMargin: Theme.contentPadding
                anchors.rightMargin: Theme.contentPadding
                anchors.verticalCenter: parent.verticalCenter
                spacing: 8

                IconButton {
                    icon: "arrow_back"
                    iconSize: 22
                    width: 36
                    height: 36
                    onClicked: root.backClicked()
                }

                Text {
                    text: root.categoryTitle || "Thể loại"
                    font.family: Theme.fontFamily
                    font.pixelSize: 20
                    font.weight: Font.Bold
                    color: Theme.textPrimary
                    elide: Text.ElideRight
                    Layout.fillWidth: true
                }

                Text {
                    text: root.itemCount + " podcast"
                    font.family: Theme.fontFamily
                    font.pixelSize: Theme.bodySize
                    color: Theme.textMuted
                }
            }
        }

        // ── Grid ────────────────────────────────────────────────────────────
        Flickable {
            Layout.fillWidth: true
            Layout.fillHeight: true
            Layout.leftMargin: Theme.contentPadding
            Layout.rightMargin: Theme.contentPadding
            Layout.topMargin: 16
            contentWidth: width
            contentHeight: gridView.contentHeight + 16
            clip: true
            boundsBehavior: Flickable.StopAtBounds
            ScrollBar.vertical: ScrollBar { policy: ScrollBar.AsNeeded }
            interactive: contentHeight > height
            visible: root.itemCount > 0

            GridView {
                id: gridView
                width: parent.width
                height: Math.ceil(Math.max(1, root.itemCount) / root.gridColumns) * root.cellH + 8
                clip: false
                interactive: false

                cellWidth: root.cellW
                cellHeight: root.cellH

                delegate: Item {
                    width: gridView.cellWidth - Theme.cardGap
                    height: gridView.cellHeight - 8

                    PodcastCard {
                        anchors.fill: parent
                        title: modelData.title || model.title || ""
                        subtitle: modelData.subtitle || model.subtitle || ""
                        categoryLabel: modelData.categoryLabel || model.categoryLabel || ""
                        imageSource: modelData.image || modelData.imageSource || model.image || model.imageSource || ""
                        downloadPercent: modelData.downloadPercent !== undefined ? modelData.downloadPercent : (modelData.download_percent || (model.download_percent !== undefined ? model.download_percent : (model.downloadPercent || 0)))
                        downloadStatus: modelData.downloadStatus !== undefined ? modelData.downloadStatus : (modelData.download_status || (model.download_status !== undefined ? model.download_status : (model.downloadStatus || "idle")))
                        isDownloading: modelData.isDownloading !== undefined ? modelData.isDownloading : (modelData.is_downloading || (model.is_downloading !== undefined ? model.is_downloading : (model.isDownloading || false)))
                        trackId: modelData.trackId !== undefined ? modelData.trackId : (modelData.track_id || (model.trackId !== undefined ? model.trackId : (model.track_id || "")))
                        audioOnly: modelData.audioOnly !== undefined ? modelData.audioOnly : (model.audioOnly !== undefined ? model.audioOnly : true)

                        onDownloadRequested: backend.downloadPodcastSuggestionById(trackId)
                        onClicked: backend.playPodcastSuggestionById(trackId)
                    }
                }
            }
        }

        // ── Empty state ─────────────────────────────────────────────────────
        Item {
            Layout.fillWidth: true
            Layout.fillHeight: true
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
                    text: "Không có podcast nào"
                    color: Theme.textPrimary
                    font.family: Theme.fontFamily
                    font.pixelSize: 18
                    font.weight: Font.DemiBold
                }

                Text {
                    Layout.fillWidth: true
                    horizontalAlignment: Text.AlignHCenter
                    wrapMode: Text.Wrap
                    text: "Chưa có podcast nào thuộc thể loại này."
                    color: Theme.textMuted
                    font.family: Theme.fontFamily
                    font.pixelSize: Theme.bodySize
                }
            }
        }
    }
}
