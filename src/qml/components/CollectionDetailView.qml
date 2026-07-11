import QtQuick
import QtQuick.Controls
import Liminal 1.0
import "DragDrop.js" as DragDrop

Item {
    id: root

    property alias model: listView.model
    property string bannerTitle: ""
    property string bannerSubtitle: ""
    property string bannerImage: ""
    property bool hasPlayableTracks: false
    property bool isPlaying: false
    property string resolvedBannerImage: {
        if (!bannerImage)
            return ""
        if (bannerImage.startsWith("http://") || bannerImage.startsWith("https://") || bannerImage.startsWith("file://"))
            return bannerImage
        return "file://" + bannerImage
    }

    signal playRequested(int index)
    signal openCollectionRequested(int index)
    signal reorderRequested(int fromIndex, int toIndex)
    signal playAllRequested()
    signal shufflePlayRequested()

    EditMediaDialog {
        id: editDialog
        parent: Overlay.overlay
    }

    function openRowContextMenu(index, isCollection, title, artist, anchorItem, x, y) {
        rowContextMenu.itemIndex = index
        rowContextMenu.isCollection = isCollection
        rowContextMenu.itemTitle = title
        rowContextMenu.itemArtist = artist
        rowContextMenu.popup(anchorItem, x, y)
    }

    Menu {
        id: rowContextMenu
        property int itemIndex: -1
        property bool isCollection: false
        property string itemTitle: ""
        property string itemArtist: ""

        MenuItem {
            text: rowContextMenu.isCollection ? "Mở playlist" : "Phát"
            onTriggered: {
                if (rowContextMenu.isCollection)
                    root.openCollectionRequested(rowContextMenu.itemIndex)
                else
                    root.playRequested(rowContextMenu.itemIndex)
            }
        }
        MenuItem {
            text: "Đưa ra ngoài thư mục"
            enabled: backend.libraryCanGoBack && !rowContextMenu.isCollection
            onTriggered: backend.moveMediaOutOfFolder(rowContextMenu.itemIndex)
        }
        MenuItem {
            text: "Đổi ảnh bìa"
            onTriggered: backend.pickMediaCover(rowContextMenu.itemIndex)
        }
        MenuItem {
            text: "Sửa tên / tác giả"
            onTriggered: editDialog.openFor(
                rowContextMenu.itemIndex,
                rowContextMenu.itemTitle,
                rowContextMenu.itemArtist
            )
        }
        MenuSeparator {}
        MenuItem {
            text: "Xóa"
            onTriggered: backend.deleteMediaAt(rowContextMenu.itemIndex)
        }
    }

    Column {
        anchors.fill: parent
        spacing: 0

        // Spotify-style banner
        Item {
            id: banner
            width: parent.width
            height: 220

            Rectangle {
                anchors.fill: parent
                radius: Theme.libraryCardRadius
                clip: true
                color: Theme.cardBg

                Image {
                    anchors.fill: parent
                    source: root.resolvedBannerImage
                    fillMode: Image.PreserveAspectCrop
                    visible: root.bannerImage !== ""
                    opacity: 0.45
                }

                Rectangle {
                    anchors.fill: parent
                    gradient: Gradient {
                        orientation: Gradient.Horizontal
                        GradientStop { position: 0; color: Qt.rgba(Theme.accentStart.r, Theme.accentStart.g, Theme.accentStart.b, 0.55) }
                        GradientStop { position: 0.5; color: Qt.rgba(Theme.bgMid.r, Theme.bgMid.g, Theme.bgMid.b, 0.85) }
                        GradientStop { position: 1; color: Qt.rgba(Theme.bgMid.r, Theme.bgMid.g, Theme.bgMid.b, 0.95) }
                    }
                }
            }

            Row {
                anchors.left: parent.left
                anchors.right: parent.right
                anchors.bottom: parent.bottom
                anchors.margins: 24
                spacing: 20

                Rectangle {
                    width: 120
                    height: 120
                    radius: Theme.libraryCardRadius
                    color: Theme.cardBg
                    border.color: Theme.cardBorder
                    border.width: 1
                    clip: true

                    Image {
                        anchors.fill: parent
                        source: root.resolvedBannerImage
                        fillMode: Image.PreserveAspectCrop
                        visible: root.bannerImage !== ""
                    }

                    Text {
                        anchors.centerIn: parent
                        visible: root.bannerImage === ""
                        text: root.bannerTitle.length > 0 ? root.bannerTitle.charAt(0).toUpperCase() : "♪"
                        font.family: Theme.fontFamily
                        font.pixelSize: 48
                        font.weight: Font.Bold
                        color: Theme.textMuted
                    }
                }

                Column {
                    anchors.verticalCenter: parent.verticalCenter
                    spacing: 8
                    width: parent.width - 160

                    Text {
                        text: "PLAYLIST"
                        font.family: Theme.fontFamily
                        font.pixelSize: Theme.captionSize
                        font.weight: Font.Bold
                        color: Theme.textSecondary
                    }

                    Text {
                        width: parent.width
                        text: root.bannerTitle
                        font.family: Theme.fontFamily
                        font.pixelSize: 36
                        font.weight: Font.Bold
                        color: Theme.textPrimary
                        elide: Text.ElideRight
                    }

                    Text {
                        width: parent.width
                        text: root.bannerSubtitle
                        font.family: Theme.fontFamily
                        font.pixelSize: Theme.bodySize
                        color: Theme.textSecondary
                        elide: Text.ElideRight
                    }
                }
            }
        }

        // Action bar (Spotify-style)
        Row {
            id: actionBar
            width: parent.width
            height: 80
            leftPadding: 24
            rightPadding: 24
            spacing: 16

            IconButton {
                anchors.verticalCenter: parent.verticalCenter
                icon: "arrow_back"
                onClicked: backend.goBackLibrary()
            }

            Rectangle {
                anchors.verticalCenter: parent.verticalCenter
                width: 56
                height: 56
                radius: width / 2
                border.color: Theme.playBorder
                border.width: 1
                opacity: root.hasPlayableTracks ? 1 : 0.45

                gradient: Gradient {
                    GradientStop { position: 0; color: Theme.accentStart }
                    GradientStop { position: 1; color: Theme.accentEnd }
                }

                AppIcon {
                    anchors.centerIn: parent
                    name: root.isPlaying ? "pause" : "play_arrow"
                    filled: true
                    font.pixelSize: 32
                    color: Theme.textOnAccent
                }

                MouseArea {
                    anchors.fill: parent
                    cursorShape: Qt.PointingHandCursor
                    enabled: root.hasPlayableTracks
                    onClicked: root.playAllRequested()
                }
            }

            IconButton {
                anchors.verticalCenter: parent.verticalCenter
                icon: "shuffle"
                iconSize: 24
                width: 40
                height: 40
                active: backend.shuffleOn
                opacity: root.hasPlayableTracks ? 1 : 0.45
                enabled: root.hasPlayableTracks
                onClicked: root.shufflePlayRequested()
            }

            Item {
                width: Math.max(0, actionBar.width - actionBar.leftPadding - actionBar.rightPadding
                                - 36 - 16 - 56 - 16 - 40 - 16 - hintText.implicitWidth)
                height: 1
            }

            Text {
                id: hintText
                anchors.verticalCenter: parent.verticalCenter
                text: "Kéo thả để sắp xếp · Chuột phải để thao tác"
                font.family: Theme.fontFamily
                font.pixelSize: Theme.captionSize
                color: Theme.textMuted
                elide: Text.ElideLeft
            }
        }

        ListView {
            id: listView
            width: parent.width
            height: parent.height - banner.height - actionBar.height
            clip: true
            boundsBehavior: Flickable.StopAtBounds
            spacing: 2

            property bool fileDragActive: false

            ScrollBar.vertical: ScrollBar { policy: ScrollBar.AsNeeded }

            delegate: Rectangle {
                id: row
                width: listView.width
                height: 56
                radius: Theme.libraryCardRadius
                opacity: rowDragHandler.active ? 0.42 : 1.0

                property int rowIndex: index
                property string rowPath: model.path
                property string rowImage: model.imageSource
                property string enteringDragPath: ""
                property bool dropHighlight: rowDropArea.containsDrag
                        && enteringDragPath !== ""
                        && enteringDragPath !== rowPath
                property string resolvedRowImage: {
                    if (!rowImage)
                        return ""
                    if (rowImage.startsWith("http://") || rowImage.startsWith("https://") || rowImage.startsWith("file://"))
                        return rowImage
                    return "file://" + rowImage
                }

                color: dropHighlight || rowHoverHandler.hovered || rowDragHandler.active
                       ? Theme.hoverOverlay : "transparent"

                Behavior on opacity {
                    NumberAnimation { duration: 140; easing.type: Easing.OutCubic }
                }
                Behavior on color {
                    ColorAnimation { duration: 120 }
                }

                Drag.active: rowDragHandler.active
                Drag.source: row
                Drag.keys: ["liminal/media"]
                Drag.dragType: Drag.Automatic
                Drag.supportedActions: Qt.MoveAction
                Drag.mimeData: { "text/plain": rowPath }
                Drag.hotSpot.x: width / 2
                Drag.hotSpot.y: height / 2

                DragHandler {
                    id: rowDragHandler
                    enabled: !model.isCollection
                    dragThreshold: 10
                    onActiveChanged: listView.fileDragActive = active
                }

                HoverHandler {
                    id: rowHoverHandler
                    acceptedDevices: PointerDevice.Mouse | PointerDevice.TouchScreen
                    enabled: !listView.fileDragActive
                }

                TapHandler {
                    acceptedButtons: Qt.LeftButton
                    enabled: !listView.fileDragActive
                    onTapped: {
                        if (model.isCollection)
                            root.openCollectionRequested(index)
                        else
                            root.playRequested(index)
                    }
                }

                MouseArea {
                    anchors.fill: parent
                    acceptedButtons: Qt.RightButton
                    z: -1
                    onClicked: function(mouse) {
                        root.openRowContextMenu(index, model.isCollection, model.title, model.subtitle, row, mouse.x, mouse.y)
                    }
                }

                Row {
                    anchors.fill: parent
                    anchors.leftMargin: 16
                    anchors.rightMargin: 16
                    spacing: 14

                    Text {
                        anchors.verticalCenter: parent.verticalCenter
                        width: 24
                        text: (index + 1).toString()
                        font.family: Theme.fontFamily
                        font.pixelSize: Theme.bodySize
                        color: Theme.textMuted
                        horizontalAlignment: Text.AlignHCenter
                    }

                    Rectangle {
                        anchors.verticalCenter: parent.verticalCenter
                        width: 40
                        height: 40
                        radius: Theme.libraryCardRadius
                        color: Theme.cardBg
                        clip: true

                        Image {
                            anchors.fill: parent
                            source: resolvedRowImage
                            fillMode: Image.PreserveAspectCrop
                            visible: rowImage !== ""
                        }

                        Text {
                            anchors.centerIn: parent
                            visible: rowImage === ""
                            text: model.isCollection ? "📁" : (model.audioOnly ? "♪" : "▶")
                            font.pixelSize: 18
                        }
                    }

                    Column {
                        anchors.verticalCenter: parent.verticalCenter
                        width: parent.width - 180
                        spacing: 2

                        Text {
                            width: parent.width
                            text: model.title
                            font.family: Theme.fontFamily
                            font.pixelSize: Theme.bodySize
                            font.weight: Font.Medium
                            color: Theme.textPrimary
                            elide: Text.ElideRight
                        }

                        Text {
                            width: parent.width
                            text: model.subtitle
                            font.family: Theme.fontFamily
                            font.pixelSize: Theme.captionSize
                            color: Theme.textSecondary
                            elide: Text.ElideRight
                        }
                    }

                    Text {
                        anchors.verticalCenter: parent.verticalCenter
                        text: model.duration || ""
                        font.family: Theme.fontFamily
                        font.pixelSize: Theme.captionSize
                        color: Theme.textMuted
                    }

                    Item {
                        id: dragHandle
                        anchors.verticalCenter: parent.verticalCenter
                        width: Theme.iconButtonSize
                        height: Theme.iconButtonSize
                        visible: !model.isCollection

                        AppIcon {
                            anchors.centerIn: parent
                            name: "drag_indicator"
                            font.pixelSize: 18
                            color: rowDragHandler.active ? Theme.accentStart : Theme.textMuted
                        }
                    }

                    IconButton {
                        anchors.verticalCenter: parent.verticalCenter
                        icon: "drive_file_move"
                        iconSize: 18
                        visible: !model.isCollection && backend.libraryCanGoBack
                        onClicked: backend.moveMediaOutOfFolder(index)
                    }
                }

                DropArea {
                    id: rowDropArea
                    anchors.fill: parent
                    z: listView.fileDragActive ? 50 : -10
                    keys: ["liminal/media"]

                    onEntered: function(drag) {
                        enteringDragPath = DragDrop.readMimePath(drag)
                    }
                    onExited: enteringDragPath = ""
                    onDropped: function(drop) {
                        DragDrop.acceptDrop(drop)
                        var src = DragDrop.readMimePath(drop) || enteringDragPath
                        enteringDragPath = ""
                        if (!src || src === rowPath)
                            return
                        if (model.isCollection) {
                            backend.moveMediaByPath(src, rowPath)
                            return
                        }
                        backend.reorderCollectionByPath(src, rowPath)
                    }
                }
            }
        }
    }
}
