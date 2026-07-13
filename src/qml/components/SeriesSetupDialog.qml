import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import Liminal 1.0

Dialog {
    id: root

    title: "Sắp xếp mùa & tập"
    modal: true
    anchors.centerIn: parent
    padding: 20
    width: Math.min(760, Overlay.overlay ? Overlay.overlay.width - 80 : 760)
    height: Math.min(560, Overlay.overlay ? Overlay.overlay.height - 80 : 560)

    property string seriesTitle: ""

    background: Rectangle {
        radius: 14
        color: Theme.glassStrong
        border.color: Theme.glassStrongBorder
        border.width: 1
    }

    onAboutToShow: reloadRows()

    function reloadRows() {
        rowsModel.clear()
        var rows = backend.currentSeriesSetupRows()
        for (var i = 0; i < rows.length; i++) {
            rowsModel.append({
                path: rows[i].path || "",
                fileName: rows[i].file_name || "",
                title: rows[i].title || "",
                season: rows[i].season || 1,
                episode: rows[i].episode || (i + 1)
            })
        }
    }

    function collectRows() {
        var rows = []
        for (var i = 0; i < rowsModel.count; i++) {
            rows.push({
                path: rowsModel.get(i).path,
                title: rowsModel.get(i).title,
                season: rowsModel.get(i).season,
                episode: rowsModel.get(i).episode
            })
        }
        return rows
    }

    function openDialog(title) {
        seriesTitle = title || ""
        reloadRows()
        open()
    }

    ListModel {
        id: rowsModel
    }

    header: ColumnLayout {
        width: parent.width
        spacing: 8

        Text {
            Layout.fillWidth: true
            text: root.seriesTitle.length > 0
                ? ("Chỉnh mùa và số tập cho: " + root.seriesTitle)
                : "Chỉnh mùa và số tập cho từng video trong phim bộ."
            wrapMode: Text.Wrap
            font.family: Theme.fontFamily
            font.pixelSize: Theme.bodySize
            color: Theme.textSecondary
        }

        RowLayout {
            Layout.fillWidth: true
            spacing: 8

            Rectangle {
                Layout.fillWidth: true
                Layout.preferredHeight: 34
                radius: 8
                color: aiMouse.containsMouse ? Theme.hoverOverlay : Theme.cardBg
                border.color: Theme.inputBorder
                opacity: backend.seriesAiSortLoading ? 0.6 : 1

                Row {
                    anchors.centerIn: parent
                    spacing: 8

                    BusyIndicator {
                        anchors.verticalCenter: parent.verticalCenter
                        visible: backend.seriesAiSortLoading
                        width: 18
                        height: 18
                    }

                    Text {
                        anchors.verticalCenter: parent.verticalCenter
                        text: backend.seriesAiSortLoading ? "AI đang sắp xếp…" : "AI sắp xếp tập"
                        font.family: Theme.fontFamily
                        font.pixelSize: Theme.captionSize
                        font.weight: Font.DemiBold
                        color: Theme.textPrimary
                    }
                }

                MouseArea {
                    id: aiMouse
                    anchors.fill: parent
                    hoverEnabled: true
                    cursorShape: Qt.PointingHandCursor
                    enabled: !backend.seriesAiSortLoading
                    onClicked: backend.requestAiSeriesSort()
                }
            }

            Rectangle {
                Layout.fillWidth: true
                Layout.preferredHeight: 34
                radius: 8
                color: autoDetectMouse.containsMouse ? Theme.hoverOverlay : Theme.cardBg
                border.color: Theme.inputBorder

                Text {
                    anchors.centerIn: parent
                    text: "Tự động nhận diện từ tên file / thư mục"
                    font.family: Theme.fontFamily
                    font.pixelSize: Theme.captionSize
                    font.weight: Font.DemiBold
                    color: Theme.textPrimary
                }

                MouseArea {
                    id: autoDetectMouse
                    anchors.fill: parent
                    hoverEnabled: true
                    cursorShape: Qt.PointingHandCursor
                    onClicked: {
                        rowsModel.clear()
                        var rows = backend.autoDetectSeriesSetupRows()
                        for (var i = 0; i < rows.length; i++) {
                            rowsModel.append({
                                path: rows[i].path || "",
                                fileName: rows[i].file_name || "",
                                title: rows[i].title || "",
                                season: rows[i].season || 1,
                                episode: rows[i].episode || (i + 1)
                            })
                        }
                    }
                }
            }
        }
    }

    contentItem: ColumnLayout {
        spacing: 10

        RowLayout {
            Layout.fillWidth: true
            spacing: 10

            Text {
                Layout.preferredWidth: 28
                text: "#"
                font.family: Theme.fontFamily
                font.pixelSize: Theme.captionSize
                font.weight: Font.DemiBold
                color: Theme.textMuted
            }
            Text {
                Layout.fillWidth: true
                text: "Tên tập"
                font.family: Theme.fontFamily
                font.pixelSize: Theme.captionSize
                font.weight: Font.DemiBold
                color: Theme.textMuted
            }
            Text {
                Layout.preferredWidth: 72
                horizontalAlignment: Text.AlignHCenter
                text: "Mùa"
                font.family: Theme.fontFamily
                font.pixelSize: Theme.captionSize
                font.weight: Font.DemiBold
                color: Theme.textMuted
            }
            Text {
                Layout.preferredWidth: 72
                horizontalAlignment: Text.AlignHCenter
                text: "Tập"
                font.family: Theme.fontFamily
                font.pixelSize: Theme.captionSize
                font.weight: Font.DemiBold
                color: Theme.textMuted
            }
        }

        ListView {
            id: rowsView
            Layout.fillWidth: true
            Layout.fillHeight: true
            clip: true
            spacing: 6
            model: rowsModel

            ScrollBar.vertical: ScrollBar { policy: ScrollBar.AsNeeded }

            delegate: Rectangle {
                width: rowsView.width
                height: 44
                radius: 8
                color: Theme.bgCard
                border.color: Theme.cardBorder

                RowLayout {
                    anchors.fill: parent
                    anchors.leftMargin: 10
                    anchors.rightMargin: 10
                    spacing: 10

                    Text {
                        Layout.preferredWidth: 28
                        text: (index + 1).toString()
                        font.family: Theme.fontFamily
                        font.pixelSize: Theme.captionSize
                        color: Theme.textMuted
                    }

                    ColumnLayout {
                        Layout.fillWidth: true
                        spacing: 0

                        TextField {
                            Layout.fillWidth: true
                            text: model.title
                            placeholderText: "Tên hiển thị"
                            font.family: Theme.fontFamily
                            font.pixelSize: Theme.bodySize
                            color: Theme.textPrimary
                            placeholderTextColor: Theme.textMuted
                            background: Item {}
                            onTextChanged: rowsModel.setProperty(index, "title", text)
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

                    SpinBox {
                        Layout.preferredWidth: 72
                        from: 1
                        to: 99
                        value: model.season
                        onValueModified: rowsModel.setProperty(index, "season", value)
                    }

                    SpinBox {
                        Layout.preferredWidth: 72
                        from: 1
                        to: 999
                        value: model.episode
                        onValueModified: rowsModel.setProperty(index, "episode", value)
                    }
                }
            }
        }
    }

    footer: DialogButtonBox {
        standardButtons: DialogButtonBox.Save | DialogButtonBox.Cancel
        onAccepted: {
            backend.saveSeriesSetupRows(root.collectRows())
            root.close()
        }
        onRejected: root.close()
    }

    Connections {
        target: backend
        function onSeriesAiSortFinished(rows) {
            rowsModel.clear()
            for (var i = 0; i < rows.length; i++) {
                rowsModel.append({
                    path: rows[i].path || "",
                    fileName: rows[i].file_name || "",
                    title: rows[i].title || "",
                    season: rows[i].season || 1,
                    episode: rows[i].episode || (i + 1)
                })
            }
        }
    }
}
