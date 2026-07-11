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
    property bool isPlaying: false
    property bool hasMedia: false
    property int volumeLevel: 100
    property bool muted: false
    property real position: 0
    property real duration: 0
    property bool shuffleOn: false
    property bool loopOn: false

    property bool seeking: false
    property bool volumeAdjusting: false

    signal previousClicked()
    signal playClicked()
    signal nextClicked()
    signal shuffleClicked()
    signal loopClicked()
    signal volumeAdjusted(real value)
    signal muteClicked()
    signal seekRequested(real value)
    signal settingsClicked()

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

    readonly property string volumeIcon: {
        if (muted || volumeLevel === 0)
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

        Item {
            Layout.fillWidth: true
            Layout.preferredHeight: 52

            RowLayout {
                anchors.left: parent.left
                anchors.top: parent.top
                anchors.bottom: parent.bottom
                width: Math.min(260, parent.width * 0.35)
                clip: true
                spacing: 12

                AppLogo {
                    logoSize: Theme.thumbSize
                    cornerRadius: 10
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
                    onClicked: root.shuffleClicked()
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
                    border.color: Theme.playBorder
                    border.width: 1
                    opacity: root.hasMedia ? 1 : 0.55

                    gradient: Gradient {
                        GradientStop { position: 0; color: Theme.accentStart }
                        GradientStop { position: 1; color: Theme.accentEnd }
                    }

                    AppIcon {
                        anchors.centerIn: parent
                        name: root.isPlaying ? "pause" : "play_arrow"
                        filled: true
                        font.pixelSize: 28
                        color: Theme.textOnAccent
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

                IconButton {
                    icon: root.loopOn ? "repeat_one" : "repeat"
                    iconSize: 22
                    width: 32
                    height: 32
                    active: root.loopOn
                    opacity: root.hasMedia ? 1 : 0.45
                    enabled: root.hasMedia
                    onClicked: root.loopClicked()
                }
            }

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

                    onValueChanged: {
                        if (pressed)
                            root.volumeAdjusted(value)
                    }

                    background: Rectangle {
                        x: volSlider.leftPadding
                        y: volSlider.topPadding + volSlider.availableHeight / 2 - 2
                        width: volSlider.availableWidth
                        height: 4
                        radius: 2
                        color: Theme.sliderTrack

                        Rectangle {
                            width: volSlider.visualPosition * parent.width
                            height: parent.height
                            radius: 2
                            gradient: Gradient {
                                orientation: Gradient.Horizontal
                                GradientStop { position: 0; color: Theme.accentStart }
                                GradientStop { position: 1; color: Theme.accentCyan }
                            }
                        }
                    }

                    handle: Rectangle {
                        x: volSlider.leftPadding + volSlider.visualPosition * (volSlider.availableWidth - width)
                        y: volSlider.topPadding + volSlider.availableHeight / 2 - height / 2
                        width: 12
                        height: 12
                        radius: 6
                        color: Theme.accentStart
                        border.color: Theme.textPrimary
                        border.width: 2
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

        RowLayout {
            Layout.fillWidth: true
            Layout.preferredHeight: 28
            spacing: 10

            Text {
                text: root.formatTime(root.position)
                font.family: Theme.fontFamily
                font.pixelSize: Theme.captionSize
                color: Theme.textMuted
                Layout.preferredWidth: 42
                horizontalAlignment: Text.AlignRight
            }

            Slider {
                id: progressSlider
                Layout.fillWidth: true
                Layout.preferredHeight: 28
                from: 0
                to: root.duration > 0 ? root.duration : 1
                enabled: root.hasMedia && root.duration > 0
                opacity: enabled ? 1 : 0.45
                live: true
                padding: 10

                onPressedChanged: {
                    root.seeking = pressed
                    if (!pressed)
                        root.seekRequested(value)
                }

                background: Rectangle {
                    x: progressSlider.leftPadding
                    y: progressSlider.topPadding + progressSlider.availableHeight / 2 - 2
                    width: progressSlider.availableWidth
                    height: 4
                    radius: 2
                    color: Theme.sliderTrack

                    Rectangle {
                        width: progressSlider.visualPosition * parent.width
                        height: parent.height
                        radius: 2
                        color: Theme.accentStart
                    }
                }

                handle: Rectangle {
                    x: progressSlider.leftPadding + progressSlider.visualPosition * (progressSlider.availableWidth - width)
                    y: progressSlider.topPadding + progressSlider.availableHeight / 2 - height / 2
                    width: 10
                    height: 10
                    radius: 5
                    color: Theme.textPrimary
                    visible: progressSlider.enabled
                }
            }

            Text {
                text: root.formatTime(root.duration)
                font.family: Theme.fontFamily
                font.pixelSize: Theme.captionSize
                color: Theme.textMuted
                Layout.preferredWidth: 42
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
