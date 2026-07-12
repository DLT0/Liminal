import re

path = "src/qml/main.qml"
with open(path, "r") as f:
    content = f.read()

replacement = """                    Flickable {
                        id: videoPage
                        objectName: "videoPage"
                        anchors.fill: parent
                        visible: backend.currentPage === 3
                        clip: true
                        contentWidth: width
                        contentHeight: videoContent.height
                        interactive: videoContent.height > videoPage.height

                        ScrollBar.vertical: ScrollBar { policy: ScrollBar.AsNeeded }

                        Item {
                            id: videoContent
                            width: videoPage.width
                            height: backend.inCollectionView
                                ? videoPage.height
                                : backend.videoSearchActive
                                    ? videoSearchPage.y + videoSearchPage.height + Theme.contentPadding
                                    : videoMyMoviesPage.y + videoMyMoviesPage.height + Theme.contentPadding

                            readonly property int videoColumns: Theme.gridColumns
                            readonly property real videoCellWidth: Math.floor(
                                (width - 2 * Theme.contentPadding - (videoColumns - 1) * Theme.cardGap) / videoColumns
                            )
                            readonly property real videoCellHeight: Math.ceil(Math.max(videoCellWidth / Theme.videoPosterAspect, videoCellWidth * 0.82)) + 8

                            readonly property real sharedHeight: Math.max(
                                180,
                                Math.ceil((Number(backend.videoSharedModel.count) || 0) / videoColumns) * videoCellHeight + 16
                            )
                            readonly property real seriesHeight: Math.max(
                                180,
                                Math.ceil((Number(backend.videoSeriesModel.count) || 0) / videoColumns) * videoCellHeight + 16
                            )
                            readonly property real moviesHeight: Math.max(
                                180,
                                Math.ceil((Number(backend.videoMoviesModel.count) || 0) / videoColumns) * videoCellHeight + 16
                            )
                            readonly property real myMoviesHeight: Math.max(
                                180,
                                Math.ceil((Number(backend.videoMyMoviesModel.count) || 0) / videoColumns) * videoCellHeight + 16
                            )
                            readonly property real searchHeight: Math.max(
                                180,
                                Math.ceil((Number(backend.videoSearchModel.count) || 0) / videoColumns) * videoCellHeight + 16
                            )

                            readonly property bool showShared: backend.videoSharedModel.count > 0

                            Text {
                                id: sharedTitle
                                x: Theme.contentPadding
                                y: Theme.contentPadding
                                width: parent.width - 2 * Theme.contentPadding
                                text: "Được chia sẻ với tôi"
                                font.family: Theme.fontFamily
                                font.pixelSize: 24
                                font.weight: Font.Bold
                                color: Theme.textPrimary
                                visible: !backend.inCollectionView && !backend.videoSearchActive && videoContent.showShared
                            }

                            LibraryPage {
                                id: videoSharedPage
                                objectName: "videoSharedPage"
                                x: 0
                                y: backend.inCollectionView ? 0 : (videoContent.showShared ? sharedTitle.y + sharedTitle.height + 4 : Theme.contentPadding)
                                width: parent.width
                                height: backend.inCollectionView ? parent.height : (videoContent.showShared ? videoContent.sharedHeight : 0)
                                visible: backend.inCollectionView || (!backend.videoSearchActive && videoContent.showShared)
                                model: backend.videoSharedModel
                                useVideoStyle: true
                                widescreenPosters: true
                                showScrollBar: false
                                scrollEnabled: false
                                verticalContentMargin: 8
                                gridColumns: videoContent.videoColumns
                                showBackButton: backend.libraryCanGoBack
                                breadcrumb: backend.libraryBreadcrumb
                                inCollectionView: backend.inCollectionView
                                bannerTitle: backend.collectionBannerTitle
                                bannerSubtitle: backend.collectionBannerSubtitle
                                bannerImage: backend.collectionBannerImage
                                hasPlayableTracks: backend.collectionHasPlayableTracks
                                isPlaying: backend.isPlaying
                                emptyTitle: ""
                                emptyMessage: ""
                                onPlayRequested: function(index) { backend.playMedia(index) }
                                onOpenCollectionRequested: function(index) { backend.openCollection(index) }
                                onPlayAllRequested: backend.togglePlayCollection()
                                onShufflePlayRequested: backend.playCollectionShuffled()
                            }

                            Text {
                                id: seriesTitle
                                x: Theme.contentPadding
                                y: videoContent.showShared ? videoSharedPage.y + videoSharedPage.height + 8 : Theme.contentPadding
                                width: parent.width - 2 * Theme.contentPadding
                                text: "Phim bộ"
                                font.family: Theme.fontFamily
                                font.pixelSize: 24
                                font.weight: Font.Bold
                                color: Theme.textPrimary
                                visible: !backend.inCollectionView && !backend.videoSearchActive
                            }

                            LibraryPage {
                                id: videoSeriesPage
                                objectName: "videoSeriesPage"
                                x: 0
                                y: seriesTitle.y + seriesTitle.height + 4
                                width: parent.width
                                height: videoContent.seriesHeight
                                visible: !backend.inCollectionView && !backend.videoSearchActive
                                model: backend.videoSeriesModel
                                useVideoStyle: true
                                widescreenPosters: true
                                showScrollBar: false
                                scrollEnabled: false
                                verticalContentMargin: 8
                                gridColumns: videoContent.videoColumns
                                showBackButton: false
                                inCollectionView: false
                                isPlaying: backend.isPlaying
                                emptyTitle: "Chưa có phim bộ"
                                emptyMessage: "Tạo thư mục trong thư mục Videos để thêm phim bộ."
                                onPlayRequested: function(index) { backend.playMedia(index) }
                                onOpenCollectionRequested: function(index) { backend.openVideoSeries(index) }
                            }

                            Text {
                                id: moviesTitle
                                x: Theme.contentPadding
                                y: videoSeriesPage.y + videoSeriesPage.height + 8
                                width: parent.width - 2 * Theme.contentPadding
                                text: "Phim lẻ"
                                font.family: Theme.fontFamily
                                font.pixelSize: 24
                                font.weight: Font.Bold
                                color: Theme.textPrimary
                                visible: !backend.inCollectionView && !backend.videoSearchActive
                            }

                            LibraryPage {
                                id: videoMoviesPage
                                objectName: "videoMoviesPage"
                                x: 0
                                y: moviesTitle.y + moviesTitle.height + 4
                                width: parent.width
                                height: videoContent.moviesHeight
                                visible: !backend.inCollectionView && !backend.videoSearchActive
                                model: backend.videoMoviesModel
                                useVideoStyle: true
                                widescreenPosters: true
                                showScrollBar: false
                                scrollEnabled: false
                                verticalContentMargin: 8
                                gridColumns: videoContent.videoColumns
                                showBackButton: false
                                inCollectionView: false
                                isPlaying: backend.isPlaying
                                emptyTitle: "Chưa có phim lẻ"
                                emptyMessage: "Đang chờ cập nhật."
                                onPlayRequested: function(index) { backend.playVideoMovie(index) }
                            }

                            Text {
                                id: myMoviesTitle
                                x: Theme.contentPadding
                                y: videoMoviesPage.y + videoMoviesPage.height + 8
                                width: parent.width - 2 * Theme.contentPadding
                                text: "Phim của tôi"
                                font.family: Theme.fontFamily
                                font.pixelSize: 24
                                font.weight: Font.Bold
                                color: Theme.textPrimary
                                visible: !backend.inCollectionView && !backend.videoSearchActive
                            }

                            LibraryPage {
                                id: videoMyMoviesPage
                                objectName: "videoMyMoviesPage"
                                x: 0
                                y: myMoviesTitle.y + myMoviesTitle.height + 4
                                width: parent.width
                                height: videoContent.myMoviesHeight
                                visible: !backend.inCollectionView && !backend.videoSearchActive
                                model: backend.videoMyMoviesModel
                                useVideoStyle: true
                                widescreenPosters: true
                                showScrollBar: false
                                scrollEnabled: false
                                verticalContentMargin: 8
                                gridColumns: videoContent.videoColumns
                                showBackButton: false
                                inCollectionView: false
                                isPlaying: backend.isPlaying
                                emptyTitle: "Chưa có phim nào"
                                emptyMessage: "Thêm phim vào thư mục Videos."
                                onPlayRequested: function(index) { backend.playVideoMyMovie(index) }
                            }

                            LibraryPage {
                                id: videoSearchPage
                                objectName: "videoSearchPage"
                                x: 0
                                y: Theme.contentPadding
                                width: parent.width
                                height: videoContent.searchHeight
                                visible: backend.videoSearchActive
                                model: backend.videoSearchModel
                                useVideoStyle: true
                                widescreenPosters: true
                                showScrollBar: false
                                scrollEnabled: false
                                verticalContentMargin: 8
                                gridColumns: videoContent.videoColumns
                                showBackButton: false
                                inCollectionView: false
                                isPlaying: backend.isPlaying
                                emptyTitle: "Không tìm thấy video"
                                emptyMessage: "Thử từ khóa khác."
                                onPlayRequested: function(index) { backend.playVideoSearch(index) }
                            }
                        }
                    }"""

pattern = re.compile(r'                    Flickable \{\s*id: videoPage\s*objectName: "videoPage".*?(?=                    \n                    Download \{\n                        id: downloadPage)', re.DOTALL)
new_content = pattern.sub(replacement, content)

with open(path, "w") as f:
    f.write(new_content)

print("Done")
