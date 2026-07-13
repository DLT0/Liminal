import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import Liminal 1.0

Dialog {
    id: root

    title: "Sắp xếp bằng cách chạm"
    modal: true
    anchors.centerIn: parent
    padding: 20
    width: Math.min(780, Overlay.overlay ? Overlay.overlay.width - 64 : 780)
    height: Math.min(680, Overlay.overlay ? Overlay.overlay.height - 64 : 680)

    property string seriesTitle: ""
    property int currentSeason: 1
    property var seasonCounters: ({})
    property int totalCount: 0
    property var undoStack: []

    readonly property int assignedCount: orderModel.count
    readonly property int pendingCount: pendingModel.count
    readonly property int nextEpisodeNumber: root.seasonNextEpisode(root.currentSeason, true)

    background: Rectangle {
        radius: 14
        color: Theme.glassStrong
        border.color: Theme.glassStrongBorder
        border.width: 1
    }

    function seasonNextEpisode(season, peek) {
        var key = String(season)
        if (!root.seasonCounters[key])
            root.seasonCounters[key] = 1
        return root.seasonCounters[key]
    }

    function bumpSeasonEpisode(season) {
        var key = String(season)
        if (!root.seasonCounters[key])
            root.seasonCounters[key] = 1
        else
            root.seasonCounters[key] = root.seasonCounters[key] + 1
    }

    function resetSession() {
        seasonCounters = {}
        undoStack = []
        orderModel.clear()
        pendingModel.clear()
    }

    function reloadRows() {
        resetSession()
        var rows = backend.currentSeriesSetupRows()
        root.totalCount = rows.length
        for (var i = 0; i < rows.length; i++) {
            pendingModel.append({
                path: rows[i].path || "",
                fileName: rows[i].file_name || "",
                title: rows[i].title || ""
            })
        }
    }

    function episodeLabel(season, episode) {
        return season > 1 ? ("M" + season + " · T" + episode) : ("Tập " + episode)
    }

    function assignPending(pendingIndex) {
        if (pendingIndex < 0 || pendingIndex >= pendingModel.count)
            return
        var row = pendingModel.get(pendingIndex)
        var season = Math.max(1, currentSeason)
        var episode = seasonNextEpisode(season, false)
        bumpSeasonEpisode(season)

        orderModel.append({
            path: row.path,
            fileName: row.fileName,
            title: row.title,
            season: season,
            episode: episode,
            label: episodeLabel(season, episode)
        })
        undoStack.push({
            path: row.path,
            fileName: row.fileName,
            title: row.title,
            season: season,
            episode: episode
        })
        pendingModel.remove(pendingIndex)
    }

    function undoLast() {
        if (undoStack.length === 0 || orderModel.count === 0)
            return
        var last = undoStack.pop()
        orderModel.remove(orderModel.count - 1)
        pendingModel.append({
            path: last.path,
            fileName: last.fileName,
            title: last.title
        })
        var key = String(last.season)
        if (root.seasonCounters[key] && root.seasonCounters[key] > 1)
            root.seasonCounters[key] = root.seasonCounters[key] - 1
    }

    function finishSeason() {
        currentSeason = Math.min(99, currentSeason + 1)
        seasonField.value = currentSeason
    }

    function collectAssignments() {
        var items = []
        for (var i = 0; i < orderModel.count; i++) {
            var row = orderModel.get(i)
            items.push({
                path: row.path,
                season: row.season,
                episode: row.episode
            })
        }
        return items
    }

    function openDialog(title) {
        seriesTitle = title || ""
        currentSeason = 1
        reloadRows()
        open()
    }

    ListModel { id: pendingModel }
    ListModel { id: orderModel }

    header: ColumnLayout {
        width: parent.width
        spacing: 12

        Text {
            Layout.fillWidth: true
            text: "Chạm từng tập theo thứ tự xem. Tập đã chọn sẽ chuyển lên dãy phía trên."
            wrapMode: Text.Wrap
            font.family: Theme.fontFamily
            font.pixelSize: Theme.bodySize
            color: Theme.textSecondary
        }

        RowLayout {
            Layout.fillWidth: true
            spacing: 8

            ColumnLayout {
                Layout.fillWidth: true
                spacing: 4

                Text {
                    text: "Tiến độ"
                    font.family: Theme.fontFamily
                    font.pixelSize: Theme.captionSize
                    color: Theme.textMuted
                }

                ProgressBar {
                    Layout.fillWidth: true
                    from: 0
                    to: Math.max(1, root.totalCount)
                    value: root.assignedCount
                }

                Text {
                    Layout.fillWidth: true
                    text: root.assignedCount + " / " + root.totalCount + " tập đã xếp"
                    font.family: Theme.fontFamily
                    font.pixelSize: Theme.captionSize
                    font.weight: Font.DemiBold
                    color: Theme.accentStart
                }
            }

            Rectangle {
                Layout.preferredWidth: 88
                Layout.preferredHeight: 64
                radius: 10
                color: Theme.bgElevated
                border.color: Theme.accentStart

                Column {
                    anchors.centerIn: parent
                    spacing: 0

                    Text {
                        anchors.horizontalCenter: parent.horizontalCenter
                        text: "Tiếp theo"
                        font.family: Theme.fontFamily
                        font.pixelSize: Theme.captionSize
                        color: Theme.textMuted
                    }

                    Text {
                        anchors.horizontalCenter: parent.horizontalCenter
                        text: root.pendingCount > 0
                            ? root.episodeLabel(root.currentSeason, root.nextEpisodeNumber)
                            : "Xong"
                        font.family: Theme.fontFamily
                        font.pixelSize: 18
                        font.weight: Font.Bold
                        color: Theme.accentStart
                    }
                }
            }
        }

        RowLayout {
            Layout.fillWidth: true
            spacing: 8

            Text {
                text: "Mùa"
                font.family: Theme.fontFamily
                font.pixelSize: Theme.captionSize
                color: Theme.textMuted
            }

            SpinBox {
                id: seasonField
                from: 1
                to: 99
                value: root.currentSeason
                onValueModified: root.currentSeason = value
            }

            ToolButton {
                text: "Mùa tiếp"
                onClicked: root.finishSeason()
            }

            ToolButton {
                text: "Hoàn tác"
                enabled: root.undoStack.length > 0
                onClicked: root.undoLast()
            }

            Item { Layout.fillWidth: true }

            ToolButton {
                text: "Đặt lại"
                onClicked: root.reloadRows()
            }
        }

        Text {
            Layout.fillWidth: true
            visible: orderModel.count > 0
            text: "Thứ tự đã chọn"
            font.family: Theme.fontFamily
            font.pixelSize: Theme.captionSize
            font.weight: Font.DemiBold
            color: Theme.textSecondary
        }

        ListView {
            Layout.fillWidth: true
            Layout.preferredHeight: Math.min(72, orderModel.count > 0 ? 72 : 0)
            visible: orderModel.count > 0
            orientation: ListView.Horizontal
            spacing: 8
            clip: true
            model: orderModel

            delegate: Rectangle {
                width: chipText.implicitWidth + 20
                height: 34
                radius: 17
                color: Theme.bgElevated
                border.color: Theme.accentStart

                Text {
                    id: chipText
                    anchors.centerIn: parent
                    text: model.label
                    font.family: Theme.fontFamily
                    font.pixelSize: Theme.captionSize
                    font.weight: Font.DemiBold
                    color: Theme.accentStart
                }
            }
        }
    }

    contentItem: ColumnLayout {
        spacing: 10

        Text {
            Layout.fillWidth: true
            visible: pendingModel.count > 0
            text: "Chạm tập tiếp theo (" + pendingModel.count + " tập còn lại)"
            font.family: Theme.fontFamily
            font.pixelSize: Theme.captionSize
            font.weight: Font.DemiBold
            color: Theme.textPrimary
        }

        Text {
            Layout.fillWidth: true
            visible: pendingModel.count === 0 && orderModel.count > 0
            text: "Đã xếp xong tất cả tập. Nhấn Lưu để áp dụng."
            font.family: Theme.fontFamily
            font.pixelSize: Theme.bodySize
            color: Theme.accentStart
        }

        ListView {
            id: pendingList
            Layout.fillWidth: true
            Layout.fillHeight: true
            clip: true
            spacing: 8
            model: pendingModel
            boundsBehavior: Flickable.StopAtBounds

            ScrollBar.vertical: ScrollBar { policy: ScrollBar.AsNeeded }

            delegate: Rectangle {
                id: pendingCard
                width: pendingList.width
                height: 64
                radius: 12
                color: tapMouse.pressed ? Theme.bgCardHover : (tapMouse.containsMouse ? Theme.bgCard : Theme.bgCard)
                border.color: tapMouse.containsMouse ? Theme.accentStart : Theme.cardBorder
                border.width: tapMouse.containsMouse ? 2 : 1
                scale: tapMouse.pressed ? 0.985 : 1

                Behavior on scale {
                    NumberAnimation { duration: 90; easing.type: Easing.OutCubic }
                }
                Behavior on border.color {
                    ColorAnimation { duration: Theme.colorDuration }
                }

                RowLayout {
                    anchors.fill: parent
                    anchors.leftMargin: 14
                    anchors.rightMargin: 14
                    spacing: 12

                    Rectangle {
                        Layout.preferredWidth: 34
                        Layout.preferredHeight: 34
                        radius: 17
                        color: Theme.bgElevated
                        border.color: Theme.cardBorder

                        AppIcon {
                            anchors.centerIn: parent
                            name: "play_arrow"
                            font.pixelSize: 18
                            color: Theme.textMuted
                        }
                    }

                    ColumnLayout {
                        Layout.fillWidth: true
                        spacing: 2

                        Text {
                            Layout.fillWidth: true
                            text: model.title || model.fileName
                            elide: Text.ElideRight
                            font.family: Theme.fontFamily
                            font.pixelSize: Theme.bodySize
                            font.weight: Font.Medium
                            color: Theme.textPrimary
                        }

                        Text {
                            Layout.fillWidth: true
                            text: model.fileName
                            elide: Text.ElideMiddle
                            font.family: Theme.fontFamily
                            font.pixelSize: Theme.captionSize
                            color: Theme.textMuted
                        }
                    }

                    Text {
                        text: "Chạm"
                        font.family: Theme.fontFamily
                        font.pixelSize: Theme.captionSize
                        font.weight: Font.DemiBold
                        color: Theme.accentStart
                        opacity: tapMouse.containsMouse ? 1 : 0.55
                    }
                }

                MouseArea {
                    id: tapMouse
                    anchors.fill: parent
                    hoverEnabled: true
                    cursorShape: Qt.PointingHandCursor
                    onClicked: root.assignPending(index)
                }
            }
        }
    }

    footer: DialogButtonBox {
        standardButtons: DialogButtonBox.Save | DialogButtonBox.Cancel
        onAccepted: {
            if (root.assignedCount === 0) {
                root.close()
                return
            }
            backend.saveTapOrderAssignments(root.collectAssignments())
            root.close()
        }
        onRejected: root.close()
    }
}
