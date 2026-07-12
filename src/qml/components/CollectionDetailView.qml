import QtQuick
import QtQuick.Controls
import Liminal 1.0

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
    signal playAllRequested()
    signal shufflePlayRequested()

    EditMediaDialog {
        id: editDialog
        parent: Overlay.overlay
    }

    ListModel {
        id: moveTargetsModel
    }

    function populateMoveTargets(sourcePath) {
        moveTargetsModel.clear()
        if (!sourcePath)
            return
        var folders = backend.foldersForMove(sourcePath)
        for (var i = 0; i < folders.length; i++)
            moveTargetsModel.append(folders[i])
    }

    function openRowContextMenu(index, isCollection, title, artist, itemPath, anchorItem, x, y) {
        rowContextMenu.itemIndex = index
        rowContextMenu.isCollection = isCollection
        rowContextMenu.itemTitle = title
        rowContextMenu.itemArtist = artist
        rowContextMenu.itemPath = itemPath
        if (!isCollection)
            populateMoveTargets(itemPath)
        else
            moveTargetsModel.clear()
        rowContextMenu.popup(anchorItem, x, y)
    }

    StyledMenu {
        id: rowContextMenu
        property int itemIndex: -1
        property bool isCollection: false
        property string itemTitle: ""
        property string itemArtist: ""
        property string itemPath: ""

        StyledMenuItem {
            iconName: rowContextMenu.isCollection ? "folder_open" : "play_arrow"
            text: rowContextMenu.isCollection ? "Mở playlist" : "Phát"
            onTriggered: {
                if (rowContextMenu.isCollection)
                    root.openCollectionRequested(rowContextMenu.itemIndex)
                else
                    root.playRequested(rowContextMenu.itemIndex)
            }
        }
        StyledMenuItem {
            iconName: "drive_file_move"
            text: "Xóa khỏi playlist"
            enabled: backend.libraryCanGoBack && !rowContextMenu.isCollection
            onTriggered: backend.moveMediaOutOfFolder(rowContextMenu.itemIndex)
        }
        StyledMenu {
            id: moveToFolderMenu
            title: "Thêm vào playlist khác"
            enabled: !rowContextMenu.isCollection

            Instantiator {
                model: moveTargetsModel
                delegate: StyledMenuItem {
                    iconName: "folder"
                    required property string title
                    required property string path
                    text: title
                    onTriggered: backend.moveMediaToFolder(rowContextMenu.itemPath, path)
                }
                onObjectAdded: function(index, object) { moveToFolderMenu.addItem(object) }
                onObjectRemoved: function(index, object) { moveToFolderMenu.removeItem(object) }
            }
            StyledMenuItem {
                visible: moveTargetsModel.count === 0
                enabled: false
                text: "Không còn playlist khác"
            }
        }
        StyledMenuItem {
            iconName: "image"
            text: "Đổi ảnh bìa"
            onTriggered: backend.pickMediaCoverByPath(rowContextMenu.itemPath)
        }
        StyledMenuItem {
            iconName: "edit"
            text: "Chỉnh sửa thông tin"
            onTriggered: editDialog.openFor(
                rowContextMenu.itemPath,
                rowContextMenu.itemTitle,
                rowContextMenu.itemArtist
            )
        }
        StyledMenuSeparator {}
        StyledMenuItem {
            iconName: "delete"
            destructive: true
            text: "Xóa khỏi thư viện"
            onTriggered: backend.deleteMediaByPath(rowContextMenu.itemPath)
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
                color: Theme.bgElevated

                Image {
                    anchors.fill: parent
                    source: root.resolvedBannerImage
                    fillMode: Image.PreserveAspectCrop
                    visible: root.bannerImage !== ""
                    opacity: 0.3
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

        // Action bar
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
                color: Theme.accent
                opacity: root.hasPlayableTracks ? 1 : 0.45

                AppIcon {
                    anchors.centerIn: parent
                    name: root.isPlaying ? "pause" : "play_arrow"
                    filled: true
                    font.pixelSize: 32
                    color: "#000000"
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

            IconButton {
                id: orderShuffleBtn
                anchors.verticalCenter: parent.verticalCenter
                icon: "casino"
                iconSize: 24
                width: 40
                height: 40
                visible: backend.collectionCanShuffleOrder
                onClicked: backend.shuffleCollectionOrder()
            }

            IconButton {
                id: orderUndoBtn
                anchors.verticalCenter: parent.verticalCenter
                icon: "undo"
                iconSize: 24
                width: 40
                height: 40
                visible: backend.collectionCanShuffleOrder
                opacity: backend.collectionOrderCanUndo ? 1 : 0.35
                enabled: backend.collectionOrderCanUndo
                onClicked: backend.undoCollectionOrderShuffle()
            }

            Item {
                width: Math.max(0, actionBar.width - actionBar.leftPadding - actionBar.rightPadding
                                - 36 - 16 - 56 - 16 - 40 - 16
                                - (orderShuffleBtn.visible ? 40 + 16 : 0)
                                - (orderUndoBtn.visible ? 40 + 16 : 0)
                                - hintText.implicitWidth)
                height: 1
            }

            Text {
                id: hintText
                anchors.verticalCenter: parent.verticalCenter
                text: "Chuột phải để thao tác"
                font.family: Theme.fontFamily
                font.pixelSize: Theme.captionSize
                color: Theme.textMuted
            }
        }

        ListView {
            id: listView
            width: parent.width
            height: parent.height - banner.height - actionBar.height
            clip: true
            boundsBehavior: Flickable.StopAtBounds
            spacing: 2

            ScrollBar.vertical: ScrollBar { policy: ScrollBar.AsNeeded }

            delegate: Rectangle {
                id: row
                width: listView.width
                height: 56
                radius: Theme.libraryCardRadius

                property string rowPath: model.path
                property string rowImage: model.imageSource
                property bool isCollection: model.isCollection
                property string resolvedRowImage: {
                    if (!rowImage)
                        return ""
                    if (rowImage.startsWith("http://") || rowImage.startsWith("https://") || rowImage.startsWith("file://"))
                        return rowImage
                    return "file://" + rowImage
                }

                color: rowHoverHandler.hovered ? Theme.bgCardHover : Theme.bgCard

                Behavior on color {
                    ColorAnimation { duration: Theme.colorDuration }
                }

                HoverHandler {
                    id: rowHoverHandler
                    acceptedDevices: PointerDevice.Mouse | PointerDevice.TouchScreen
                }

                TapHandler {
                    acceptedButtons: Qt.LeftButton
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
                        root.openRowContextMenu(
                            index,
                            model.isCollection,
                            model.title,
                            model.subtitle,
                            rowPath,
                            row,
                            mouse.x,
                            mouse.y
                        )
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
                        width: parent.width - 280
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

                    Row {
                        anchors.verticalCenter: parent.verticalCenter
                        spacing: 2

                        IconButton {
                            icon: "arrow_upward"
                            iconSize: 18
                            width: 32
                            height: 32
                            opacity: index > 0 ? 1 : 0.3
                            enabled: index > 0
                            onClicked: backend.moveCollectionItemUp(index)
                        }

                        IconButton {
                            icon: "arrow_downward"
                            iconSize: 18
                            width: 32
                            height: 32
                            opacity: index < listView.count - 1 ? 1 : 0.3
                            enabled: index < listView.count - 1
                            onClicked: backend.moveCollectionItemDown(index)
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
            }
        }
    }
}
