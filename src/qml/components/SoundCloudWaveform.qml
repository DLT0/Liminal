import QtQuick
import Liminal 1.0

Item {
    id: root

    property var waveform: []       // array of 150 floats [0.0 - 1.0]
    property real position: 0       // current time in seconds
    property real duration: 0       // total duration in seconds
    property bool isPlaying: false
    property bool hasMedia: false

    signal seekRequested(real position)

    readonly property real progress: duration > 0 ? (position / duration) : 0

    // Visual styling
    property color activeColor: Theme.accentStart
    property color inactiveColor: Theme.sliderTrack
    property color hoverColor: Theme.accentCyan
    property real barWidth: 3
    property real barGap: 2

    // Hover track position (0.0 to 1.0)
    property real hoverProgress: -1

    onWaveformChanged: canvas.requestPaint()
    onProgressChanged: canvas.requestPaint()
    onHoverProgressChanged: canvas.requestPaint()

    Canvas {
        id: canvas
        anchors.fill: parent
        antialiasing: true

        onPaint: {
            var ctx = getContext("2d")
            ctx.clearRect(0, 0, width, height)

            // Fallback: draw a clean horizontal timeline if no waveform or media is loaded
            if (!root.hasMedia || !root.waveform || root.waveform.length === 0) {
                ctx.strokeStyle = root.inactiveColor
                ctx.lineWidth = 2
                ctx.beginPath()
                ctx.moveTo(0, height / 2)
                ctx.lineTo(width, height / 2)
                ctx.stroke()
                return
            }

            var n_bars = root.waveform.length
            var totalBarWidth = root.barWidth + root.barGap

            // Scale to fit the component width perfectly
            var scaleX = width / (n_bars * totalBarWidth - root.barGap)
            var actualBarW = Math.max(1.0, root.barWidth * scaleX)
            var actualGap = Math.max(0.5, root.barGap * scaleX)

            var progressLimitIdx = Math.floor(root.progress * n_bars)
            var hoverLimitIdx = root.hoverProgress >= 0 ? Math.floor(root.hoverProgress * n_bars) : -1

            ctx.lineWidth = actualBarW
            ctx.lineCap = "round"

            for (var i = 0; i < n_bars; i++) {
                var val = root.waveform[i]
                
                // Height of each bar is bounded to at least 4px for visibility
                var barH = Math.max(4.0, val * height)
                var y = (height - barH) / 2
                var x = i * (actualBarW + actualGap) + (actualBarW / 2)

                // Select styling color
                var color = root.inactiveColor
                if (hoverLimitIdx >= 0) {
                    if (i <= hoverLimitIdx) {
                        color = root.hoverColor
                    } else if (i <= progressLimitIdx) {
                        // Dims the played portion beyond the current hover point
                        color = Qt.rgba(root.activeColor.r, root.activeColor.g, root.activeColor.b, 0.40)
                    }
                } else if (i <= progressLimitIdx) {
                    color = root.activeColor
                }

                ctx.strokeStyle = color
                ctx.beginPath()
                
                // Guard against start/end overlaps when bar height is too small
                var startY = y + (actualBarW / 2)
                var endY = y + barH - (actualBarW / 2)
                if (startY >= endY) {
                    startY = y
                    endY = y + barH
                }
                
                ctx.moveTo(x, startY)
                ctx.lineTo(x, endY)
                ctx.stroke()
            }
        }
    }

    MouseArea {
        id: clickArea
        anchors.fill: parent
        hoverEnabled: true
        cursorShape: Qt.PointingHandCursor

        onPositionChanged: function(mouse) {
            root.hoverProgress = Math.max(0.0, Math.min(1.0, mouse.x / width))
        }

        onExited: {
            root.hoverProgress = -1
        }

        onClicked: function(mouse) {
            var frac = Math.max(0.0, Math.min(1.0, mouse.x / width))
            if (root.duration > 0) {
                root.seekRequested(frac * root.duration)
            }
        }
    }
}
