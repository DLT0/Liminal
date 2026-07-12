import QtQuick
import QtQuick.Controls
import Liminal 1.0

Item {
    id: root

    property alias model: musicListView.model
    property string bannerTitle: ""
    property string bannerSubtitle: ""
    property string bannerImage: ""
    property string bannerDescription: ""
    property bool hasPlayableTracks: false
    property bool isPlaying: false
    property bool useSeriesStyle: false
    property bool useMovieStyle: false
    property bool showDownloadState: false
    property int selectedSeason: 0

    readonly property bool useVideoDetailStyle: root.useSeriesStyle || root.useMovieStyle
    readonly property var seasonList: backend.collectionSeasons
    readonly property string resolvedBannerImage: {
        if (!bannerImage)
            return ""
        if (bannerImage.startsWith("http://") || bannerImage.startsWith("https://") || bannerImage.startsWith("file://"))
            return bannerImage
        return "file://" + bannerImage
    }
    readonly property string playButtonLabel: backend.collectionPrimaryPlayLabel || "Phát"
    readonly property int heroHeight: Math.min(500, Math.max(360, Math.round(height * 0.58)))

    signal playRequested(int index)
    signal openCollectionRequested(int index)
    signal playAllRequested()
    signal shufflePlayRequested()
    signal downloadEpisodeRequested(int index)
    signal seriesSetupRequested()
    signal seriesShareRequested()

    onSeasonListChanged: {
        if (seasonList.length > 0)
            selectedSeason = seasonList[0]
        else
            selectedSeason = 0
    }

    onSelectedSeasonChanged: {
        if (netflixScroll.visible)
            netflixScroll.contentY = Math.min(netflixScroll.contentY, netflixHero.height)
    }

    onVisibleChanged: {
        if (visible && useVideoDetailStyle)
            netflixScroll.contentY = 0
    }

    EditMediaDialog {
        id: editDialog
        parent: Overlay.overlay
    }

    SeriesSetupDialog {
        id: seriesSetupDialog
        parent: Overlay.overlay
    }

    SeriesTapOrderDialog {
        id: seriesTapOrderDialog
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

    function openRowContextMenu(index, isCollection, title, artist, itemPath, anchorItem, x, y, season, episode) {
        rowContextMenu.itemIndex = index
        rowContextMenu.isCollection = isCollection
        rowContextMenu.itemTitle = title
        rowContextMenu.itemArtist = artist
        rowContextMenu.itemPath = itemPath
        rowContextMenu.itemSeason = season || 1
        rowContextMenu.itemEpisode = episode || (index + 1)
        if (!isCollection && !root.useVideoDetailStyle
                && backend.mediaCanMoveToPlaylist(itemPath))
            populateMoveTargets(itemPath)
        else
            moveTargetsModel.clear()
        rowContextMenu.popup(anchorItem, x, y)
    }

    function episodeMatchesSeason(season) {
        if (!root.useSeriesStyle || root.seasonList.length <= 1)
            return true
        if (root.selectedSeason <= 0)
            return true
        return season === root.selectedSeason
    }

    SeriesEpisodeDialog {
        id: seriesEpisodeDialog
        parent: Overlay.overlay
    }

    StyledMenu {
        id: rowContextMenu
        property int itemIndex: -1
        property bool isCollection: false
        property string itemTitle: ""
        property string itemArtist: ""
        property string itemPath: ""
        property int itemSeason: 1
        property int itemEpisode: 1
        readonly property bool showMoveToPlaylistMenu: !root.useVideoDetailStyle
            && !rowContextMenu.isCollection
            && backend.mediaCanMoveToPlaylist(rowContextMenu.itemPath)

        StyledMenuItem {
            iconName: rowContextMenu.isCollection ? "folder_open" : "play_arrow"
            text: rowContextMenu.isCollection
                ? (root.useSeriesStyle ? "Mở thư mục" : "Mở playlist")
                : "Phát"
            onTriggered: {
                if (rowContextMenu.isCollection)
                    root.openCollectionRequested(rowContextMenu.itemIndex)
                else
                    root.playRequested(rowContextMenu.itemIndex)
            }
        }
        StyledMenuItem {
            visible: !root.useVideoDetailStyle
            iconName: "drive_file_move"
            text: "Xóa khỏi playlist"
            enabled: backend.libraryCanGoBack && !rowContextMenu.isCollection
            onTriggered: backend.moveMediaOutOfFolder(rowContextMenu.itemIndex)
        }
        StyledMenuItem {
            visible: root.useSeriesStyle && !rowContextMenu.isCollection
            iconName: "drive_file_move"
            text: "Chuyển về Phim của tôi"
            enabled: backend.libraryCanGoBack
            onTriggered: backend.moveMediaOutOfFolder(rowContextMenu.itemIndex)
        }
        StyledMenuItem {
            id: moveToPlaylistEntry
            visible: rowContextMenu.showMoveToPlaylistMenu
            enabled: rowContextMenu.showMoveToPlaylistMenu
            iconName: "folder"
            text: "Thêm vào playlist khác"
            onTriggered: moveToFolderMenu.popup(moveToPlaylistEntry, moveToPlaylistEntry.width, 0)
        }
        StyledMenuItem {
            iconName: "image"
            text: "Đổi ảnh bìa"
            onTriggered: backend.pickMediaCoverByPath(rowContextMenu.itemPath)
        }
        StyledMenuItem {
            iconName: "edit"
            text: root.useSeriesStyle ? "Chỉnh mùa / tập" : "Chỉnh sửa thông tin"
            onTriggered: {
                if (root.useSeriesStyle)
                    seriesEpisodeDialog.openFor(
                        rowContextMenu.itemPath,
                        rowContextMenu.itemTitle,
                        rowContextMenu.itemSeason,
                        rowContextMenu.itemEpisode
                    )
                else
                    editDialog.openFor(
                        rowContextMenu.itemPath,
                        rowContextMenu.itemTitle,
                        rowContextMenu.itemArtist
                    )
            }
        }
        StyledMenuSeparator {}
        StyledMenuItem {
            iconName: "delete"
            destructive: true
            text: "Xóa khỏi thư viện"
            onTriggered: backend.deleteMediaByPath(rowContextMenu.itemPath)
        }
    }

    Menu {
        id: moveToFolderMenu
        parent: Overlay.overlay
        topPadding: 8
        bottomPadding: 8
        leftPadding: 8
        rightPadding: 8

        background: Rectangle {
            radius: 10
            color: Theme.glassStrong
            border.width: 1
            border.color: Theme.glassStrongBorder
        }

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

    // ── Music / playlist layout (unchanged) ──────────────────────────────
    Column {
        id: musicDetailColumn
        anchors.fill: parent
        visible: !root.useVideoDetailStyle
        spacing: 0

        Item {
            id: musicBanner
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

        Row {
            id: musicActionBar
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
                anchors.verticalCenter: parent.verticalCenter
                icon: "casino"
                iconSize: 24
                width: 40
                height: 40
                visible: backend.collectionCanShuffleOrder
                onClicked: backend.shuffleCollectionOrder()
            }

            IconButton {
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
        }

        ListView {
            id: musicListView
            width: parent.width
            height: parent.height - musicBanner.height - musicActionBar.height
            clip: true
            boundsBehavior: Flickable.StopAtBounds
            spacing: 2
            model: root.model

            ScrollBar.vertical: ScrollBar { policy: ScrollBar.AsNeeded }

            delegate: Rectangle {
                width: musicListView.width
                height: 56
                radius: Theme.libraryCardRadius
                color: musicRowHover.hovered ? Theme.bgCardHover : Theme.bgCard

                property string rowPath: model.path
                property string rowImage: model.imageSource

                HoverHandler { id: musicRowHover }

                TapHandler {
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
                            index, model.isCollection, model.title, model.artist,
                            rowPath, parent, mouse.x, mouse.y, model.season, model.episode
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
                            source: rowImage ? (rowImage.startsWith("file://") || rowImage.startsWith("http") ? rowImage : "file://" + rowImage) : ""
                            fillMode: Image.PreserveAspectCrop
                            visible: rowImage !== ""
                        }
                    }

                    Column {
                        anchors.verticalCenter: parent.verticalCenter
                        width: parent.width - 200
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
                }
            }
        }
    }

    // ── Netflix-style video detail ───────────────────────────────────────
    Rectangle {
        id: stickyBar
        anchors.top: parent.top
        anchors.left: parent.left
        anchors.right: parent.right
        height: 56
        z: 10
        visible: root.useVideoDetailStyle && netflixScroll.contentY > root.heroHeight - 72
        color: Theme.bgBase
        opacity: 0.96
        border.color: Theme.border
        border.width: 1

        Row {
            anchors.fill: parent
            anchors.leftMargin: 12
            anchors.rightMargin: 20
            spacing: 8

            IconButton {
                anchors.verticalCenter: parent.verticalCenter
                icon: "arrow_back"
                onClicked: backend.goBackLibrary()
            }

            Text {
                anchors.verticalCenter: parent.verticalCenter
                width: parent.width - 96
                text: root.bannerTitle
                font.family: Theme.fontFamily
                font.pixelSize: 16
                font.weight: Font.Bold
                color: Theme.textPrimary
                elide: Text.ElideRight
            }
        }
    }

    Flickable {
        id: netflixScroll
        anchors.fill: parent
        visible: root.useVideoDetailStyle
        clip: true
        boundsBehavior: Flickable.StopAtBounds
        contentWidth: width
        contentHeight: netflixHero.height + netflixBody.implicitHeight
        interactive: contentHeight > height

        ScrollBar.vertical: ScrollBar { policy: ScrollBar.AsNeeded }

        Item {
            id: netflixHero
            width: netflixScroll.width
            height: root.heroHeight

            Item {
                anchors.fill: parent
                clip: true

                Item {
                    width: parent.width
                    height: parent.height + 80
                    y: Math.min(0, -netflixScroll.contentY * 0.35)

                    Image {
                        anchors.fill: parent
                        source: root.resolvedBannerImage
                        fillMode: Image.PreserveAspectCrop
                        visible: root.bannerImage !== ""
                    }
                }
            }

            Rectangle {
                anchors.fill: parent
                visible: root.bannerImage === ""
                color: "#1a1a1a"
            }

            Rectangle {
                anchors.fill: parent
                gradient: Gradient {
                    GradientStop { position: 0.0; color: "#33000000" }
                    GradientStop { position: 0.55; color: "#99000000" }
                    GradientStop { position: 1.0; color: Theme.bgBase }
                }
            }

            Rectangle {
                anchors.fill: parent
                gradient: Gradient {
                    orientation: Gradient.Horizontal
                    GradientStop { position: 0.0; color: "#cc000000" }
                    GradientStop { position: 0.42; color: "#66000000" }
                    GradientStop { position: 0.75; color: "transparent" }
                }
            }

            IconButton {
                x: 20
                y: 20
                icon: "arrow_back"
                iconColor: "#ffffff"
                bordered: true
                width: 40
                height: 40
                onClicked: backend.goBackLibrary()
            }

            Column {
                anchors.left: parent.left
                anchors.right: parent.right
                anchors.bottom: parent.bottom
                anchors.margins: 32
                anchors.rightMargin: Math.max(32, netflixScroll.width * 0.35)
                spacing: 10

                Text {
                    text: root.useMovieStyle ? "PHIM LẺ" : "PHIM BỘ"
                    font.family: Theme.fontFamily
                    font.pixelSize: Theme.captionSize
                    font.weight: Font.Bold
                    color: Theme.accentStart
                }

                Text {
                    width: parent.width
                    text: root.bannerTitle
                    font.family: Theme.fontFamily
                    font.pixelSize: Math.min(52, Math.max(32, netflixScroll.width * 0.04))
                    font.weight: Font.Black
                    color: "#ffffff"
                    wrapMode: Text.Wrap
                    maximumLineCount: 3
                    elide: Text.ElideRight
                }

                Text {
                    width: parent.width
                    visible: root.bannerSubtitle.length > 0
                    text: root.bannerSubtitle
                    font.family: Theme.fontFamily
                    font.pixelSize: Theme.bodySize
                    color: "#d6d6d6"
                    elide: Text.ElideRight
                }
            }
        }

        Column {
            id: netflixBody
            width: netflixScroll.width
            y: netflixHero.height - 24
            spacing: 20
            topPadding: 0
            bottomPadding: 32

            Row {
                width: parent.width - 64
                x: 32
                spacing: 12

                Rectangle {
                    id: primaryPlayBtn
                    height: 44
                    width: playBtnRow.implicitWidth + 28
                    radius: 4
                    color: root.hasPlayableTracks ? "#ffffff" : "#666666"

                    Row {
                        id: playBtnRow
                        anchors.centerIn: parent
                        spacing: 8

                        AppIcon {
                            anchors.verticalCenter: parent.verticalCenter
                            name: root.isPlaying ? "pause" : "play_arrow"
                            filled: true
                            font.pixelSize: 28
                            color: "#000000"
                        }

                        Text {
                            anchors.verticalCenter: parent.verticalCenter
                            text: root.playButtonLabel
                            font.family: Theme.fontFamily
                            font.pixelSize: 16
                            font.weight: Font.Bold
                            color: "#000000"
                        }
                    }

                    MouseArea {
                        anchors.fill: parent
                        cursorShape: Qt.PointingHandCursor
                        enabled: root.hasPlayableTracks || (root.useMovieStyle && root.showDownloadState)
                        onClicked: root.playAllRequested()
                    }
                }

                IconButton {
                    anchors.verticalCenter: parent.verticalCenter
                    icon: "shuffle"
                    iconSize: 22
                    iconColor: "#ffffff"
                    bordered: true
                    width: 44
                    height: 44
                    visible: root.useSeriesStyle
                    active: backend.shuffleOn
                    opacity: root.hasPlayableTracks ? 1 : 0.45
                    enabled: root.hasPlayableTracks
                    onClicked: root.shufflePlayRequested()
                }

                IconButton {
                    anchors.verticalCenter: parent.verticalCenter
                    icon: "format_list_numbered"
                    iconSize: 22
                    iconColor: "#ffffff"
                    bordered: true
                    width: 44
                    height: 44
                    visible: root.useSeriesStyle && !root.showDownloadState
                    onClicked: seriesTapOrderDialog.openDialog(root.bannerTitle)
                }

                IconButton {
                    anchors.verticalCenter: parent.verticalCenter
                    icon: "tune"
                    iconSize: 22
                    iconColor: "#ffffff"
                    bordered: true
                    width: 44
                    height: 44
                    visible: root.useSeriesStyle && !root.showDownloadState
                    onClicked: seriesSetupDialog.openDialog(root.bannerTitle)
                }

                IconButton {
                    anchors.verticalCenter: parent.verticalCenter
                    icon: "share"
                    iconSize: 22
                    iconColor: "#ffffff"
                    bordered: true
                    width: 44
                    height: 44
                    visible: root.useSeriesStyle && !root.showDownloadState
                    onClicked: root.seriesShareRequested()
                }
            }

            Column {
                width: parent.width - 64
                x: 32
                spacing: 8
                visible: root.useMovieStyle

                Text {
                    width: parent.width
                    visible: root.bannerDescription.length > 0
                    text: root.bannerDescription
                    font.family: Theme.fontFamily
                    font.pixelSize: Theme.bodySize
                    color: Theme.textSecondary
                    wrapMode: Text.WordWrap
                    lineHeight: 1.35
                }

                Text {
                    width: parent.width
                    visible: root.bannerDescription.length === 0
                    text: "Xem phim ngay với chất lượng tốt nhất từ thư viện của bạn."
                    font.family: Theme.fontFamily
                    font.pixelSize: Theme.bodySize
                    color: Theme.textMuted
                    wrapMode: Text.WordWrap
                    lineHeight: 1.35
                }
            }

            Column {
                width: parent.width - 64
                x: 32
                spacing: 8
                visible: root.useSeriesStyle && root.bannerDescription.length > 0

                Text {
                    width: parent.width
                    text: root.bannerDescription
                    font.family: Theme.fontFamily
                    font.pixelSize: Theme.bodySize
                    color: Theme.textSecondary
                    wrapMode: Text.WordWrap
                    maximumLineCount: 4
                    elide: Text.ElideRight
                }
            }

            Row {
                id: seasonRow
                x: 32
                width: parent.width - 64
                spacing: 8
                visible: root.useSeriesStyle && root.seasonList.length > 1 && root.seasonList.length <= 6
                height: visible ? 36 : 0

                Repeater {
                    model: root.seasonList

                    Rectangle {
                        required property int modelData
                        height: 32
                        width: seasonLabel.implicitWidth + 20
                        radius: 4
                        color: root.selectedSeason === modelData ? "#ffffff" : "#333333"
                        border.color: root.selectedSeason === modelData ? "#ffffff" : "#555555"
                        border.width: 1

                        Text {
                            id: seasonLabel
                            anchors.centerIn: parent
                            text: "Mùa " + parent.modelData
                            font.family: Theme.fontFamily
                            font.pixelSize: Theme.bodySize
                            font.weight: root.selectedSeason === parent.modelData ? Font.Bold : Font.Normal
                            color: root.selectedSeason === parent.modelData ? "#000000" : "#ffffff"
                        }

                        MouseArea {
                            anchors.fill: parent
                            cursorShape: Qt.PointingHandCursor
                            onClicked: root.selectedSeason = parent.modelData
                        }
                    }
                }
            }

            ComboBox {
                id: seasonCombo
                x: 32
                width: Math.min(220, parent.width - 64)
                visible: root.useSeriesStyle && root.seasonList.length > 6
                model: root.seasonList.map(function(s) { return "Mùa " + s })
                currentIndex: {
                    var idx = root.seasonList.indexOf(root.selectedSeason)
                    return idx >= 0 ? idx : 0
                }
                onActivated: function(index) {
                    if (index >= 0 && index < root.seasonList.length)
                        root.selectedSeason = root.seasonList[index]
                }
            }

            Text {
                x: 32
                visible: root.useSeriesStyle
                text: root.seasonList.length > 1 ? ("Tập · Mùa " + root.selectedSeason) : "Danh sách tập"
                font.family: Theme.fontFamily
                font.pixelSize: 18
                font.weight: Font.Bold
                color: Theme.textPrimary
            }

            ListView {
                id: episodeListView
                width: parent.width
                height: contentHeight
                interactive: false
                spacing: 4
                model: musicListView.model
                visible: root.useSeriesStyle

                delegate: Item {
                    id: episodeRow
                    required property int index
                    required property string title
                    required property string subtitle
                    required property string artist
                    required property string path
                    required property string imageSource
                    required property int season
                    required property int episode
                    required property string duration
                    required property string downloadStatus
                    required property bool isDownloading
                    required property real downloadPercent

                    width: episodeListView.width
                    height: episodeVisible ? 132 : 0
                    visible: height > 0
                    clip: true

                    readonly property bool episodeVisible: {
                        var epSeason = season > 0 ? season : 1
                        return root.episodeMatchesSeason(epSeason)
                    }

                    readonly property string resolvedRowImage: {
                        if (!imageSource)
                            return ""
                        if (imageSource.startsWith("http://") || imageSource.startsWith("https://") || imageSource.startsWith("file://"))
                            return imageSource
                        return "file://" + imageSource
                    }

                    readonly property string episodeTitle: {
                        if (title && title.length > 0)
                            return title
                        if (episode > 0)
                            return "Tập " + episode
                        return "Tập " + (index + 1)
                    }

                    Rectangle {
                        anchors.fill: parent
                        anchors.leftMargin: 24
                        anchors.rightMargin: 24
                        radius: 6
                        color: epHover.hovered ? Theme.bgCardHover : "transparent"
                        border.color: epHover.hovered ? Theme.cardBorder : "transparent"
                        border.width: 1

                        Behavior on color {
                            ColorAnimation { duration: Theme.colorDuration }
                        }

                        HoverHandler { id: epHover }

                        TapHandler {
                            onTapped: {
                                if (root.showDownloadState && downloadStatus !== "done")
                                    root.downloadEpisodeRequested(index)
                                else
                                    root.playRequested(index)
                            }
                            onDoubleTapped: {
                                if (root.showDownloadState && downloadStatus !== "done")
                                    root.downloadEpisodeRequested(index)
                            }
                        }

                        MouseArea {
                            anchors.fill: parent
                            acceptedButtons: Qt.RightButton
                            z: -1
                            onClicked: function(mouse) {
                                root.openRowContextMenu(
                                    index, false, episodeTitle, artist,
                                    path, episodeRow, mouse.x, mouse.y,
                                    season, episode
                                )
                            }
                        }

                        Row {
                            anchors.fill: parent
                            anchors.margins: 12
                            spacing: 16

                            Item {
                                width: 200
                                height: 108
                                anchors.verticalCenter: parent.verticalCenter

                                Rectangle {
                                    anchors.fill: parent
                                    radius: 4
                                    color: Theme.cardBg
                                    clip: true

                                    Image {
                                        anchors.fill: parent
                                        source: resolvedRowImage
                                        fillMode: Image.PreserveAspectCrop
                                        visible: imageSource !== ""
                                    }

                                    Rectangle {
                                        anchors.fill: parent
                                        visible: imageSource === ""
                                        color: Theme.bgElevated

                                        Text {
                                            anchors.centerIn: parent
                                            text: episode > 0 ? episode : (index + 1)
                                            font.family: Theme.fontFamily
                                            font.pixelSize: 28
                                            font.weight: Font.Bold
                                            color: Theme.textMuted
                                        }
                                    }

                                    Rectangle {
                                        anchors.fill: parent
                                        color: "#99000000"
                                        opacity: epHover.hovered ? 1 : 0

                                        Behavior on opacity {
                                            NumberAnimation { duration: 150 }
                                        }

                                        AppIcon {
                                            anchors.centerIn: parent
                                            name: "play_arrow"
                                            filled: true
                                            font.pixelSize: 40
                                            color: "#ffffff"
                                        }
                                    }
                                }
                            }

                            Column {
                                anchors.verticalCenter: parent.verticalCenter
                                width: parent.width - 280
                                spacing: 6

                                Row {
                                    spacing: 8
                                    width: parent.width

                                    Text {
                                        text: (episode > 0 ? episode : (index + 1)) + ". " + episodeTitle
                                        font.family: Theme.fontFamily
                                        font.pixelSize: 15
                                        font.weight: Font.Bold
                                        color: Theme.textPrimary
                                        elide: Text.ElideRight
                                        width: parent.width - (epDuration.visible ? epDuration.implicitWidth + 8 : 0)
                                    }

                                    Text {
                                        id: epDuration
                                        visible: !root.showDownloadState && duration.length > 0
                                        text: duration
                                        font.family: Theme.fontFamily
                                        font.pixelSize: Theme.captionSize
                                        color: Theme.textMuted
                                    }
                                }

                                Text {
                                    width: parent.width
                                    visible: subtitle.length > 0
                                    text: subtitle
                                    font.family: Theme.fontFamily
                                    font.pixelSize: Theme.captionSize
                                    color: Theme.textSecondary
                                    elide: Text.ElideRight
                                }

                                Text {
                                    width: parent.width
                                    visible: root.showDownloadState
                                    text: downloadStatus === "done"
                                        ? "Đã tải — nhấp để phát"
                                        : (isDownloading
                                            ? ("Đang tải " + Math.round(downloadPercent) + "%")
                                            : "Nhấp để tải tập này")
                                    font.family: Theme.fontFamily
                                    font.pixelSize: Theme.captionSize
                                    color: downloadStatus === "done" ? Theme.accentStart : Theme.textMuted
                                }
                            }
                        }
                    }
                }
            }
        }
    }
}
