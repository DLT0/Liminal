import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import QtQuick.Window
import Liminal 1.0

Item {
    id: root

    property string bookPath: ""
    property string bookTitle: "Sách"
    property string bookAuthor: ""
    property var chapters: []
    property bool isPdf: false
    property int totalPdfPages: 0

    property int currentChapter: 0
    property real zoomLevel: 1.0
    property bool showSidebar: false
    property string searchQuery: ""
    property var searchResults: []

    signal closeRequested()

    function readingPercent() {
        var total = 0, read = 0
        for (var i = 0; i < chapters.length; i++) {
            var len = (chapters[i].content || "").length
            total += len
            if (i < currentChapter) read += len
        }
        var cur = chapters[currentChapter]
        if (cur) {
            var curLen = (cur.content || "").length
            var maxScroll = Math.max(1, readerFlickable.contentHeight - readerFlickable.height)
            read += curLen * Math.min(1, readerFlickable.contentY / maxScroll)
        }
        return total > 0 ? read / total : 0
    }

    Timer {
        interval: 3000; repeat: true; running: root.visible
        onTriggered: {
            if (root.isPdf) {
                var page = pdfView.currentIndex || 0
                backend.saveBookPosition(bookPath, page, 0, root.totalPdfPages > 0 ? page / root.totalPdfPages : 0, 0)
            } else {
                backend.saveBookPosition(bookPath, currentChapter, 0, readingPercent(), readerFlickable.contentY)
            }
        }
    }

    Component.onCompleted: {
        var pos = backend.getBookPosition(root.bookPath)
        if (pos) {
            if (root.isPdf) {
                pdfView.currentIndex = pos.chapter_index || 0
            } else {
                currentChapter = pos.chapter_index || 0
                readerFlickable.contentY = pos.scroll_y || 0
            }
        }
    }

    RowLayout {
        anchors.fill: parent; spacing: 0

        // ── Sidebar ──
        Rectangle {
            Layout.preferredWidth: 240; Layout.fillHeight: true
            visible: root.showSidebar
            color: Theme.bgElevated; border.color: Theme.cardBorder
            ColumnLayout {
                anchors.fill: parent; anchors.margins: 8; spacing: 6
                Rectangle {
                    Layout.fillWidth: true; Layout.preferredHeight: 32; radius: 6
                    color: Theme.inputBg; border.color: Theme.inputBorder
                    TextInput {
                        id: searchInput
                        anchors.fill: parent; anchors.margins: 8
                        font.family: Theme.fontFamily; font.pixelSize: 12; color: Theme.textPrimary
                        onTextChanged: {
                            root.searchQuery = text.toLowerCase()
                            var r = []
                            for (var i = 0; i < root.chapters.length; i++) {
                                if (root.searchQuery.length > 0 &&
                                    ((root.chapters[i].title || "").toLowerCase().indexOf(root.searchQuery) >= 0 ||
                                     (root.chapters[i].content || "").toLowerCase().indexOf(root.searchQuery) >= 0))
                                    r.push({ chapter: i, title: root.chapters[i].title || ("Chương " + (i+1)) })
                            }
                            root.searchResults = r
                        }
                    }
                }
                Text { text: "Nội dung"; font.family: Theme.fontFamily; font.pixelSize: 11; font.weight: Font.Bold; color: Theme.textSecondary; visible: searchInput.text.length === 0 }
                ListView {
                    Layout.fillWidth: true; Layout.fillHeight: true; clip: true; spacing: 2
                    visible: searchInput.text.length === 0
                    model: root.chapters
                    delegate: Rectangle {
                        width: parent.width; height: 28; radius: 4
                        color: model.index === currentChapter ? Theme.accentStart + "33" : "transparent"
                        Text {
                            anchors.fill: parent; anchors.margins: 8; verticalAlignment: Text.AlignVCenter
                            text: modelData.title || ("Chương " + (model.index + 1))
                            font.family: Theme.fontFamily; font.pixelSize: 11; color: model.index === currentChapter ? Theme.accentStart : Theme.textSecondary; elide: Text.ElideRight
                        }
                        MouseArea { anchors.fill: parent; cursorShape: Qt.PointingHandCursor
                            onClicked: { currentChapter = model.index; readerFlickable.contentY = 0 } }
                    }
                    ScrollBar.vertical: ScrollBar { policy: ScrollBar.AsNeeded }
                }
                ListView {
                    Layout.fillWidth: true; Layout.fillHeight: true; clip: true; spacing: 2
                    visible: searchInput.text.length > 0
                    model: root.searchResults
                    delegate: Rectangle {
                        width: parent.width; height: 28; radius: 4
                        Text {
                            anchors.fill: parent; anchors.margins: 8; verticalAlignment: Text.AlignVCenter
                            text: modelData.title; font.family: Theme.fontFamily; font.pixelSize: 11; color: Theme.textSecondary; elide: Text.ElideRight
                        }
                        MouseArea { anchors.fill: parent; cursorShape: Qt.PointingHandCursor
                            onClicked: { currentChapter = modelData.chapter; readerFlickable.contentY = 0; searchInput.text = "" } }
                    }
                    ScrollBar.vertical: ScrollBar { policy: ScrollBar.AsNeeded }
                }
            }
        }

        // ── Main ──
        ColumnLayout {
            Layout.fillWidth: true; Layout.fillHeight: true; spacing: 0

            // Toolbar
            Rectangle {
                Layout.fillWidth: true; Layout.preferredHeight: 48
                color: Theme.bgElevated; border.color: Theme.cardBorder
                RowLayout {
                    anchors.fill: parent; anchors.leftMargin: 8; anchors.rightMargin: 8; spacing: 6
                    IconButton { icon: "arrow_back"; iconSize: 20; onClicked: root.closeRequested() }
                    ColumnLayout { Layout.fillWidth: true; spacing: 1
                        Text { text: root.bookTitle; font.family: Theme.fontFamily; font.pixelSize: 13; font.weight: Font.Bold; color: Theme.textPrimary; elide: Text.ElideRight; Layout.fillWidth: true }
                        Text { text: root.bookAuthor + " · " + Math.round(root.readingPercent() * 100) + "%"; font.pixelSize: 10; color: Theme.textMuted; Layout.fillWidth: true }
                    }
                    IconButton { icon: root.showSidebar ? "chevron_right" : "menu"; iconSize: 18; width: 32; height: 32; onClicked: root.showSidebar = !root.showSidebar }
                    IconButton { icon: "zoom_out"; iconSize: 16; width: 28; height: 28; onClicked: root.zoomLevel = Math.max(0.5, root.zoomLevel - 0.25) }
                    Text { text: Math.round(root.zoomLevel * 100) + "%"; font.pixelSize: 10; color: Theme.textMuted }
                    IconButton { icon: "zoom_in"; iconSize: 16; width: 28; height: 28; onClicked: root.zoomLevel = Math.min(3.0, root.zoomLevel + 0.25) }
                }
            }

            // Progress bar
            Rectangle {
                Layout.fillWidth: true; Layout.preferredHeight: 3; color: Theme.sliderTrack
                Rectangle { height: parent.height; width: root.readingPercent() * parent.width; color: Theme.accentStart }
            }

            // ── Content ──
            Rectangle {
                Layout.fillWidth: true; Layout.fillHeight: true; color: Theme.bgTop

                // PDF: virtualized ListView (smooth, lazy, scrollable)
                ListView {
                    id: pdfView
                    anchors.fill: parent; anchors.margins: 8
                    visible: root.isPdf && root.totalPdfPages > 0
                    model: root.totalPdfPages
                    spacing: 4
                    cacheBuffer: 5
                    boundsBehavior: Flickable.StopAtBounds

                    delegate: Item {
                        width: pdfView.width
                        height: pdfImg.implicitHeight > 0 ? pdfImg.implicitHeight : pdfView.width * 1.4

                        Image {
                            id: pdfImg
                            width: parent.width
                            fillMode: Image.PreserveAspectFit
                            smooth: true; asynchronous: true
                            source: "image://bookpage/" + root.bookPath + "/" + model.index + "/" + root.zoomLevel
                        }

                        Text {
                            anchors.horizontalCenter: parent.horizontalCenter; anchors.bottom: parent.bottom; anchors.bottomMargin: -14
                            text: (model.index + 1); font.pixelSize: 9; color: Theme.textMuted
                        }
                    }

                    ScrollBar.vertical: ScrollBar { policy: ScrollBar.AsNeeded }
                }

                // Text: continuous scroll in Flickable
                Flickable {
                    id: readerFlickable
                    anchors.fill: parent; anchors.margins: 24
                    clip: true; contentWidth: width; contentHeight: textColumn.height + 40
                    visible: !root.isPdf

                    Column {
                        id: textColumn
                        width: parent.width; spacing: 12

                        Repeater {
                            model: root.chapters
                            delegate: Column {
                                width: parent.width; spacing: 8
                                Rectangle {
                                    width: parent.width; height: 32; color: "transparent"; visible: modelData.title !== ""
                                    Text {
                                        anchors.verticalCenter: parent.verticalCenter
                                        text: modelData.title
                                        font.family: Theme.fontFamily; font.pixelSize: 18 * root.zoomLevel; font.weight: Font.Bold
                                        color: Theme.accentStart
                                    }
                                }
                                Text {
                                    width: parent.width
                                    text: modelData.content || ""
                                    font.family: "Georgia, Noto Serif, serif"
                                    font.pixelSize: 16 * root.zoomLevel
                                    lineHeight: 1.6; lineHeightMode: Text.ProportionalHeight
                                    color: Theme.textPrimary; wrapMode: Text.WordWrap
                                }
                                Rectangle {
                                    width: parent.width * 0.3; height: 1
                                    color: Theme.cardBorder; anchors.horizontalCenter: parent.horizontalCenter
                                }
                            }
                        }
                    }

                    ScrollBar.vertical: ScrollBar {
                        policy: ScrollBar.AsNeeded
                        onPositionChanged: {
                            var y = readerFlickable.contentY
                            for (var i = 0; i < root.chapters.length; i++) {
                                var h = 100 + ((root.chapters[i].content || "").length / 100) * 16
                                if (y < h) { root.currentChapter = i; break }
                                y -= h
                            }
                        }
                    }

                    MouseArea {
                        anchors.fill: parent; acceptedButtons: Qt.LeftButton
                        onClicked: function(mouse) {
                            if (mouse.x < parent.width * 0.2 && root.currentChapter > 0) {
                                root.currentChapter--; readerFlickable.contentY = 0
                            } else if (mouse.x > parent.width * 0.8 && root.currentChapter < root.chapters.length - 1) {
                                root.currentChapter++; readerFlickable.contentY = 0
                            }
                        }
                    }
                }

                Text {
                    anchors.centerIn: parent; visible: chapters.length === 0
                    text: "Không thể đọc file này"
                    font.family: Theme.fontFamily; color: Theme.textMuted
                }
            }
        }
    }
}
