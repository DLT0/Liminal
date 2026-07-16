import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import Liminal 1.0

GlassPanel {
    id: root

    height: Theme.playerBarHeight
    strong: true
    radius: 0

    property string trackTitle: "LIMINAL"
    property string trackArtist: "Offline Media Player"
    property string trackThumbnail: ""
    property string resolvedThumbnail: {
        if (!trackThumbnail)
            return ""
        if (trackThumbnail.startsWith("http://") || trackThumbnail.startsWith("https://") || trackThumbnail.startsWith("file://"))
            return trackThumbnail
        return "file://" + trackThumbnail
    }
    property bool isPlaying: false
    property bool hasMedia: false
    property int volumeLevel: 100
    property bool muted: false
    property real position: 0
    property real duration: 0
    property bool shuffleOn: false
    property int loopMode: 0  // 0=off, 1=repeat all, 2=repeat one

    property bool seeking: false
    property bool volumeAdjusting: false

    property bool isPodcast: false
    property real playbackSpeed: 1.0

    signal previousClicked()
    signal playClicked()
    signal nextClicked()
    signal shuffleClicked()
    signal loopClicked()
    signal volumeAdjusted(real value)
    signal muteClicked()
    signal seekRequested(real value)
    signal settingsClicked()
    signal skipBackClicked()
    signal skipForwardClicked()
    signal speedChanged(real speed)

    function formatTime(seconds) {
        if (!seconds || seconds <= 0)
            return "0:00"
        const total = Math.floor(seconds)
        const m = Math.floor(total / 60)
        const s = total % 60
        const h = Math.floor(m / 60)
        const mins = m % 60
        if (h > 0)
            return h + ":" + (mins < 10 ? "0" : "") + mins + ":" + (s < 10 ? "0" : "") + s
        return m + ":" + (s < 10 ? "0" : "") + s
    }

    readonly property string loopIcon: loopMode === 2 ? "repeat_one" : "repeat"
    readonly property bool loopActive: loopMode > 0

    readonly property string volumeIcon: {
        if (muted)
            return "volume_off"
        if (volumeLevel === 0)
            return "volume_off"
        if (volumeLevel < 40)
            return "volume_down"
        return "volume_up"
    }

    ColumnLayout {
        anchors.fill: parent
        anchors.leftMargin: 20
        anchors.rightMargin: 20
        anchors.topMargin: 6
        anchors.bottomMargin: 8
        spacing: 4

        // ── Row 1: Thumbnail · Controls · Volume ─────────────────────────
        Item {
            Layout.fillWidth: true
            Layout.preferredHeight: 52

            // Left: thumbnail + track info
            RowLayout {
                anchors.left: parent.left
                anchors.top: parent.top
                anchors.bottom: parent.bottom
                width: Math.min(260, parent.width * 0.35)
                clip: true
                spacing: 12

                Item {
                    width: Theme.thumbSize
                    height: Theme.thumbSize

                    Rectangle {
                        anchors.fill: parent
                        radius: 10
                        clip: true
                        color: Theme.cardBg
                        border.color: Theme.cardBorder
                        border.width: 1
                        visible: root.trackThumbnail !== ""

                        Image {
                            anchors.fill: parent
                            source: root.resolvedThumbnail
                            fillMode: Image.PreserveAspectCrop
                            smooth: true
                            antialiasing: true
                            mipmap: true
                        }
                    }

                    AppLogo {
                        anchors.fill: parent
                        logoSize: Theme.thumbSize
                        cornerRadius: 10
                        visible: root.trackThumbnail === ""
                    }
                }

                ColumnLayout {
                    spacing: 2
                    Layout.fillWidth: true

                    Text {
                        text: root.trackTitle
                        font.family: Theme.fontFamily
                        font.pixelSize: 14
                        font.weight: Font.Bold
                        color: Theme.textPrimary
                        elide: Text.ElideRight
                        Layout.fillWidth: true
                    }

                    Text {
                        text: root.trackArtist
                        font.family: Theme.fontFamily
                        font.pixelSize: Theme.captionSize
                        color: Theme.textMuted
                        elide: Text.ElideRight
                        Layout.fillWidth: true
                    }
                }
            }

            // Centre: playback controls
            RowLayout {
                anchors.centerIn: parent
                height: parent.height
                spacing: 8

                IconButton {
                    icon: "shuffle"
                    iconSize: 22
                    width: 32
                    height: 32
                    active: root.shuffleOn
                    opacity: root.hasMedia ? 1 : 0.45
                    enabled: root.hasMedia
                    visible: !root.isPodcast
                    onClicked: root.shuffleClicked()
                }

                // Podcast: skip back -15s
                Rectangle {
                    width: Theme.controlButtonSize
                    height: Theme.controlButtonSize
                    radius: 8
                    color: "transparent"
                    visible: root.isPodcast
                    opacity: root.hasMedia ? 1 : 0.45

                    AppIcon {
                        anchors.centerIn: parent
                        name: "replay_10"
                        font.pixelSize: 28
                        color: Theme.textPrimary
                    }

                    Text {
                        anchors.bottom: parent.bottom
                        anchors.bottomMargin: -2
                        anchors.horizontalCenter: parent.horizontalCenter
                        text: "15"
                        font.family: Theme.fontFamily
                        font.pixelSize: 8
                        font.weight: Font.Bold
                        color: Theme.textPrimary
                    }

                    MouseArea {
                        anchors.fill: parent
                        cursorShape: Qt.PointingHandCursor
                        enabled: root.hasMedia
                        onClicked: root.skipBackClicked()
                    }
                }

                IconButton {
                    icon: "skip_previous"
                    iconSize: 28
                    width: Theme.controlButtonSize
                    height: Theme.controlButtonSize
                    opacity: root.hasMedia ? 1 : 0.45
                    enabled: root.hasMedia
                    onClicked: root.previousClicked()
                }

                Rectangle {
                    width: Theme.playButtonSize
                    height: Theme.playButtonSize
                    radius: width / 2
                    color: Theme.accent
                    opacity: root.hasMedia ? 1 : 0.55

                    AppIcon {
                        anchors.centerIn: parent
                        name: root.isPlaying ? "pause" : "play_arrow"
                        filled: true
                        font.pixelSize: 28
                        color: "#000000"
                    }

                    MouseArea {
                        anchors.fill: parent
                        cursorShape: Qt.PointingHandCursor
                        enabled: root.hasMedia
                        onClicked: root.playClicked()
                    }
                }

                IconButton {
                    icon: "skip_next"
                    iconSize: 28
                    width: Theme.controlButtonSize
                    height: Theme.controlButtonSize
                    opacity: root.hasMedia ? 1 : 0.45
                    enabled: root.hasMedia
                    onClicked: root.nextClicked()
                }

                // Podcast: skip forward +30s
                Rectangle {
                    width: Theme.controlButtonSize
                    height: Theme.controlButtonSize
                    radius: 8
                    color: "transparent"
                    visible: root.isPodcast
                    opacity: root.hasMedia ? 1 : 0.45

                    AppIcon {
                        anchors.centerIn: parent
                        name: "forward_30"
                        font.pixelSize: 28
                        color: Theme.textPrimary
                    }

                    Text {
                        anchors.bottom: parent.bottom
                        anchors.bottomMargin: -2
                        anchors.horizontalCenter: parent.horizontalCenter
                        text: "30"
                        font.family: Theme.fontFamily
                        font.pixelSize: 8
                        font.weight: Font.Bold
                        color: Theme.textPrimary
                    }

                    MouseArea {
                        anchors.fill: parent
                        cursorShape: Qt.PointingHandCursor
                        enabled: root.hasMedia
                        onClicked: root.skipForwardClicked()
                    }
                }

                IconButton {
                    icon: root.loopIcon
                    iconSize: 22
                    width: 32
                    height: 32
                    active: root.loopActive
                    opacity: root.hasMedia ? 1 : 0.45
                    enabled: root.hasMedia
                    visible: !root.isPodcast
                    onClicked: root.loopClicked()
                }

                // Podcast: playback speed
                Rectangle {
                    width: 40
                    height: 28
                    radius: 6
                    color: speedMouse.containsMouse ? Theme.bgHighlight : Theme.inputBg
                    visible: root.isPodcast
                    opacity: root.hasMedia ? 1 : 0.45

                    Text {
                        anchors.centerIn: parent
                        text: root.playbackSpeed.toFixed(2).replace(/0+$/, "").replace(/\.$/, "") + "x"
                        font.family: Theme.fontFamily
                        font.pixelSize: 12
                        font.weight: Font.Bold
                        color: Theme.accent
                    }

                    MouseArea {
                        id: speedMouse
                        anchors.fill: parent
                        hoverEnabled: true
                        cursorShape: Qt.PointingHandCursor
                        enabled: root.hasMedia
                        onClicked: {
                            var speeds = [1.0, 1.25, 1.5, 2.0, 0.75]
                            var idx = speeds.indexOf(root.playbackSpeed)
                            var next = speeds[(idx + 1) % speeds.length]
                            root.speedChanged(next)
                        }
                    }
                }
            }

            // Right: volume
            RowLayout {
                anchors.right: parent.right
                anchors.top: parent.top
                anchors.bottom: parent.bottom
                width: 190
                spacing: 6

                IconButton {
                    icon: root.volumeIcon
                    iconSize: 20
                    width: 32
                    height: 32
                    active: root.muted
                    onClicked: root.muteClicked()
                }

                Slider {
                    id: volSlider
                    Layout.fillWidth: true
                    Layout.preferredHeight: 28
                    from: 0
                    to: 100
                    stepSize: 1
                    live: true
                    padding: 10

                    onPressedChanged: root.volumeAdjusting = pressed
                    onMoved: root.volumeAdjusted(value)

                    background: Rectangle {
                        x: volSlider.leftPadding
                        y: volSlider.topPadding + volSlider.availableHeight / 2 - 2
                        width: volSlider.availableWidth
                        height: 4
                        radius: 2
                        color: Theme.border

                        Rectangle {
                            width: volSlider.visualPosition * parent.width
                            height: parent.height
                            radius: 2
                            color: Theme.accent
                        }
                    }

                    handle: Rectangle {
                        x: volSlider.leftPadding + volSlider.visualPosition * (volSlider.availableWidth - width)
                        y: volSlider.topPadding + volSlider.availableHeight / 2 - height / 2
                        width: 12
                        height: 12
                        radius: 6
                        color: "#ffffff"
                    }
                }

                IconButton {
                    icon: "settings"
                    iconSize: 20
                    width: 32
                    height: 32
                    onClicked: root.settingsClicked()
                }
            }
        }

        // ── Row 2: Time · Progress slider · Duration ──────────────────────
        RowLayout {
            Layout.fillWidth: true
            Layout.preferredHeight: 26
            spacing: 8

            Text {
                text: root.formatTime(root.position)
                font.family: Theme.fontFamily
                font.pixelSize: Theme.captionSize
                color: Theme.textMuted
                Layout.preferredWidth: 38
                horizontalAlignment: Text.AlignRight
            }

            Slider {
                id: progressSlider
                Layout.fillWidth: true
                Layout.preferredHeight: 26
                visible: true
                from: 0
                to: root.duration > 0 ? root.duration : 1
                enabled: root.hasMedia && root.duration > 0
                opacity: enabled ? 1 : 0.45
                live: true
                padding: 8

                onPressedChanged: {
                    root.seeking = pressed
                    if (!pressed)
                        root.seekRequested(value)
                }

                HoverHandler {
                    id: progressHover
                }

                background: Rectangle {
                    id: trackBg
                    x: progressSlider.leftPadding
                    y: progressSlider.topPadding + progressSlider.availableHeight / 2 - 2
                    width: progressSlider.availableWidth
                    height: 4
                    radius: 2
                    color: Theme.border

                    Behavior on height {
                        NumberAnimation { duration: 150; easing.type: Easing.OutQuad }
                    }

                    Rectangle {
                        id: fillBar
                        width: progressSlider.visualPosition * parent.width
                        height: parent.height
                        radius: 2
                        color: progressHover.hovered ? Theme.accentCyan : Theme.accent

                        Behavior on width {
                            SmoothedAnimation {
                                velocity: 180
                                duration: 120
                            }
                        }
                        Behavior on color {
                            ColorAnimation { duration: 200 }
                        }
                    }
                }

                handle: Rectangle {
                    x: progressSlider.leftPadding + progressSlider.visualPosition * (progressSlider.availableWidth - width)
                    y: progressSlider.topPadding + progressSlider.availableHeight / 2 - height / 2
                    width: 10
                    height: 10
                    radius: 5
                    color: Theme.textPrimary
                    opacity: progressSlider.enabled && progressHover.hovered ? 1 : 0

                    Behavior on opacity {
                        NumberAnimation { duration: 120; easing.type: Easing.OutQuad }
                    }
                }
            }

            Text {
                text: root.formatTime(root.duration)
                font.family: Theme.fontFamily
                font.pixelSize: Theme.captionSize
                color: Theme.textMuted
                Layout.preferredWidth: 38
            }
        }
    }

    onVolumeLevelChanged: {
        if (!volumeAdjusting && volSlider.value !== volumeLevel)
            volSlider.value = volumeLevel
    }

    onPositionChanged: {
        if (!seeking && progressSlider.value !== position)
            progressSlider.value = position
    }

    onDurationChanged: {
        progressSlider.to = duration > 0 ? duration : 1
    }

    Component.onCompleted: {
        progressSlider.value = position
        volSlider.value = volumeLevel
    }
}
