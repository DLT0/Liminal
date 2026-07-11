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

    Popup {
        id: videoQualityPopup
        parent: Overlay.overlay
        x: Math.round((parent.width - width) / 2)
        y: Math.round((parent.height - height) / 2)
        width: 320
        modal: true
        focus: true
        closePolicy: Popup.CloseOnEscape | Popup.CloseOnPressOutside

        property string targetUrl: ""

        background: Rectangle {
            color: Theme.cardBg
            border.color: Theme.cardBorder
            border.width: 1
            radius: Theme.cardRadius
        }

        ColumnLayout {
            anchors.fill: parent
            anchors.margins: 20
            spacing: 16

            Text {
                text: "Chọn chất lượng Video"
                font.family: Theme.fontFamily
                font.pixelSize: 18
                font.weight: Font.Bold
                color: Theme.textPrimary
                Layout.alignment: Qt.AlignHCenter
            }

            Flow {
                Layout.fillWidth: true
                spacing: 10

                Repeater {
                    model: ["480", "720", "1080", "1440", "2160", "best"]
                    delegate: Rectangle {
                        width: 130
                        height: 40
                        radius: 8
                        color: backend.downloadQuality === modelData ? Theme.accentStart : Theme.glassFill
                        border.color: backend.downloadQuality === modelData ? Theme.accentEnd : Theme.glassBorder
                        border.width: backend.downloadQuality === modelData ? 2 : 1

                        Text {
                            anchors.centerIn: parent
                            text: {
                                if (modelData === "1080") return "FHD";
                                if (modelData === "1440") return "2K";
                                if (modelData === "2160") return "4K";
                                if (modelData === "best") return "Max";
                                return modelData + "p";
                            }
                            font.family: Theme.fontFamily
                            font.pixelSize: Theme.bodySize
                            font.weight: backend.downloadQuality === modelData ? Font.Bold : Font.Normal
                            color: backend.downloadQuality === modelData ? Theme.textOnAccent : Theme.textSecondary
                        }

                        MouseArea {
                            anchors.fill: parent
                            cursorShape: Qt.PointingHandCursor
                            onClicked: {
                                backend.setDownloadQuality(modelData)
                            }
                        }
                    }
                }
            }

            RowLayout {
                Layout.fillWidth: true
                Layout.topMargin: 10
                spacing: 10

                Button {
                    Layout.fillWidth: true
                    text: "Huỷ"
                    onClicked: videoQualityPopup.close()
                }

                Button {
                    Layout.fillWidth: true
                    text: "Tải ngay"
                    onClicked: {
                        backend.downloadMedia(videoQualityPopup.targetUrl, "video")
                        videoQualityPopup.close()
                    }
                    background: Rectangle {
                        color: Theme.accentEnd
                        radius: 6
                    }
                    contentItem: Text {
                        text: parent.text
                        font.family: Theme.fontFamily
                        color: Theme.textOnAccent
                        horizontalAlignment: Text.AlignHCenter
                        verticalAlignment: Text.AlignVCenter
                        font.weight: Font.Bold
                    }
                }
            }
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
                onClicked: {
                    videoQualityPopup.targetUrl = directUrlField.text.trim()
                    videoQualityPopup.open()
                }
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
                        text: "🎬 Tải video"
                        enabled: model.url !== ""
                        onClicked: {
                            videoQualityPopup.targetUrl = model.url
                            videoQualityPopup.open()
                        }
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
