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
    signal sidebarFocusRequested()
    signal searchFocusRequested()

    property int selectedIndex: -1
    readonly property bool hasKeyboardFocus: keyboardScope.activeFocus

    function activateFocus(selectLast) {
        if (listView.count === 0) {
            keyboardScope.forceActiveFocus()
            selectedIndex = -1
            return
        }
        keyboardScope.forceActiveFocus()
        selectedIndex = selectLast ? listView.count - 1 : 0
        listView.currentIndex = selectedIndex
        listView.positionViewAtIndex(selectedIndex, ListView.Visible)
    }

    function clearSelection() {
        selectedIndex = -1
        listView.currentIndex = -1
    }

    function activateSelectedItem() {
        if (selectedIndex < 0 || selectedIndex >= listView.count)
            return
        listView.positionViewAtIndex(selectedIndex, ListView.Visible)
        var row = listView.itemAtIndex(selectedIndex)
        if (!row)
            return
        if (row.isCollection)
            root.openCollectionRequested(selectedIndex)
        else
            root.playRequested(selectedIndex)
    }

    FocusScope {
        id: keyboardScope
        anchors.fill: parent
        focus: false

        Keys.onPressed: function(event) {
            switch (event.key) {
            case Qt.Key_Up:
                if (selectedIndex > 0) {
                    selectedIndex--
                    listView.currentIndex = selectedIndex
                    listView.positionViewAtIndex(selectedIndex, ListView.Visible)
                } else if (selectedIndex === 0) {
                    root.sidebarFocusRequested()
                } else if (listView.count > 0) {
                    selectedIndex = 0
                    listView.currentIndex = 0
                    listView.positionViewAtIndex(0, ListView.Visible)
                }
                event.accepted = true
                break
            case Qt.Key_Down:
                if (selectedIndex < listView.count - 1) {
                    selectedIndex++
                    listView.currentIndex = selectedIndex
                    listView.positionViewAtIndex(selectedIndex, ListView.Visible)
                } else if (selectedIndex < 0 && listView.count > 0) {
                    selectedIndex = 0
                    listView.currentIndex = 0
                    listView.positionViewAtIndex(0, ListView.Visible)
                }
                event.accepted = true
                break
            case Qt.Key_Return:
            case Qt.Key_Enter:
            case Qt.Key_Space:
                activateSelectedItem()
                event.accepted = true
                break
            case Qt.Key_Backtab:
                root.sidebarFocusRequested()
                event.accepted = true
                break
            case Qt.Key_Tab:
                root.searchFocusRequested()
                event.accepted = true
                break
            }
        }
    }

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
            text: "Đưa ra ngoài thư mục"
            enabled: backend.libraryCanGoBack && !rowContextMenu.isCollection
            onTriggered: backend.moveMediaOutOfFolder(rowContextMenu.itemIndex)
        }
        StyledMenu {
            id: moveToFolderMenu
            title: "Chuyển vào thư mục"
            enabled: !rowContextMenu.isCollection && moveTargetsModel.count > 0

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
        }
        StyledMenuItem {
            iconName: "image"
            text: "Đổi ảnh bìa"
            onTriggered: backend.pickMediaCover(rowContextMenu.itemIndex)
        }
        StyledMenuItem {
            iconName: "edit"
            text: "Chỉnh sửa thông tin"
            onTriggered: editDialog.openFor(
                rowContextMenu.itemIndex,
                rowContextMenu.itemTitle,
                rowContextMenu.itemArtist
            )
        }
        StyledMenuSeparator {}
        StyledMenuItem {
            iconName: "delete"
            destructive: true
            text: "Xóa khỏi thư viện"
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
                text: "Mũi tên lên/xuống để sắp xếp · Phát ngẫu nhiên không đổi thứ tự · Chuột phải để thao tác"
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

            ScrollBar.vertical: ScrollBar { policy: ScrollBar.AsNeeded }

            delegate: Rectangle {
                id: row
                width: listView.width
                height: 56
                radius: Theme.libraryCardRadius

                property string rowPath: model.path
                property string rowImage: model.imageSource
                property bool isCollection: model.isCollection
                property bool keyboardSelected: root.hasKeyboardFocus && root.selectedIndex === index
                property string resolvedRowImage: {
                    if (!rowImage)
                        return ""
                    if (rowImage.startsWith("http://") || rowImage.startsWith("https://") || rowImage.startsWith("file://"))
                        return rowImage
                    return "file://" + rowImage
                }

                color: keyboardSelected
                    ? Qt.rgba(Theme.accentStart.r, Theme.accentStart.g, Theme.accentStart.b, 0.14)
                    : (rowHoverHandler.hovered ? Theme.hoverOverlay : "transparent")

                KeyboardFocusRing {
                    anchors.fill: parent
                    show: keyboardSelected
                    ringRadius: Theme.focusListRadius
                    ringWidth: Theme.focusRingWidth
                }

                Behavior on color {
                    ColorAnimation { duration: 120 }
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
