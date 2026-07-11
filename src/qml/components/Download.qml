import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import Liminal 1.0

Item {
    id: root

    property string downloadName: ""
    property real downloadPercent: 0
    property string downloadStatus: ""
    property string errorStatus: ""

    function formatDuration(value) {
        var seconds = Number(value || 0)
        if (!seconds)
            return "--:--"
        var minutes = Math.floor(seconds / 60)
        var remainder = Math.floor(seconds % 60)
        return minutes + ":" + (remainder < 10 ? "0" : "") + remainder
    }

    function search(text) {
        var query = text.trim()
        if (query.length > 0)
            backend.searchOnline(query)
        else
            results.clear()
    }

    ListModel { id: results }

    Timer {
        id: searchTimer
        interval: 350
        repeat: false
        onTriggered: root.search(searchField.text)
    }

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
            results.clear()
            for (var i = 0; i < items.length; ++i) {
                var item = items[i]
                results.append({
                    title: item.title || "Không có tiêu đề",
                    duration: root.formatDuration(item.duration),
                    thumbnail: item.thumbnail || "",
                    url: item.webpage_url || item.original_url || item.url || ""
                })
            }
        }

        function onSearchError(message) {
            root.errorStatus = message || "Không thể tìm kiếm media."
            errorTimer.restart()
        }

        function onDownloadProgress(title, percent) {
            root.downloadName = title
            root.downloadPercent = Math.max(0, Math.min(100, Number(percent) || 0))
            root.downloadStatus = "Đang tải… " + Math.round(root.downloadPercent) + "%"
        }

        function onDownloadFinished(kind) {
            root.downloadPercent = 100
            root.downloadStatus = "Đã tải " + (kind === "audio" ? "nhạc" : "video")
        }

        function onDownloadError(message) {
            root.errorStatus = message || "Tải xuống thất bại."
            errorTimer.restart()
        }
    }

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: Theme.contentPadding
        spacing: 16

        Text {
            text: "Tải xuống"
            font.family: Theme.fontFamily
            font.pixelSize: Theme.pageTitleSize
            font.weight: Font.Bold
            color: Theme.textPrimary
        }

        RowLayout {
            Layout.fillWidth: true
            spacing: 10

            TextField {
                id: searchField
                Layout.fillWidth: true
                placeholderText: "Tìm tên bài hát hoặc video trên YouTube…"
                font.family: Theme.fontFamily
                color: Theme.textPrimary
                placeholderTextColor: Theme.textMuted
                onTextChanged: {
                    searchTimer.restart()
                }
                Keys.onReturnPressed: {
                    searchTimer.stop()
                    root.search(text)
                }
                background: Rectangle {
                    radius: Theme.cardRadius
                    color: Theme.inputBg
                    border.color: Theme.inputBorder
                    border.width: 1
                }
            }

            Button {
                text: "Tìm kiếm"
                onClicked: root.search(searchField.text)
            }
        }

        RowLayout {
            Layout.fillWidth: true
            spacing: 10

            TextField {
                id: directUrlField
                Layout.fillWidth: true
                placeholderText: "Hoặc dán link trực tiếp cần tải…"
                font.family: Theme.fontFamily
                color: Theme.textPrimary
                placeholderTextColor: Theme.textMuted
                onTextChanged: root.errorStatus = ""
                background: Rectangle {
                    radius: Theme.cardRadius
                    color: Theme.inputBg
                    border.color: Theme.inputBorder
                    border.width: 1
                }
            }

            Button {
                text: "🎵 Tải nhạc"
                enabled: directUrlField.text.trim().match(/^https?:\/\/.+/) !== null
                onClicked: backend.downloadMedia(directUrlField.text.trim(), "audio")
            }

            Button {
                text: "🎬 Tải video"
                enabled: directUrlField.text.trim().match(/^https?:\/\/.+/) !== null
                onClicked: backend.downloadMedia(directUrlField.text.trim(), "video")
            }
        }

        Rectangle {
            Layout.fillWidth: true
            visible: root.errorStatus.length > 0
            implicitHeight: errorText.implicitHeight + 16
            radius: Theme.cardRadius
            color: "#552b2b"
            border.color: "#e57373"

            Text {
                id: errorText
                anchors.fill: parent
                anchors.margins: 8
                text: root.errorStatus
                color: "#ffcdd2"
                font.family: Theme.fontFamily
                wrapMode: Text.Wrap
            }
        }

        ColumnLayout {
            Layout.fillWidth: true
            spacing: 5
            visible: root.downloadStatus.length > 0

            Text {
                Layout.fillWidth: true
                text: (root.downloadName.length > 0 ? root.downloadName + " — " : "")
                      + root.downloadStatus
                font.family: Theme.fontFamily
                font.pixelSize: Theme.captionSize
                color: Theme.textSecondary
                elide: Text.ElideRight
            }

            ProgressBar {
                Layout.fillWidth: true
                from: 0
                to: 100
                value: root.downloadPercent
            }
        }

        ListView {
            id: resultList
            Layout.fillWidth: true
            Layout.fillHeight: true
            spacing: 10
            clip: true
            model: results

            delegate: Rectangle {
                width: resultList.width
                height: 84
                radius: Theme.cardRadius
                color: Theme.cardBg
                border.color: Theme.cardBorder
                border.width: 1

                RowLayout {
                    anchors.fill: parent
                    anchors.margins: 10
                    spacing: 12

                    Rectangle {
                        Layout.preferredWidth: 108
                        Layout.fillHeight: true
                        radius: 7
                        color: Theme.glassStrong
                        clip: true

                        Image {
                            anchors.fill: parent
                            source: model.thumbnail
                            fillMode: Image.PreserveAspectCrop
                            visible: source !== ""
                        }

                        Text {
                            anchors.centerIn: parent
                            text: model.title.length > 0 ? model.title.charAt(0).toUpperCase() : "?"
                            visible: model.thumbnail === ""
                            font.pixelSize: 28
                            font.weight: Font.Bold
                            color: Theme.textMuted
                        }
                    }

                    ColumnLayout {
                        Layout.fillWidth: true
                        spacing: 4

                        Text {
                            Layout.fillWidth: true
                            text: model.title
                            font.family: Theme.fontFamily
                            font.pixelSize: Theme.bodySize
                            font.weight: Font.Bold
                            color: Theme.textPrimary
                            elide: Text.ElideRight
                        }

                        Text {
                            text: model.duration
                            font.family: Theme.fontFamily
                            font.pixelSize: Theme.captionSize
                            color: Theme.textMuted
                        }
                    }

                    Button {
                        text: "🎵 Nhạc"
                        enabled: model.url !== ""
                        onClicked: backend.downloadMedia(model.url, "audio")
                    }

                    Button {
                        text: "🎬 Video"
                        enabled: model.url !== ""
                        onClicked: backend.downloadMedia(model.url, "video")
                    }
                }
            }

            ScrollBar.vertical: ScrollBar { policy: ScrollBar.AsNeeded }
        }

        Text {
            Layout.fillWidth: true
            visible: results.count === 0
            text: "Nhập từ khóa để tìm media cần tải."
            horizontalAlignment: Text.AlignHCenter
            font.family: Theme.fontFamily
            font.pixelSize: Theme.bodySize
            color: Theme.textMuted
        }
    }
}
