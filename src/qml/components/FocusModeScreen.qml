import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import QtMultimedia
import Liminal 1.0

Item {
    id: root

    visible: backend.inFocusMode
    z: 100

    property bool controlsVisible: true
    property bool episodeSidebarOpen: false
    property real volumePercent: 100
    // Video mute is intentionally independent from backend.muted, which belongs
    // to the music/mpv player and must not mute video playback.
    property bool videoMuted: false
    readonly property int autoHideDelay: 3000
    // Keep video inside the QML scene. The native mpv --wid surface can be
    // above QML overlays, which hides the episode sidebar and controls.
    // User-selectable playback backend. In-app Qt Multimedia is the default.
    // The value is captured when Focus Mode opens so changing Settings cannot
    // switch pipelines while a video is already playing.
    property bool useMpv: false

    signal videoPlaybackStateChanged(bool isPlaying)
    signal videoPositionChanged(int positionMs)
    signal videoDurationChanged(int durationMs)

    function formatTime(milliseconds) {
        const total = Math.floor(Math.max(0, milliseconds) / 1000)
        const h = Math.floor(total / 3600)
        const m = Math.floor((total % 3600) / 60)
        const s = total % 60
        if (h > 0)
            return h + ":" + (m < 10 ? "0" : "") + m + ":" + (s < 10 ? "0" : "") + s
        return m + ":" + (s < 10 ? "0" : "") + s
    }

    function showControls() {
        controlsVisible = true
        hideTimer.restart()
    }

    function isPlaying() {
        return useMpv ? mpvVideo.playing : (videoPlayer.playbackState === MediaPlayer.PlayingState)
    }

    function togglePlayback() {
        if (useMpv)
            mpvVideo.togglePause()
        else if (videoPlayer.playbackState === MediaPlayer.PlayingState)
            videoPlayer.pause()
        else
            videoPlayer.play()
    }

    function seekTo(positionMs) {
        if (useMpv)
            mpvVideo.seek(positionMs)
        else
            videoPlayer.setPosition(positionMs)
    }

    function currentPosition() {
        return useMpv ? mpvVideo.position : videoPlayer.position
    }

    function currentDuration() {
        return useMpv ? mpvVideo.duration : videoPlayer.duration
    }

    function startPlayback() {
        playbackError.visible = false
        if (useMpv) {
            mpvVideo.attachToItem(mpvHost)
            applyVideoVolume()
            mpvVideo.play(backend.focusModeSource)
            return
        }
        videoPlayer.source = backend.focusModeSource
        videoPlayer.play()
    }

    function stopPlayback() {
        if (useMpv) {
            mpvVideo.stop()
            mpvVideo.detach()
            return
        }
        videoPlayer.stop()
        videoPlayer.source = ""
    }

    function applyVideoVolume() {
        if (useMpv)
            mpvVideo.setVolume(videoMuted ? 0 : volumePercent)
        else
            audioOutput.volume = videoMuted ? 0 : (volumePercent / 100) * backend.audioGainFactor
    }

    function setVolume(percent, syncBackend) {
        volumePercent = Math.max(0, Math.min(100, percent))
        videoMuted = volumePercent === 0
        applyVideoVolume()

        // Share the level with PlayerBar, but never share its mute flag.
        if (syncBackend === true && backend.volume !== volumePercent) {
            const musicWasMuted = backend.muted
            backend.setVolume(volumePercent)
            // setVolume() intentionally unmutes the music backend for normal
            // PlayerBar use. Restore its prior mute state when video changes
            // only the shared level.
            if (musicWasMuted && !backend.muted)
                backend.toggleMute()
        }
    }

    function syncVolumeFromBackend(resetVideoMute) {
        volumePercent = backend.volume
        if (resetVideoMute === true)
            videoMuted = volumePercent === 0
        applyVideoVolume()
    }

    function toggleVideoMute() {
        if (videoMuted) {
            setVolume(volumePercent > 0 ? volumePercent : 100, true)
            return
        }
        videoMuted = true
        applyVideoVolume()
    }

    Timer {
        id: hideTimer
        interval: root.autoHideDelay
        onTriggered: root.controlsVisible = false
    }

    AudioOutput {
        id: audioOutput
        volume: 1.0
    }

    MediaPlayer {
        id: videoPlayer
        audioOutput: audioOutput
        videoOutput: videoOutput

        onPlaybackStateChanged: {
            centerPlayPause.opacity = 1.0
            flashTimer.restart()
        }
        onPlayingChanged: root.videoPlaybackStateChanged(playing)
        onPositionChanged: root.videoPositionChanged(position)
        onDurationChanged: root.videoDurationChanged(duration)
        onMediaStatusChanged: {
            if (mediaStatus === MediaPlayer.EndOfMedia)
                root.handleMediaEnded()
        }
        onErrorOccurred: function(error, errorString) {
            playbackError.text = errorString || "Không thể phát video này."
            playbackError.visible = true
        }
    }

    Connections {
        target: mpvVideo
        enabled: root.useMpv
        function onPlayingChanged() {
            root.videoPlaybackStateChanged(mpvVideo.playing)
            centerPlayPause.opacity = 1.0
            flashTimer.restart()
        }
        function onPositionChanged(positionMs) {
            root.videoPositionChanged(positionMs)
        }
        function onDurationChanged(durationMs) {
            root.videoDurationChanged(durationMs)
        }
        function onMediaEnded() {
            root.handleMediaEnded()
        }
        function onErrorOccurred(message) {
            playbackError.text = message
            playbackError.visible = true
        }
    }

    Connections {
        target: backend
        function onVolumeChanged() {
            if (root.visible)
                root.syncVolumeFromBackend(false)
        }

        function onFocusModeChanged() {
            if (!root.visible || backend.focusModeSource === "")
                return
            if (root.useMpv) {
                if (mpvVideo.playing)
                    mpvVideo.stop()
                root.startPlayback()
                return
            }
            if (videoPlayer.source === backend.focusModeSource)
                return
            videoPlayer.stop()
            root.startPlayback()
        }
    }

    function handleMediaEnded() {
        if (backend.hasNextEpisode)
            backend.nextVideoEpisode()
        else
            backend.exitFocusMode()
    }

    onVisibleChanged: {
        if (visible) {
            useMpv = backend.videoPlaybackMode === "mpv"
            syncVolumeFromBackend(true)
            showControls()
            startPlayback()
        } else {
            episodeSidebarOpen = false
            stopPlayback()
        }
    }

    Rectangle {
        anchors.fill: parent
        color: root.useMpv && mpvVideo.geometryMode ? "transparent" : "black"
    }

    Item {
        id: mpvHost
        anchors.fill: parent
        visible: root.useMpv
    }

    VideoOutput {
        id: videoOutput
        visible: !root.useMpv
        anchors.fill: parent
        fillMode: VideoOutput.PreserveAspectFit
    }

    Text {
        id: playbackError
        anchors.centerIn: parent
        width: parent.width * 0.7
        visible: false
        wrapMode: Text.Wrap
        horizontalAlignment: Text.AlignHCenter
        color: "white"
        font.pixelSize: 16
    }

    MouseArea {
        anchors.fill: parent
        hoverEnabled: true
        cursorShape: root.controlsVisible ? Qt.ArrowCursor : Qt.BlankCursor
        onMouseXChanged: root.showControls()
        onMouseYChanged: root.showControls()
        onClicked: {
            root.showControls()
            if (root.episodeSidebarOpen) {
                root.episodeSidebarOpen = false
                return
            }
            root.togglePlayback()
        }
    }

    Rectangle {
        id: centerPlayPause
        anchors.centerIn: parent
        width: 80
        height: 80
        radius: 40
        color: "#99000000"
        opacity: 0

        Behavior on opacity { NumberAnimation { duration: 250 } }

        AppIcon {
            anchors.centerIn: parent
            name: root.isPlaying() ? "pause" : "play_arrow"
            color: "white"
            font.pixelSize: 36
        }
    }

    Timer {
        id: flashTimer
        interval: 700
        onTriggered: centerPlayPause.opacity = 0
    }

    Shortcut {
        sequence: "Escape"
        enabled: root.visible
        onActivated: {
            root.showControls()
            if (root.episodeSidebarOpen) {
                root.episodeSidebarOpen = false
                return
            }
            if (backend.isFullScreen) {
                backend.toggleFullScreen()
                return
            }
            backend.exitFocusMode()
        }
    }
    Shortcut {
        sequence: "Space"
        enabled: root.visible
        onActivated: {
            root.showControls()
            root.togglePlayback()
        }
    }
    Shortcut {
        sequence: "Left"
        enabled: root.visible
        onActivated: {
            root.showControls()
            root.seekTo(Math.max(0, root.currentPosition() - 10000))
        }
    }
    Shortcut {
        sequence: "Right"
        enabled: root.visible
        onActivated: {
            root.showControls()
            root.seekTo(Math.min(root.currentDuration(), root.currentPosition() + 10000))
        }
    }

    Item {
        anchors.fill: parent
        opacity: root.controlsVisible ? 1 : 0
        enabled: root.controlsVisible

        Behavior on opacity { NumberAnimation { duration: 220 } }

        Rectangle {
            anchors.top: parent.top
            anchors.left: parent.left
            anchors.right: parent.right
            height: 76
            gradient: Gradient {
                GradientStop { position: 0; color: "#d9000000" }
                GradientStop { position: 1; color: "transparent" }
            }

            RowLayout {
                anchors.fill: parent
                anchors.leftMargin: 20
                anchors.rightMargin: 20
                spacing: 14

                IconButton {
                    icon: "arrow_back"
                    iconColor: "white"
                    iconSize: 28
                    Layout.preferredWidth: 44
                    Layout.preferredHeight: 44
                    onClicked: {
                        root.showControls()
                        if (root.episodeSidebarOpen)
                            root.episodeSidebarOpen = false
                        else
                            backend.exitFocusMode()
                    }
                }
                Text {
                    text: backend.focusModeTitle
                    color: "white"
                    font.pixelSize: 21
                    font.weight: Font.DemiBold
                    elide: Text.ElideRight
                    Layout.fillWidth: false
                    Layout.maximumWidth: parent.width * 0.45
                }
                Item { Layout.fillWidth: true }
                IconButton {
                    icon: backend.isFullScreen ? "fullscreen_exit" : "fullscreen"
                    iconColor: "white"
                    iconSize: 26
                    Layout.preferredWidth: 44
                    Layout.preferredHeight: 44
                    onClicked: {
                        root.showControls()
                        backend.toggleFullScreen()
                    }
                }
            }
        }

        Rectangle {
            anchors.bottom: parent.bottom
            anchors.left: parent.left
            anchors.right: parent.right
            height: 144
            gradient: Gradient {
                GradientStop { position: 0; color: "transparent" }
                GradientStop { position: 1; color: "#dd000000" }
            }

            ColumnLayout {
                anchors.fill: parent
                anchors.margins: 24
                spacing: 8

                Slider {
                    id: seekSlider
                    from: 0
                    to: Math.max(1, root.currentDuration())
                    value: root.currentPosition()
                    Layout.fillWidth: true
                    onMoved: root.seekTo(value)
                }

                RowLayout {
                    Layout.fillWidth: true

                    Text { text: root.formatTime(root.currentPosition()); color: "white" }
                    Item { Layout.fillWidth: true }
                    Text {
                        text: "-" + root.formatTime(Math.max(0, root.currentDuration() - root.currentPosition()))
                        color: "white"
                    }
                }

                RowLayout {
                    Layout.fillWidth: true

                    IconButton {
                        icon: "skip_previous"
                        iconColor: "white"
                        visible: backend.hasPreviousEpisode
                        onClicked: {
                            root.showControls()
                            backend.previousVideoEpisode()
                        }
                    }
                    IconButton {
                        icon: "replay_10"
                        iconColor: "white"
                        onClicked: root.seekTo(Math.max(0, root.currentPosition() - 10000))
                    }
                    IconButton {
                        icon: root.isPlaying() ? "pause" : "play_arrow"
                        iconColor: "white"
                        iconSize: 34
                        onClicked: root.togglePlayback()
                    }
                    IconButton {
                        icon: "forward_10"
                        iconColor: "white"
                        onClicked: root.seekTo(Math.min(root.currentDuration(), root.currentPosition() + 10000))
                    }
                    IconButton {
                        icon: "skip_next"
                        iconColor: "white"
                        visible: backend.hasNextEpisode
                        onClicked: {
                            root.showControls()
                            backend.nextVideoEpisode()
                        }
                    }
                    Item { Layout.fillWidth: true }
                    IconButton {
                        icon: root.videoMuted ? "volume_off" : "volume_up"
                        iconColor: "white"
                        onClicked: {
                            root.showControls()
                            root.toggleVideoMute()
                        }
                    }
                    Slider {
                        from: 0
                        to: 100
                        value: root.volumePercent
                        Layout.preferredWidth: 110
                        onMoved: root.setVolume(value, true)
                    }
                }
            }
        }
    }

    MouseArea {
        id: episodeSidebarBackdrop
        anchors.left: parent.left
        anchors.top: parent.top
        anchors.bottom: parent.bottom
        anchors.right: episodeSidebar.left
        visible: root.episodeSidebarOpen
        z: 49
        onClicked: {
            root.episodeSidebarOpen = false
            root.showControls()
        }
    }

    Rectangle {
        id: episodeSidebar
        width: 340
        height: parent.height
        anchors.top: parent.top
        color: Theme.bgElevated
        border.color: Theme.glassBorder
        z: 50

        x: root.episodeSidebarOpen ? parent.width - width : parent.width
        Behavior on x {
            NumberAnimation { duration: 260; easing.type: Easing.OutCubic }
        }

        ListView {
            anchors.top: sidebarHeader.bottom
            anchors.left: parent.left
            anchors.right: parent.right
            anchors.bottom: parent.bottom
            anchors.margins: 16
            anchors.topMargin: 0
            model: backend.currentEpisodeList
            spacing: 8
            clip: true

            delegate: Rectangle {
                width: ListView.view.width
                height: 76
                radius: Theme.focusListRadius
                color: index === backend.currentEpisodeIndex ? "#33ffffff" : "transparent"

                RowLayout {
                    anchors.fill: parent
                    anchors.margins: 8
                    spacing: 12

                    Rectangle {
                        Layout.preferredWidth: 76
                        Layout.preferredHeight: 60
                        radius: 4
                        color: Theme.cardBg
                        clip: true

                        Image {
                            id: episodeThumbnail
                            anchors.fill: parent
                            source: modelData.image || ""
                            fillMode: Image.PreserveAspectCrop
                            visible: source !== ""
                        }

                        Text {
                            anchors.centerIn: parent
                            text: modelData.episode || (index + 1)
                            color: Theme.textMuted
                            font.pixelSize: 22
                            font.weight: Font.Bold
                            visible: episodeThumbnail.status !== Image.Ready
                        }
                    }

                    ColumnLayout {
                        Layout.fillWidth: true
                        spacing: 3

                        Text {
                            text: "S" + (modelData.season || 1) + "E" + (modelData.episode || index + 1)
                            color: Theme.textSecondary
                            font.pixelSize: Theme.captionSize
                        }
                        Text {
                            text: modelData.title || ""
                            color: Theme.textPrimary
                            font.pixelSize: Theme.bodySize
                            elide: Text.ElideRight
                            Layout.fillWidth: true
                        }
                        Text {
                            text: modelData.subtitle || ""
                            color: Theme.textMuted
                            font.pixelSize: Theme.captionSize
                            elide: Text.ElideRight
                            Layout.fillWidth: true
                        }
                    }
                }

                TapHandler {
                    onTapped: {
                        backend.playEpisodeAtIndex(index)
                        root.episodeSidebarOpen = false
                        root.showControls()
                    }
                }
            }
        }

        RowLayout {
            id: sidebarHeader
            anchors.top: parent.top
            anchors.left: parent.left
            anchors.right: parent.right
            height: 60
            anchors.leftMargin: 16
            anchors.rightMargin: 8
            z: 1

            MouseArea {
                anchors.fill: parent
                z: -1
                onClicked: {
                    root.episodeSidebarOpen = false
                    root.showControls()
                }
            }

            Text {
                text: "Tập phim"
                color: Theme.textPrimary
                font.pixelSize: 18
                font.weight: Font.DemiBold
                Layout.fillWidth: true
            }

            IconButton {
                id: closeEpisodeSidebarButton
                icon: "close"
                iconColor: Theme.textPrimary
                iconSize: 24
                Layout.preferredWidth: 44
                Layout.preferredHeight: 44
                z: 2
                onClicked: {
                    root.episodeSidebarOpen = false
                    root.showControls()
                }
            }
        }
    }

    Rectangle {
        id: episodeSidebarStickyTab
        width: 32
        height: 72
        radius: 8
        x: root.episodeSidebarOpen
           ? episodeSidebar.x - width
           : parent.width - width
        anchors.verticalCenter: parent.verticalCenter
        color: Theme.bgElevated
        border.color: Theme.glassBorder
        z: 60
        visible: backend.currentEpisodeList.length > 0 && root.controlsVisible

        IconButton {
            anchors.centerIn: parent
            icon: root.episodeSidebarOpen ? "chevron_right" : "playlist_play"
            iconColor: Theme.textPrimary
            iconSize: 22
            width: 32
            height: 32
            onClicked: {
                root.showControls()
                root.episodeSidebarOpen = !root.episodeSidebarOpen
            }
        }
    }
}
