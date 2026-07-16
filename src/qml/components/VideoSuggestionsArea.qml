import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import Liminal 1.0

// Khối đề xuất Video: danh sách phát (mỗi section = 1 playlist / kênh).
// Đề xuất chung và Shorts được chuyển sang trang Podcast.
Item {
    id: root

    property int gridColumns: Theme.gridColumns
    property alias suggestionsModel: sectionHelpers.videoModel

    signal downloadVideoRequested(int index)

    implicitHeight: contentCol.implicitHeight

    QtObject {
        id: sectionHelpers
        property var videoModel: backend.videoSuggestionsModel

        function itemAt(model, index) {
            if (!model)
                return null
            if (typeof model.itemAt === "function")
                return model.itemAt(index)
            if (typeof model.item_at === "function")
                return model.item_at(index)
            return null
        }

        function toCardItem(item, index) {
            if (!item)
                return null
            return {
                title: item.title || "",
                subtitle: item.subtitle || "",
                categoryLabel: item.category_label || item.categoryLabel || "",
                category: item.category || "",
                imageSource: item.image || item.imageSource || "",
                downloadPercent: item.download_percent !== undefined
                    ? item.download_percent
                    : (item.downloadPercent || 0),
                downloadStatus: item.download_status || item.downloadStatus || "pending",
                isDownloading: item.is_downloading !== undefined
                    ? item.is_downloading
                    : !!item.isDownloading,
                audioOnly: item.audio_only !== undefined
                    ? item.audio_only
                    : (item.audioOnly !== undefined ? item.audioOnly : false),
                originalIndex: index
            }
        }

        // Sections có ít nhất 1 video được gán — group theo playlist_id
        function activeSections() {
            var sections = backend.videoSections || []
            var model = videoModel
            var count = Number(model ? model.count : 0) || 0
            var counts = {}
            for (var i = 0; i < count; i++) {
                var item = itemAt(model, i)
                var plId = (item && (item.playlist_id || item.playlistId)) || ""
                if (plId)
                    counts[plId] = (counts[plId] || 0) + 1
            }
            var out = []
            for (var j = 0; j < sections.length; j++) {
                var s = sections[j]
                if (s.id && counts[s.id] > 0)
                    out.push(s)
            }
            // Section chưa kịp có trong cache nhưng item đã có playlist_id
            for (var key in counts) {
                var known = false
                for (var k = 0; k < out.length; k++) {
                    if (out[k].id === key) {
                        known = true
                        break
                    }
                }
                if (!known && counts[key] > 0) {
                    var sample = null
                    for (var m = 0; m < count; m++) {
                        var it = itemAt(model, m)
                        var itPlId = (it && (it.playlist_id || it.playlistId)) || ""
                        if (it && itPlId === key) {
                            sample = it
                            break
                        }
                    }
                    out.push({
                        id: key,
                        label: (sample && (sample.category_label || sample.categoryLabel))
                            ? (sample.category_label || sample.categoryLabel)
                            : key
                    })
                }
            }
            return out
        }

        function filteredBySection(model, sectionId) {
            var list = []
            var count = Number(model ? model.count : 0) || 0
            for (var i = 0; i < count; i++) {
                var item = itemAt(model, i)
                var plId = (item && (item.playlist_id || item.playlistId)) || ""
                if (item && plId === sectionId) {
                    var card = toCardItem(item, i)
                    if (card)
                        list.push(card)
                }
            }
            return list
        }
    }

    readonly property var activeVideoSections: sectionHelpers.activeSections()

    ColumnLayout {
        id: contentCol
        width: parent.width
        spacing: 0

        // ── Danh sách phát (mỗi section = 1 playlist) ──
        Repeater {
            model: root.activeVideoSections
            delegate: ColumnLayout {
                Layout.fillWidth: true
                spacing: 0
                visible: channelSection.itemCount > 0

                SectionHeader {
                    text: modelData.label
                    Layout.fillWidth: true
                    Layout.leftMargin: Theme.contentPadding
                    Layout.rightMargin: Theme.contentPadding
                }

                Item { Layout.preferredHeight: 8 }

                SuggestionsSection {
                    id: channelSection
                    Layout.fillWidth: true
                    Layout.leftMargin: Theme.contentPadding
                    Layout.rightMargin: Theme.contentPadding
                    arrayModel: sectionHelpers.filteredBySection(
                        backend.videoSuggestionsModel, modelData.id)
                    gridColumns: root.gridColumns
                    emptyMinHeight: 0
                    onDownloadRequested: function(origIdx) {
                        root.downloadVideoRequested(origIdx)
                    }
                }

                Item { Layout.preferredHeight: Theme.sectionSpacing }
            }
        }
    }
}
