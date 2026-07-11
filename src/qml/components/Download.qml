import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import Liminal 1.0

Item {
    id: root

    Component.onCompleted: {
        if (backend.downloadDependencyError.length > 0)
            errorStatus = backend.downloadDependencyError
    }

    property string intakeMode: "search"   // search | link
    property string mediaType: "music"     // music | video
    property string searchStatus: "idle"   // idle | loading | results | empty
    property string errorStatus: ""
    property string activeDownloadUrl: ""
    property string activeDownloadId: ""
    property bool directDownloadActive: false
    property real directDownloadProgress: 0
    property string directDownloadState: "idle"
    property string directDownloadError: ""
    property bool linkFromResolve: false
    property string playlistFolder: ""
    property bool queuePanelOpen: false
    property int selectedCount: 0

    function recalcSelectedCount() {
        var count = 0
        for (var i = 0; i < results.count; ++i) {
            if (results.get(i).selected)
                count++
        }
        selectedCount = count
    }

    function findQueueIndex(value) {
        for (var i = 0; i < downloadQueue.count; ++i) {
            var row = downloadQueue.get(i)
            if (row.id === value || row.url === value)
                return i
        }
        return -1
    }

    function queueStats() {
        var total = downloadQueue.count
        var done = 0
        var active = 0
        var pending = 0
        for (var i = 0; i < total; ++i) {
            var state = downloadQueue.get(i).state
            if (state === "done")
                done++
            else if (state === "downloading")
                active++
            else if (state === "queued")
                pending++
        }
        return { total: total, done: done, active: active, pending: pending }
    }

    function addToDownloadQueue(items, folder) {
        queuePanelOpen = true
        for (var i = 0; i < items.length; ++i) {
            var item = items[i]
            if (item.in_library || item.inLibrary)
                continue
            var itemUrl = item.url || item.id || ""
            if (!itemUrl)
                continue
            if (findQueueIndex(itemUrl) >= 0)
                continue
            downloadQueue.append({
                id: item.id || "",
                title: item.title || "Không có tiêu đề",
                url: itemUrl,
                batchLabel: folder || "",
                outputFolder: folder || "",
                state: "queued",
                progress: 0,
                error: ""
            })
        }
    }

    function enqueueItems(items, folder) {
        var kind = mediaType === "music" ? "audio" : "video"
        addToDownloadQueue(items, folder)
        for (var i = 0; i < items.length; ++i) {
            var item = items[i]
            if (item.in_library || item.inLibrary)
                continue
            var itemUrl = (item.url || item.id || "").trim()
            if (!itemUrl)
                continue
            markDownloadQueued(itemUrl, item.title || "", folder || "")
            backend.downloadMedia(itemUrl, kind, folder || "")
        }
    }

    function queueLinkInput(url) {
        var trimmed = url.trim()
        if (!trimmed.match(/^https?:\/\/.+/)) {
            errorStatus = "Link không hợp lệ. Hãy dán URL đầy đủ bắt đầu bằng http:// hoặc https://."
            return
        }
        errorStatus = ""
        queuePanelOpen = true
        backend.queueLink(trimmed, mediaType)
    }

    function clearFinishedQueue() {
        for (var i = downloadQueue.count - 1; i >= 0; --i) {
            var state = downloadQueue.get(i).state
            if (state === "done" || state === "error")
                downloadQueue.remove(i)
        }
    }

    function toggleSelection(index) {
        var row = results.get(index)
        results.setProperty(index, "selected", !row.selected)
        recalcSelectedCount()
    }

    function selectAllResults(select) {
        for (var i = 0; i < results.count; ++i) {
            var row = results.get(i)
            if (row.downloadState === "library" || row.downloadState === "done")
                continue
            results.setProperty(i, "selected", select)
        }
        recalcSelectedCount()
    }

    function downloadSelected() {
        var selected = []
        for (var i = 0; i < results.count; ++i) {
            var row = results.get(i)
            if (!row.selected)
                continue
            if (row.downloadState !== "idle" && row.downloadState !== "error")
                continue
            selected.push({
                id: row.id,
                title: row.title,
                url: row.url,
                inLibrary: row.inLibrary
            })
        }
        if (selected.length === 0)
            return
        enqueueItems(selected, playlistFolder)
        selectAllResults(false)
    }

    function formatDuration(value) {
        var seconds = Number(value || 0)
        if (!seconds)
            return "--:--"
        var minutes = Math.floor(seconds / 60)
        var remainder = Math.floor(seconds % 60)
        return minutes + ":" + (remainder < 10 ? "0" : "") + remainder
    }

    function findResultIndex(value) {
        for (var i = 0; i < results.count; ++i) {
            if (results.get(i).id === value || results.get(i).url === value)
                return i
        }
        return -1
    }

    function markDownloadQueued(url, title, folder) {
        activeDownloadUrl = url
        var idx = findResultIndex(url)
        if (idx >= 0) {
            activeDownloadId = results.get(idx).id
            results.setProperty(idx, "downloadState", "queued")
            results.setProperty(idx, "downloadProgress", 0)
            results.setProperty(idx, "downloadError", "")
            title = title || results.get(idx).title
        } else {
            directDownloadActive = true
            directDownloadProgress = 0
            directDownloadState = "queued"
            directDownloadError = ""
        }
        if (findQueueIndex(url) < 0) {
            queuePanelOpen = true
            downloadQueue.append({
                id: idx >= 0 ? results.get(idx).id : "",
                title: title || "Đang tải…",
                url: url,
                batchLabel: folder || playlistFolder || "",
                outputFolder: folder || playlistFolder || "",
                state: "queued",
                progress: 0,
                error: ""
            })
        }
    }

    function markDownloadActive(url) {
        activeDownloadUrl = url
        var idx = findResultIndex(url)
        if (idx < 0) {
            directDownloadState = "downloading"
            return
        }

        activeDownloadId = results.get(idx).id
        results.setProperty(idx, "downloadState", "downloading")
        results.setProperty(idx, "downloadProgress", 0)
        results.setProperty(idx, "downloadError", "")
    }

    function playlistDownloadStats() {
        var total = results.count
        var done = 0
        var active = 0
        for (var i = 0; i < total; ++i) {
            var state = results.get(i).downloadState
            if (state === "done")
                done++
            else if (state === "queued" || state === "downloading")
                active++
        }
        return { total: total, done: done, active: active }
    }

    function populateResults(items) {
        results.clear()
        for (var i = 0; i < items.length; ++i) {
            var item = items[i]
            var inLibrary = Boolean(item.in_library)
            results.append({
                id: item.id || "",
                title: item.title || "Không có tiêu đề",
                artist: item.artist || "",
                duration: item.duration || "--:--",
                thumbnail: item.thumbnail_url || "",
                url: item.url || "",
                inLibrary: inLibrary,
                selected: false,
                downloadState: inLibrary ? "library" : "idle",
                downloadProgress: 0,
                downloadError: ""
            })
        }
        selectedCount = 0
        searchStatus = results.count > 0 ? "results" : "empty"
    }

    function startDownload(url, forcedKind) {
        var trimmed = url.trim()
        if (!trimmed.match(/^https?:\/\/.+/)) {
            errorStatus = "Link không hợp lệ. Hãy dán URL đầy đủ bắt đầu bằng http:// hoặc https://."
            return
        }

        var kind = forcedKind || mediaType
        errorStatus = ""

        if (kind === "music") {
            markDownloadQueued(trimmed, "", playlistFolder)
            backend.downloadMedia(trimmed, "audio", playlistFolder)
        } else {
            videoQualityPopup.targetUrl = trimmed
            videoQualityPopup.outputFolder = playlistFolder
            videoQualityPopup.open()
        }
    }

    function submitLink(url) {
        var trimmed = url.trim()
        if (!trimmed.match(/^https?:\/\/.+/)) {
            errorStatus = "Link không hợp lệ. Hãy dán URL đầy đủ bắt đầu bằng http:// hoặc https://."
            return
        }

        errorStatus = ""
        linkFromResolve = true
        playlistFolder = ""
        searchStatus = "loading"
        backend.resolveLink(trimmed, mediaType)
    }

    function queueCurrentResults() {
        var batch = []
        for (var i = 0; i < results.count; ++i) {
            var row = results.get(i)
            if (row.inLibrary)
                continue
            if (row.downloadState !== "idle" && row.downloadState !== "error")
                continue
            batch.push({
                id: row.id,
                title: row.title,
                url: row.url,
                inLibrary: row.inLibrary
            })
        }
        if (batch.length === 0)
            return
        enqueueItems(batch, playlistFolder)
    }

    function downloadAllFromList() {
        var batch = []
        for (var i = 0; i < results.count; ++i) {
            var row = results.get(i)
            if (row.downloadState !== "idle" && row.downloadState !== "error")
                continue
            batch.push({
                id: row.id,
                title: row.title,
                url: row.url,
                inLibrary: row.inLibrary
            })
        }
        enqueueItems(batch, playlistFolder)
    }

    function runSearch(text) {
        var query = text.trim()
        if (query.length === 0) {
            results.clear()
            searchStatus = "idle"
            return
        }
        searchStatus = "loading"
        backend.searchOnline(query, mediaType)
    }

    ListModel { id: results }
    ListModel { id: downloadQueue }

    Timer {
        id: errorTimer
        interval: 5000
        repeat: false
        onTriggered: root.errorStatus = ""
    }

    Connections {
        target: backend

        function onSearchResults(items) {
            root.errorStatus = ""
            root.populateResults(items)
            root.linkFromResolve = root.intakeMode === "link" && results.count > 0
        }

        function onPlaylistLinkReady(folder, items) {
            root.errorStatus = ""
            root.playlistFolder = folder || ""
            root.linkFromResolve = true
            root.populateResults(items)
        }

        function onPlaylistQueued(folder, mediaType, items) {
            root.errorStatus = ""
            root.addToDownloadQueue(items, folder || "")
            for (var i = 0; i < items.length; ++i) {
                var item = items[i]
                if (item.in_library || item.inLibrary)
                    continue
                root.markDownloadQueued(item.url || item.id || "")
            }
        }

        function onLinkQueueError(url, message) {
            root.errorStatus = message || "Không thể thêm link vào hàng đợi."
            errorTimer.restart()
        }

        function onSearchError(message) {
            root.errorStatus = message || (root.intakeMode === "link"
                ? "Không thể đọc link."
                : "Không thể tìm kiếm media.")
            root.searchStatus = "idle"
            root.linkFromResolve = false
            root.playlistFolder = ""
            errorTimer.restart()
        }

        function onDownloadJobStarted(url) {
            root.markDownloadActive(url)
            var qIdx = root.findQueueIndex(url)
            if (qIdx >= 0)
                downloadQueue.setProperty(qIdx, "state", "downloading")
        }

        function onDownloadJobRequeued(url) {
            root.markDownloadQueued(url)
            var qIdx = root.findQueueIndex(url)
            if (qIdx >= 0)
                downloadQueue.setProperty(qIdx, "state", "queued")
        }

        function onDownloadProgress(videoId, percent) {
            var value = Math.max(0, Math.min(100, Number(percent) || 0))
            var idx = root.findResultIndex(videoId)
            if (idx >= 0)
                results.setProperty(idx, "downloadProgress", value)
            else if (root.directDownloadActive && root.directDownloadState === "downloading")
                root.directDownloadProgress = value
            var qIdx = root.findQueueIndex(videoId)
            if (qIdx >= 0)
                downloadQueue.setProperty(qIdx, "progress", value)
        }

        function onDownloadFinished(videoId, filePath) {
            var idx = root.findResultIndex(videoId)
            if (idx >= 0) {
                results.setProperty(idx, "downloadState", "done")
                results.setProperty(idx, "downloadProgress", 100)
                results.setProperty(idx, "inLibrary", true)
            }
            if (root.directDownloadActive && root.directDownloadState === "downloading") {
                root.directDownloadProgress = 100
                root.directDownloadState = "done"
            }
            var qIdx = root.findQueueIndex(videoId)
            if (qIdx >= 0) {
                downloadQueue.setProperty(qIdx, "state", "done")
                downloadQueue.setProperty(qIdx, "progress", 100)
            }
            root.activeDownloadUrl = ""
            root.activeDownloadId = ""
        }

        function onDownloadError(videoId, message) {
            root.errorStatus = message || "Tải xuống thất bại."
            var idx = root.findResultIndex(videoId || root.activeDownloadId || root.activeDownloadUrl)
            if (idx >= 0) {
                results.setProperty(idx, "downloadState", "error")
                results.setProperty(idx, "downloadError", root.errorStatus)
            }
            if (root.directDownloadActive && root.directDownloadState === "downloading") {
                root.directDownloadState = "error"
                root.directDownloadError = root.errorStatus
            }
            var qIdx = root.findQueueIndex(videoId || root.activeDownloadUrl)
            if (qIdx >= 0) {
                downloadQueue.setProperty(qIdx, "state", "error")
                downloadQueue.setProperty(qIdx, "error", root.errorStatus)
            }
            root.activeDownloadUrl = ""
            root.activeDownloadId = ""
            errorTimer.restart()
        }
    }

    component SegmentedButton: Rectangle {
        id: segBtn
        property string label: ""
        property string iconName: ""
        property bool selected: false

        signal tapped()

        implicitWidth: row.implicitWidth + 24
        implicitHeight: 30
        radius: 6
        color: selected ? Theme.glassStrong : "transparent"

        Row {
            id: row
            anchors.centerIn: parent
            spacing: 6

            AppIcon {
                name: segBtn.iconName
                color: segBtn.selected ? Theme.textPrimary : Theme.textSecondary
                font.pixelSize: 13
            }

            Text {
                text: segBtn.label
                anchors.verticalCenter: parent.verticalCenter
                font.family: Theme.fontFamily
                font.pixelSize: Theme.captionSize
                font.weight: segBtn.selected ? Font.DemiBold : Font.Normal
                color: segBtn.selected ? Theme.textPrimary : Theme.textSecondary
            }
        }

        MouseArea {
            anchors.fill: parent
            cursorShape: Qt.PointingHandCursor
            onClicked: segBtn.tapped()
        }
    }

    component WaveformProgress: Item {
        property real progress: 0
        property string state: "downloading"

        implicitWidth: 200
        implicitHeight: 24

        readonly property int barCount: 24
        readonly property int filledCount: Math.round((progress / 100) * barCount)

        function barHeight(index) {
            var seed = Math.sin(index * 12.9898) * 43758.5453
            return 0.3 + Math.abs(seed - Math.floor(seed)) * 0.7
        }

        Row {
            anchors.fill: parent
            spacing: 2

            Repeater {
                model: barCount
                delegate: Item {
                    required property int index
                    width: (parent.width - (barCount - 1) * parent.spacing) / barCount
                    height: parent.height

                    Rectangle {
                        anchors.bottom: parent.bottom
                        width: parent.width
                        height: parent.height * barHeight(index)
                        radius: width / 2
                        visible: index >= filledCount
                        color: Theme.sliderTrack
                    }

                    Rectangle {
                        anchors.bottom: parent.bottom
                        width: parent.width
                        height: parent.height * barHeight(index)
                        radius: width / 2
                        visible: index < filledCount && state === "error"
                        color: "#F87171"
                    }

                    Rectangle {
                        anchors.bottom: parent.bottom
                        width: parent.width
                        height: parent.height * barHeight(index)
                        radius: width / 2
                        visible: index < filledCount && state !== "error"
                        gradient: Gradient {
                            orientation: Gradient.Vertical
                            GradientStop { position: 0; color: Theme.accentStart }
                            GradientStop { position: 1; color: Theme.accentEnd }
                        }
                    }
                }
            }
        }
    }

    Popup {
        id: videoQualityPopup
        parent: Overlay.overlay
        modal: true
        focus: true
        closePolicy: Popup.CloseOnEscape | Popup.CloseOnPressOutside
        padding: 24
        width: 460
        height: qualityPopupContent.implicitHeight + topPadding + bottomPadding
        x: Math.round((parent.width - width) / 2)
        y: Math.round((parent.height - height) / 2)

        property string targetUrl: ""
        property string outputFolder: ""

        readonly property var qualityOptions: [
            { value: "480",  label: "480p", size: "~80MB",  recommended: false },
            { value: "720",  label: "720p", size: "~150MB", recommended: false },
            { value: "1080", label: "FHD",  size: "~350MB", recommended: true },
            { value: "1440", label: "2K",   size: "~600MB", recommended: false },
            { value: "2160", label: "4K",   size: "~1.2GB", recommended: false },
            { value: "best", label: "Max",  size: "Tối đa", recommended: false }
        ]

        function currentQualityOption() {
            for (var i = 0; i < qualityOptions.length; ++i) {
                if (qualityOptions[i].value === backend.downloadQuality)
                    return qualityOptions[i]
            }
            return qualityOptions[2]
        }

        function qualityMetaText(option) {
            var parts = [option.size]
            if (option.recommended)
                parts.push("Khuyến nghị")
            return parts.join(" · ")
        }

        background: Rectangle {
            color: Theme.cardBg
            border.color: Theme.cardBorder
            border.width: 1
            radius: Theme.cardRadius
        }

        ColumnLayout {
            id: qualityPopupContent
            width: videoQualityPopup.availableWidth
            spacing: 18

            Item {
                Layout.fillWidth: true
                Layout.preferredHeight: 20

                Text {
                    id: titleText
                    anchors.horizontalCenter: parent.horizontalCenter
                    text: "Chọn chất lượng Video"
                    font.family: Theme.fontFamily
                    font.pixelSize: 16
                    font.weight: Font.DemiBold
                    color: Theme.textPrimary
                }

                AppIcon {
                    anchors.right: parent.right
                    anchors.verticalCenter: parent.verticalCenter
                    name: "layers"
                    color: Theme.textMuted
                    font.pixelSize: 16
                }
            }

            Column {
                Layout.fillWidth: true
                spacing: 10

                Item {
                    id: qualitySegment
                    width: parent.width
                    height: 34

                    Rectangle {
                        anchors.top: parent.top
                        width: parent.width
                        height: 1
                        color: Theme.glassStrongBorder
                    }

                    Row {
                        id: qualityRow
                        anchors.top: parent.top
                        anchors.topMargin: 1
                        width: parent.width
                        height: parent.height - 2

                        Repeater {
                            model: videoQualityPopup.qualityOptions

                            delegate: Item {
                                required property var modelData
                                required property int index

                                width: qualityRow.width / videoQualityPopup.qualityOptions.length
                                height: qualityRow.height

                                readonly property bool selected:
                                    backend.downloadQuality === modelData.value

                                Rectangle {
                                    visible: index > 0
                                    x: 0
                                    width: 1
                                    height: parent.height * 0.55
                                    anchors.verticalCenter: parent.verticalCenter
                                    color: Theme.glassStrongBorder
                                }

                                Text {
                                    anchors.centerIn: parent
                                    text: modelData.label
                                    font.family: "JetBrains Mono, Cascadia Mono, Consolas, monospace"
                                    font.pixelSize: 11
                                    font.weight: selected ? Font.Bold : Font.Normal
                                    color: selected ? Theme.textPrimary : Theme.textMuted
                                }

                                Rectangle {
                                    anchors.bottom: parent.bottom
                                    anchors.horizontalCenter: parent.horizontalCenter
                                    width: selected ? parent.width * 0.72 : 0
                                    height: 2
                                    radius: 1
                                    color: Theme.accentStart
                                    Behavior on width {
                                        NumberAnimation { duration: 160; easing.type: Easing.OutCubic }
                                    }
                                }

                                MouseArea {
                                    anchors.fill: parent
                                    cursorShape: Qt.PointingHandCursor
                                    hoverEnabled: true
                                    onClicked: backend.setDownloadQuality(modelData.value)
                                }
                            }
                        }
                    }

                    Rectangle {
                        anchors.bottom: parent.bottom
                        width: parent.width
                        height: 1
                        color: Theme.glassStrongBorder
                    }
                }

                Text {
                    id: qualityMetaText
                    anchors.horizontalCenter: parent.horizontalCenter
                    text: videoQualityPopup.qualityMetaText(videoQualityPopup.currentQualityOption())
                    font.family: Theme.fontFamily
                    font.pixelSize: Theme.captionSize
                    color: Theme.textMuted
                }
            }

            RowLayout {
                Layout.fillWidth: true
                Layout.topMargin: 4
                Layout.preferredHeight: 32
                spacing: 0

                Item {
                    Layout.preferredWidth: cancelLabel.implicitWidth + 16
                    Layout.preferredHeight: 32

                    Text {
                        id: cancelLabel
                        anchors.centerIn: parent
                        text: "[ Huỷ ]"
                        font.family: "JetBrains Mono, Cascadia Mono, Consolas, monospace"
                        font.pixelSize: Theme.bodySize
                        color: cancelHover.containsMouse ? Theme.textPrimary : Theme.textSecondary
                    }

                    MouseArea {
                        id: cancelHover
                        anchors.fill: parent
                        hoverEnabled: true
                        cursorShape: Qt.PointingHandCursor
                        onClicked: videoQualityPopup.close()
                    }
                }

                Item { Layout.fillWidth: true }

                Item {
                    Layout.preferredWidth: downloadLabel.implicitWidth + 16
                    Layout.preferredHeight: 32

                    Text {
                        id: downloadLabel
                        anchors.centerIn: parent
                        text: "[ Tải ngay ]"
                        font.family: "JetBrains Mono, Cascadia Mono, Consolas, monospace"
                        font.pixelSize: Theme.bodySize
                        font.weight: Font.DemiBold
                        color: downloadHover.containsMouse ? Theme.accentCyan : Theme.textPrimary
                    }

                    MouseArea {
                        id: downloadHover
                        anchors.fill: parent
                        hoverEnabled: true
                        cursorShape: Qt.PointingHandCursor
                        onClicked: {
                            root.markDownloadQueued(
                                videoQualityPopup.targetUrl,
                                "",
                                videoQualityPopup.outputFolder)
                            backend.downloadMedia(
                                videoQualityPopup.targetUrl,
                                "video",
                                videoQualityPopup.outputFolder)
                            videoQualityPopup.close()
                        }
                    }
                }
            }
        }
    }

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: Theme.contentPadding
        anchors.topMargin: 0
        spacing: 16

        Rectangle {
            id: queuePanel
            Layout.fillWidth: true
            visible: downloadQueue.count > 0 || root.queuePanelOpen
            implicitHeight: queueColumn.implicitHeight + 20
            radius: Theme.cardRadius
            color: Theme.glassFill
            border.color: Theme.cardBorder
            border.width: 1

            ColumnLayout {
                id: queueColumn
                anchors.fill: parent
                anchors.margins: 10
                spacing: 8

                RowLayout {
                    Layout.fillWidth: true
                    spacing: 8

                    AppIcon {
                        name: "queue_music"
                        color: Theme.accentStart
                        font.pixelSize: 18
                    }

                    Text {
                        Layout.fillWidth: true
                        text: {
                            var stats = root.queueStats()
                            if (stats.total === 0)
                                return "Hàng đợi tải xuống"
                            var parts = [stats.done + "/" + stats.total + " hoàn tất"]
                            if (stats.active > 0) {
                                var activeText = stats.active + " đang tải"
                                if (backend.downloadConcurrency > 1)
                                    activeText += " (song song)"
                                parts.push(activeText)
                            }
                            if (stats.pending > 0)
                                parts.push(stats.pending + " chờ")
                            return "Hàng đợi · " + parts.join(" · ")
                        }
                        font.family: Theme.fontFamily
                        font.pixelSize: Theme.bodySize
                        font.weight: Font.DemiBold
                        color: Theme.textPrimary
                        elide: Text.ElideRight
                    }

                    Rectangle {
                        Layout.preferredWidth: queueToggleLabel.implicitWidth + 16
                        Layout.preferredHeight: 28
                        radius: 6
                        visible: downloadQueue.count > 0
                        color: queueToggleHover.containsMouse ? Theme.glassStrong : "transparent"

                        Text {
                            id: queueToggleLabel
                            anchors.centerIn: parent
                            text: root.queuePanelOpen ? "Thu gọn" : "Mở rộng"
                            font.family: Theme.fontFamily
                            font.pixelSize: Theme.captionSize
                            color: Theme.textSecondary
                        }

                        MouseArea {
                            id: queueToggleHover
                            anchors.fill: parent
                            hoverEnabled: true
                            cursorShape: Qt.PointingHandCursor
                            onClicked: root.queuePanelOpen = !root.queuePanelOpen
                        }
                    }

                    Rectangle {
                        Layout.preferredWidth: clearQueueLabel.implicitWidth + 16
                        Layout.preferredHeight: 28
                        radius: 6
                        visible: downloadQueue.count > 0
                        color: clearQueueHover.containsMouse ? Theme.glassStrong : "transparent"

                        Text {
                            id: clearQueueLabel
                            anchors.centerIn: parent
                            text: "Xóa xong"
                            font.family: Theme.fontFamily
                            font.pixelSize: Theme.captionSize
                            color: Theme.textMuted
                        }

                        MouseArea {
                            id: clearQueueHover
                            anchors.fill: parent
                            hoverEnabled: true
                            cursorShape: Qt.PointingHandCursor
                            onClicked: root.clearFinishedQueue()
                        }
                    }
                }

                ListView {
                    id: queueList
                    Layout.fillWidth: true
                    Layout.preferredHeight: Math.min(220, count > 0 ? contentHeight : 0)
                    visible: root.queuePanelOpen && downloadQueue.count > 0
                    spacing: 6
                    clip: true
                    model: downloadQueue

                    delegate: Rectangle {
                        id: queueRow
                        width: queueList.width
                        height: queueRowContent.implicitHeight + 12
                        radius: 8
                        color: Theme.bgTop
                        border.color: Theme.cardBorder
                        border.width: 1

                        required property string id
                        required property string title
                        required property string url
                        required property string batchLabel
                        required property string state
                        required property real progress
                        required property string error

                        ColumnLayout {
                            id: queueRowContent
                            anchors.fill: parent
                            anchors.margins: 8
                            spacing: 4

                            RowLayout {
                                Layout.fillWidth: true
                                spacing: 8

                                Text {
                                    Layout.fillWidth: true
                                    text: title
                                    font.family: Theme.fontFamily
                                    font.pixelSize: Theme.captionSize
                                    font.weight: Font.Medium
                                    color: Theme.textPrimary
                                    elide: Text.ElideRight
                                }

                                Text {
                                    visible: batchLabel.length > 0
                                    text: batchLabel
                                    font.family: Theme.fontFamily
                                    font.pixelSize: 10
                                    color: Theme.textMuted
                                    elide: Text.ElideRight
                                    maximumLineCount: 1
                                    Layout.maximumWidth: 120
                                }

                                AppIcon {
                                    name: state === "done" ? "check"
                                         : state === "downloading" ? "progress_activity"
                                         : state === "error" ? "error"
                                         : "schedule"
                                    color: state === "done" ? "#34D399"
                                           : state === "error" ? "#F87171"
                                           : state === "downloading" ? Theme.accentStart
                                           : Theme.textMuted
                                    font.pixelSize: 14

                                    RotationAnimation on rotation {
                                        running: state === "downloading"
                                        from: 0
                                        to: 360
                                        duration: 900
                                        loops: Animation.Infinite
                                    }
                                }
                            }

                            WaveformProgress {
                                Layout.fillWidth: true
                                visible: state === "downloading" || state === "queued"
                                progress: progress
                                state: state
                            }
                        }
                    }
                }
            }
        }

        // In link mode the intake card stays centered. Collapsing this spacer
        // moves it to the top when Search is selected, leaving room for results.
        Item {
            id: intakeTopSpacer
            Layout.fillWidth: true
            Layout.preferredHeight: implicitHeight
            implicitHeight: root.searchStatus === "results"
                ? 0
                : Math.max(0, (root.height - intakeCard.implicitHeight) / 2 - 24)

            Behavior on implicitHeight {
                NumberAnimation {
                    duration: 320
                    easing.type: Easing.OutCubic
                }
            }
        }

        // Unified intake card
        Rectangle {
            id: intakeCard
            Layout.fillWidth: true
            radius: Theme.cardRadius + 4
            color: Theme.glassFill
            border.color: Theme.cardBorder
            border.width: 1
            implicitHeight: intakeColumn.implicitHeight + 32

            ColumnLayout {
                id: intakeColumn
                anchors.fill: parent
                anchors.margins: 16
                spacing: 12

                RowLayout {
                    Layout.fillWidth: true
                    spacing: 8

                    Rectangle {
                        Layout.preferredHeight: 38
                        Layout.preferredWidth: modeRow.implicitWidth + 8
                        radius: 8
                        color: Theme.bgTop
                        border.color: Theme.cardBorder
                        border.width: 1

                        Row {
                            id: modeRow
                            anchors.centerIn: parent
                            spacing: 2

                            SegmentedButton {
                                label: "Tìm kiếm"
                                iconName: "search"
                                selected: root.intakeMode === "search"
                                onTapped: {
                                    root.intakeMode = "search"
                                    root.results.clear()
                                    root.searchStatus = "idle"
                                    root.linkFromResolve = false
                                    root.playlistFolder = ""
                                }
                            }

                            SegmentedButton {
                                label: "Dán link"
                                iconName: "link"
                                selected: root.intakeMode === "link"
                                onTapped: {
                                    root.intakeMode = "link"
                                    root.results.clear()
                                    root.searchStatus = "idle"
                                    root.linkFromResolve = false
                                    root.playlistFolder = ""
                                }
                            }
                        }
                    }

                    Item { Layout.fillWidth: true }

                    Rectangle {
                        Layout.preferredHeight: 38
                        Layout.preferredWidth: mediaRow.implicitWidth + 8
                        radius: 8
                        color: Theme.bgTop
                        border.color: Theme.cardBorder
                        border.width: 1

                        Row {
                            id: mediaRow
                            anchors.centerIn: parent
                            spacing: 2

                            SegmentedButton {
                                label: "Nhạc"
                                iconName: "music_note"
                                selected: root.mediaType === "music"
                                onTapped: root.mediaType = "music"
                            }

                            SegmentedButton {
                                label: "Video"
                                iconName: "videocam"
                                selected: root.mediaType === "video"
                                onTapped: root.mediaType = "video"
                            }
                        }
                    }

                }

                RowLayout {
                    Layout.fillWidth: true
                    spacing: 8

                    Rectangle {
                        id: queryFieldBg
                        Layout.fillWidth: true
                        implicitHeight: 42
                        radius: 8
                        color: Theme.bgTop
                        border.color: queryField.activeFocus ? Theme.accentStart : Theme.inputBorder
                        border.width: queryField.activeFocus ? Theme.focusRingWidth : 1

                        Behavior on border.color {
                            ColorAnimation {
                                duration: Theme.colorDuration
                                easing.type: Easing.OutCubic
                            }
                        }

                        Behavior on border.width {
                            NumberAnimation {
                                duration: Theme.colorDuration
                                easing.type: Easing.OutCubic
                            }
                        }

                        KeyboardFocusRing {
                            anchors.fill: parent
                            show: queryField.activeFocus
                            ringRadius: 8
                            ringWidth: Theme.focusRingWidth
                            glowOpacity: 0.22
                        }

                        AppIcon {
                            id: inputIcon
                            anchors.left: parent.left
                            anchors.leftMargin: 12
                            anchors.verticalCenter: parent.verticalCenter
                            name: root.intakeMode === "search" ? "search" : "link"
                            color: Theme.textMuted
                            font.pixelSize: 16
                        }

                        TextField {
                            id: queryField
                            anchors.fill: parent
                            anchors.leftMargin: 36
                            anchors.rightMargin: queryField.text.length > 0 ? 36 : 12
                            placeholderText: root.intakeMode === "search"
                                ? "Tìm tên " + (root.mediaType === "music" ? "bài hát" : "video") + " trên YouTube…"
                                : "Dán link YouTube — có thể thêm nhiều playlist vào hàng đợi…"
                            font.family: Theme.fontFamily
                            color: Theme.textPrimary
                            placeholderTextColor: Theme.textMuted
                            background: Item {}
                            onTextChanged: root.errorStatus = ""
                            Keys.onReturnPressed: {
                                if (root.intakeMode === "search")
                                    root.runSearch(text)
                                else
                                    root.queueLinkInput(text)
                            }
                        }

                        IconButton {
                            anchors.right: parent.right
                            anchors.rightMargin: 6
                            anchors.verticalCenter: parent.verticalCenter
                            visible: queryField.text.length > 0
                            icon: "close"
                            iconSize: 14
                            onClicked: queryField.text = ""
                        }
                    }

                    Rectangle {
                        Layout.preferredWidth: actionLabel.implicitWidth + 40
                        Layout.preferredHeight: 42
                        radius: 8
                        visible: root.intakeMode === "search"
                        gradient: Gradient {
                            orientation: Gradient.Horizontal
                            GradientStop { position: 0; color: Theme.accentStart }
                            GradientStop { position: 1; color: Theme.accentEnd }
                        }

                        Text {
                            id: actionLabel
                            anchors.centerIn: parent
                            text: "Tìm kiếm"
                            font.family: Theme.fontFamily
                            font.pixelSize: Theme.bodySize
                            font.weight: Font.DemiBold
                            color: Theme.textOnAccent
                        }

                        MouseArea {
                            anchors.fill: parent
                            cursorShape: Qt.PointingHandCursor
                            onClicked: root.runSearch(queryField.text)
                        }
                    }

                    Rectangle {
                        Layout.preferredWidth: queueActionLabel.implicitWidth + 28
                        Layout.preferredHeight: 42
                        radius: 8
                        visible: root.intakeMode === "link"
                        color: queueActionHover.containsMouse ? Theme.glassStrong : Theme.bgTop
                        border.color: Theme.cardBorder
                        border.width: 1

                        Text {
                            id: queueActionLabel
                            anchors.centerIn: parent
                            text: "Hàng đợi"
                            font.family: Theme.fontFamily
                            font.pixelSize: Theme.bodySize
                            font.weight: Font.DemiBold
                            color: Theme.textPrimary
                        }

                        MouseArea {
                            id: queueActionHover
                            anchors.fill: parent
                            hoverEnabled: true
                            cursorShape: Qt.PointingHandCursor
                            onClicked: {
                                root.queueLinkInput(queryField.text)
                                queryField.text = ""
                            }
                        }
                    }

                    Rectangle {
                        Layout.preferredWidth: linkActionLabel.implicitWidth + 28
                        Layout.preferredHeight: 42
                        radius: 8
                        visible: root.intakeMode === "link"
                        gradient: Gradient {
                            orientation: Gradient.Horizontal
                            GradientStop { position: 0; color: Theme.accentStart }
                            GradientStop { position: 1; color: Theme.accentEnd }
                        }

                        Text {
                            id: linkActionLabel
                            anchors.centerIn: parent
                            text: "Xem trước"
                            font.family: Theme.fontFamily
                            font.pixelSize: Theme.bodySize
                            font.weight: Font.DemiBold
                            color: Theme.textOnAccent
                        }

                        MouseArea {
                            anchors.fill: parent
                            cursorShape: Qt.PointingHandCursor
                            onClicked: root.submitLink(queryField.text)
                        }
                    }
                }

                WaveformProgress {
                    Layout.fillWidth: true
                    visible: root.intakeMode === "link" && root.directDownloadActive
                    progress: root.directDownloadProgress
                    state: root.directDownloadState

                    MouseArea {
                        id: directHover
                        anchors.fill: parent
                        hoverEnabled: true
                        acceptedButtons: Qt.NoButton
                    }

                    AppToolTip {
                        visible: directHover.containsMouse && root.directDownloadState === "error"
                        text: root.directDownloadError
                    }
                }
            }
        }

        Rectangle {
            Layout.fillWidth: true
            visible: root.errorStatus.length > 0
            implicitHeight: errorRow.implicitHeight + 16
            radius: Theme.cardRadius
            color: "#552b2b"
            border.color: "#e57373"

            RowLayout {
                id: errorRow
                anchors.fill: parent
                anchors.margins: 8
                spacing: 12

                Text {
                    id: errorText
                    Layout.fillWidth: true
                    text: root.errorStatus
                    color: "#ffcdd2"
                    font.family: Theme.fontFamily
                    wrapMode: Text.Wrap
                }

                Button {
                    visible: queryField.text.trim().length > 0
                    text: "Thử lại"
                    onClicked: {
                        if (root.intakeMode === "search")
                            root.runSearch(queryField.text)
                        else
                            root.submitLink(queryField.text)
                    }
                }
            }
        }

        RowLayout {
            Layout.fillWidth: true
            visible: root.searchStatus === "results" && root.intakeMode === "search" && results.count > 0
            spacing: 12

            Text {
                Layout.fillWidth: true
                text: root.selectedCount > 0
                    ? root.selectedCount + " mục đã chọn"
                    : results.count + " kết quả"
                font.family: Theme.fontFamily
                font.pixelSize: Theme.bodySize
                font.weight: Font.DemiBold
                color: Theme.textSecondary
            }

            Rectangle {
                Layout.preferredWidth: selectAllLabel.implicitWidth + 20
                Layout.preferredHeight: 32
                radius: 8
                color: selectAllHover.containsMouse ? Theme.glassStrong : Theme.bgTop
                border.color: Theme.cardBorder
                border.width: 1

                Text {
                    id: selectAllLabel
                    anchors.centerIn: parent
                    text: root.selectedCount > 0 ? "Bỏ chọn" : "Chọn tất cả"
                    font.family: Theme.fontFamily
                    font.pixelSize: Theme.captionSize
                    font.weight: Font.DemiBold
                    color: Theme.textPrimary
                }

                MouseArea {
                    id: selectAllHover
                    anchors.fill: parent
                    hoverEnabled: true
                    cursorShape: Qt.PointingHandCursor
                    onClicked: root.selectAllResults(root.selectedCount === 0)
                }
            }

            Rectangle {
                Layout.preferredWidth: downloadSelectedLabel.implicitWidth + 24
                Layout.preferredHeight: 32
                radius: 8
                visible: root.selectedCount > 0
                opacity: downloadSelectedHover.enabled ? 1 : 0.45
                color: downloadSelectedHover.containsMouse ? Theme.glassStrong : Theme.bgTop
                border.color: Theme.cardBorder
                border.width: 1

                Text {
                    id: downloadSelectedLabel
                    anchors.centerIn: parent
                    text: "Tải đã chọn (" + root.selectedCount + ")"
                    font.family: Theme.fontFamily
                    font.pixelSize: Theme.captionSize
                    font.weight: Font.DemiBold
                    color: Theme.textPrimary
                }

                MouseArea {
                    id: downloadSelectedHover
                    anchors.fill: parent
                    hoverEnabled: true
                    enabled: root.selectedCount > 0
                    cursorShape: enabled ? Qt.PointingHandCursor : Qt.ArrowCursor
                    onClicked: root.downloadSelected()
                }
            }
        }

        RowLayout {
            Layout.fillWidth: true
            visible: root.intakeMode === "link" && root.searchStatus === "results" && results.count > 1
            spacing: 12

            Text {
                Layout.fillWidth: true
                text: {
                    var stats = root.playlistDownloadStats()
                    var base = root.playlistFolder.length > 0
                        ? "Playlist · " + results.count + " mục → " + root.playlistFolder
                        : "Playlist · " + results.count + " mục"
                    if (stats.active > 0) {
                        var mode = (results.count > 30 || stats.total > 30) && backend.downloadConcurrency > 1
                            ? "tải song song x2"
                            : "tải lần lượt"
                        return base + " · " + stats.done + "/" + stats.total + " · " + mode
                    }
                    return base
                }
                font.family: Theme.fontFamily
                font.pixelSize: Theme.bodySize
                font.weight: Font.DemiBold
                color: Theme.textSecondary
            }

            Rectangle {
                Layout.preferredWidth: queueAllLabel.implicitWidth + 24
                Layout.preferredHeight: 32
                radius: 8
                color: queueAllHover.containsMouse ? Theme.glassStrong : Theme.bgTop
                border.color: Theme.cardBorder
                border.width: 1

                Text {
                    id: queueAllLabel
                    anchors.centerIn: parent
                    text: "Hàng đợi"
                    font.family: Theme.fontFamily
                    font.pixelSize: Theme.captionSize
                    font.weight: Font.DemiBold
                    color: Theme.textPrimary
                }

                MouseArea {
                    id: queueAllHover
                    anchors.fill: parent
                    hoverEnabled: true
                    cursorShape: Qt.PointingHandCursor
                    onClicked: root.queueCurrentResults()
                }
            }

            Rectangle {
                Layout.preferredWidth: downloadAllLabel.implicitWidth + 24
                Layout.preferredHeight: 32
                radius: 8
                opacity: downloadAllHover.enabled ? 1 : 0.45
                color: downloadAllHover.containsMouse ? Theme.glassStrong : Theme.bgTop
                border.color: Theme.cardBorder
                border.width: 1

                Text {
                    id: downloadAllLabel
                    anchors.centerIn: parent
                    text: {
                        var stats = root.playlistDownloadStats()
                        return stats.active > 0 ? "Đang tải…" : "Tải tất cả"
                    }
                    font.family: Theme.fontFamily
                    font.pixelSize: Theme.captionSize
                    font.weight: Font.DemiBold
                    color: Theme.textPrimary
                }

                MouseArea {
                    id: downloadAllHover
                    anchors.fill: parent
                    hoverEnabled: true
                    cursorShape: Qt.PointingHandCursor
                    onClicked: root.downloadAllFromList()
                }
            }
        }

        ListView {
            id: resultList
            Layout.fillWidth: true
            Layout.fillHeight: true
            spacing: 8
            clip: true
            visible: root.searchStatus === "results"
            opacity: visible ? 1 : 0
            model: results

            Behavior on opacity {
                NumberAnimation { duration: 220; easing.type: Easing.OutCubic }
            }
            transform: Translate { y: (1 - resultList.opacity) * 12 }

            delegate: Rectangle {
                id: resultRow
                width: resultList.width
                height: resultContent.implicitHeight + 24
                radius: Theme.cardRadius
                color: Theme.cardBg
                border.color: rowHover.containsMouse ? Theme.glassStrongBorder : Theme.cardBorder
                border.width: 1

                required property int index
                required property bool selected
                required property string title
                required property string artist
                required property string duration
                required property string thumbnail
                required property string url
                required property bool inLibrary
                required property string downloadState
                required property real downloadProgress
                required property string downloadError

                onDownloadStateChanged: {
                    if (downloadState !== "downloading")
                        statusIcon.rotation = 0
                }

                RowLayout {
                    id: resultContent
                    anchors.fill: parent
                    anchors.margins: 12
                    spacing: 12

                    Rectangle {
                        Layout.preferredWidth: 28
                        Layout.preferredHeight: 28
                        Layout.alignment: Qt.AlignVCenter
                        visible: root.intakeMode === "search"
                               && downloadState !== "library"
                               && downloadState !== "done"
                        radius: 6
                        color: selected ? Qt.rgba(Theme.accentStart.r, Theme.accentStart.g, Theme.accentStart.b, 0.18)
                                         : Theme.glassStrong
                        border.color: selected ? Theme.accentStart : Theme.cardBorder
                        border.width: 1

                        AppIcon {
                            anchors.centerIn: parent
                            visible: selected
                            name: "check"
                            color: Theme.accentStart
                            font.pixelSize: 14
                        }

                        MouseArea {
                            anchors.fill: parent
                            cursorShape: Qt.PointingHandCursor
                            onClicked: root.toggleSelection(index)
                        }
                    }

                    Rectangle {
                        Layout.preferredWidth: 48
                        Layout.preferredHeight: 48
                        radius: 8
                        color: Theme.glassStrong
                        clip: true

                        Image {
                            anchors.fill: parent
                            source: thumbnail
                            fillMode: Image.PreserveAspectCrop
                            visible: thumbnail !== ""
                        }

                        Text {
                            anchors.centerIn: parent
                            text: title.length > 0 ? title.charAt(0).toUpperCase() : "?"
                            visible: thumbnail === ""
                            font.pixelSize: 20
                            font.weight: Font.Bold
                            color: Theme.textMuted
                        }
                    }

                    ColumnLayout {
                        Layout.fillWidth: true
                        spacing: 4

                        Text {
                            Layout.fillWidth: true
                            text: title
                            font.family: Theme.fontFamily
                            font.pixelSize: Theme.bodySize
                            font.weight: Font.DemiBold
                            color: Theme.textPrimary
                            elide: Text.ElideRight
                        }

                        Text {
                            Layout.fillWidth: true
                            visible: artist.length > 0
                            text: artist
                            font.family: Theme.fontFamily
                            font.pixelSize: Theme.captionSize
                            color: Theme.textMuted
                            elide: Text.ElideRight
                        }

                        Text {
                            Layout.fillWidth: true
                            visible: inLibrary
                            text: "Đã có trong thư viện"
                            font.family: Theme.fontFamily
                            font.pixelSize: Theme.captionSize
                            color: "#34D399"
                            elide: Text.ElideRight
                        }

                        WaveformProgress {
                            Layout.fillWidth: true
                            visible: downloadState !== "idle" && downloadState !== "library"
                            progress: downloadProgress
                            state: downloadState
                        }
                    }

                    Text {
                        text: duration
                        font.family: Theme.fontFamily
                        font.pixelSize: Theme.captionSize
                        color: Theme.textMuted
                        Layout.alignment: Qt.AlignVCenter
                    }

                    Rectangle {
                        Layout.preferredWidth: 36
                        Layout.preferredHeight: 36
                        radius: 18
                        color: downloadState === "done" ? "#34D39926"
                               : downloadState === "library" ? "#34D39926"
                               : downloadState === "downloading" ? Qt.rgba(Theme.accentStart.r, Theme.accentStart.g, Theme.accentStart.b, 0.15)
                               : downloadState === "queued" ? Qt.rgba(Theme.textMuted.r, Theme.textMuted.g, Theme.textMuted.b, 0.12)
                               : downloadState === "error" ? "#F8717126"
                               : Theme.glassStrong

                        AppIcon {
                            id: statusIcon
                            anchors.centerIn: parent
                            name: downloadState === "done" ? "check"
                                 : downloadState === "library" ? (root.mediaType === "video" ? "movie" : "library_music")
                                 : downloadState === "downloading" ? "progress_activity"
                                 : downloadState === "queued" ? "schedule"
                                 : downloadState === "error" ? "error"
                                 : "download"
                            color: downloadState === "done" ? "#34D399"
                                   : downloadState === "library" ? "#34D399"
                                   : downloadState === "downloading" ? Theme.accentStart
                                   : downloadState === "queued" ? Theme.textMuted
                                   : downloadState === "error" ? "#F87171"
                                   : Theme.textPrimary
                            font.pixelSize: 16

                            RotationAnimation on rotation {
                                running: downloadState === "downloading"
                                from: 0
                                to: 360
                                duration: 900
                                loops: Animation.Infinite
                            }
                        }

                        MouseArea {
                            id: downloadBtn
                            anchors.fill: parent
                            enabled: downloadState !== "downloading"
                                   && downloadState !== "queued"
                                   && downloadState !== "done"
                                   && downloadState !== "library"
                                   && url !== ""
                            cursorShape: enabled ? Qt.PointingHandCursor : Qt.ArrowCursor
                            hoverEnabled: true
                            onClicked: root.startDownload(url)

                            AppToolTip {
                                visible: downloadBtn.containsMouse
                                       && (downloadState === "error" || downloadState === "library")
                                text: downloadState === "library"
                                    ? "Bài này đã có trong thư viện"
                                    : downloadError
                            }
                        }
                    }
                }

                MouseArea {
                    id: rowHover
                    anchors.fill: parent
                    hoverEnabled: true
                    acceptedButtons: Qt.NoButton
                    z: -1
                }
            }

            ScrollBar.vertical: ScrollBar { policy: ScrollBar.AsNeeded }
        }

        Item {
            id: searchPlaceholder
            Layout.fillWidth: true
            Layout.fillHeight: true
            visible: root.searchStatus !== "results"
                && (root.intakeMode === "search"
                    || root.searchStatus === "loading"
                    || root.searchStatus === "empty")
            opacity: visible ? 1 : 0

            Behavior on opacity {
                NumberAnimation { duration: 220; easing.type: Easing.OutCubic }
            }
            transform: Translate { y: (1 - searchPlaceholder.opacity) * 12 }

            Column {
                anchors.centerIn: parent
                spacing: 8

                AppIcon {
                    anchors.horizontalCenter: parent.horizontalCenter
                    visible: root.searchStatus === "loading"
                    name: "progress_activity"
                    color: Theme.textMuted
                    font.pixelSize: 20

                    RotationAnimation on rotation {
                        running: root.searchStatus === "loading"
                        from: 0
                        to: 360
                        duration: 900
                        loops: Animation.Infinite
                    }
                }

                Text {
                    anchors.horizontalCenter: parent.horizontalCenter
                    text: {
                        if (root.searchStatus === "loading" && root.intakeMode === "link")
                            return "Đang đọc playlist…"
                        if (root.searchStatus === "loading")
                            return "Đang tìm kiếm…"
                        if (root.searchStatus === "empty" && root.intakeMode === "link")
                            return "Không tìm thấy video trong link."
                        if (root.searchStatus === "empty")
                            return "Không tìm thấy kết quả."
                        return "Nhập từ khóa để tìm media cần tải."
                    }
                    font.family: Theme.fontFamily
                    font.pixelSize: Theme.bodySize
                    color: Theme.textMuted
                }
            }
        }

        // Balances the fixed top offset so the link card remains visually
        // centered regardless of the window height.
        Item {
            Layout.fillWidth: true
            Layout.fillHeight: root.intakeMode === "link" && root.searchStatus !== "results"
            visible: root.intakeMode === "link" && root.searchStatus !== "results"
        }
    }
}
