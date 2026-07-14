pragma Singleton
import QtQuick

QtObject {
    // Colors and layout are driven by ~/.config/liminal/settings.json via `uiConfig`.

    readonly property color bgBase:      uiConfig.bgBase
    readonly property color bgElevated:  uiConfig.bgElevated
    readonly property color bgHighlight: uiConfig.bgHighlight
    readonly property color bgCard:      uiConfig.bgCard
    readonly property color bgCardHover: uiConfig.bgCardHover
    readonly property color accent:      uiConfig.accent
    readonly property color border:      uiConfig.border

    readonly property color bgTop:    bgElevated
    readonly property color bgMid:    bgElevated
    readonly property color bgBottom: bgElevated
    readonly property color shimmerRight: "transparent"
    readonly property color shimmerLeft:  "transparent"

    readonly property color accentStart: accent
    readonly property color accentEnd:   accent
    readonly property color accentCyan:  accent

    readonly property color glassFill:         uiConfig.glassFill
    readonly property color glassBorder:       uiConfig.glassBorder
    readonly property color glassStrong:       uiConfig.glassStrong
    readonly property color glassStrongBorder: border

    readonly property color textPrimary:   uiConfig.textPrimary
    readonly property color textSecondary: uiConfig.textSecondary
    readonly property color textMuted:     uiConfig.textMuted
    readonly property color textOnAccent:  uiConfig.textOnAccent

    readonly property color cardBg:       uiConfig.cardBg
    readonly property color cardBorder:   uiConfig.cardBorder
    readonly property color inputBg:      uiConfig.inputBg
    readonly property color inputBorder:  uiConfig.inputBorder
    readonly property color sliderTrack:  uiConfig.sliderTrack
    readonly property color hoverOverlay: uiConfig.hoverOverlay
    readonly property color playBorder:   "transparent"

    // Spotify-style pure black surfaces (settings & elevated UI)
    readonly property color settingsCardBg:     "#0a0a0a"
    readonly property color settingsCardBorder: Qt.rgba(1, 1, 1, 0.06)
    readonly property color settingsIconBg:     Qt.rgba(1, 1, 1, 0.08)
    readonly property color settingsShadow:     Qt.rgba(0, 0, 0, 0.5)

    readonly property color trafficRed:    "#ef4444"
    readonly property color trafficYellow: "#eab308"
    readonly property color trafficGreen:  "#22c55e"

    readonly property int titleBarHeight:  40
    readonly property int sidebarWidth:    uiConfig.sidebarWidth
    readonly property int playerBarHeight: uiConfig.playerBarHeight
    readonly property int contentPadding:  uiConfig.contentPadding
    readonly property int gridColumns:     uiConfig.gridColumns
    readonly property int cardRadius:      uiConfig.cardRadius
    readonly property int libraryCardRadius: 0
    readonly property int focusRingWidth:    2
    readonly property int focusListRadius:   10
    readonly property int cardGap:         uiConfig.cardGap
    readonly property real videoPosterAspect: 16 / 9

    readonly property string fontFamily: "Inter, Segoe UI, Noto Sans, sans-serif"
    readonly property string monoFontFamily: "JetBrains Mono, Fira Code, Consolas, monospace"
    readonly property int pageTitleSize: 28
    readonly property int bodySize:      13
    readonly property int captionSize:   11
    readonly property int settingsSubtitleSize: 12

    readonly property int  hoverDuration: 180
    readonly property int  colorDuration: 200
    readonly property real hoverScale:    1.04

    readonly property int playButtonSize:    48
    readonly property int controlButtonSize: 36
    readonly property int iconButtonSize:    36
    readonly property int thumbSize:         44
}
