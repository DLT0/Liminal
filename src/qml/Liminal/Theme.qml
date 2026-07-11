pragma Singleton
import QtQuick

QtObject {
    // ── Active theme index (0=DeepSlate, 1=Midnight, 2=WarmCharcoal) ──
    property int themeIndex: 0

    readonly property var palettes: [
        // 0 — Deep Slate + Indigo (default)
        {
            bgTop:            "#12141C",
            bgMid:            "#181B24",
            bgBottom:         "#12141C",
            shimmerRight:     "#156C5CE7",
            shimmerLeft:      "#0E6C5CE7",
            glassFill:        "#181B24",
            glassBorder:      "#2A2E3A",
            glassStrong:      "#20242F",
            glassStrongBorder:"#2A2E3A",
            accentStart:      "#6C5CE7",
            accentEnd:        "#00CEC9",
            accentCyan:       "#00CEC9",
            textPrimary:      "#F1F2F6",
            textSecondary:    "#8A8F9C",
            textMuted:        "#5A5F6C",
            textOnAccent:     "#FFFFFF",
            cardBg:           "#20242F",
            cardBorder:       "#2A2E3A",
            inputBg:          "#20242F",
            inputBorder:      "#2A2E3A",
            sliderTrack:      "#2A2E3A",
            hoverOverlay:     "#156C5CE7",
            playBorder:       "#406C5CE7",
        },
        // 1 — Midnight Blue
        {
            bgTop:            "#0D1117",
            bgMid:            "#161B22",
            bgBottom:         "#0D1117",
            shimmerRight:     "#1258A6FF",
            shimmerLeft:      "#0E3FB950",
            glassFill:        "#161B22",
            glassBorder:      "#21262D",
            glassStrong:      "#1C2128",
            glassStrongBorder:"#2D333B",
            accentStart:      "#58A6FF",
            accentEnd:        "#3FB950",
            accentCyan:       "#3FB950",
            textPrimary:      "#E6EDF3",
            textSecondary:    "#7D8590",
            textMuted:        "#484F58",
            textOnAccent:     "#0D1117",
            cardBg:           "#1C2128",
            cardBorder:       "#21262D",
            inputBg:          "#1C2128",
            inputBorder:      "#21262D",
            sliderTrack:      "#21262D",
            hoverOverlay:     "#1558A6FF",
            playBorder:       "#4058A6FF",
        },
        // 2 — Warm Charcoal + Amber
        {
            bgTop:            "#1A1A1E",
            bgMid:            "#232327",
            bgBottom:         "#1A1A1E",
            shimmerRight:     "#18F5A623",
            shimmerLeft:      "#12FF7A59",
            glassFill:        "#232327",
            glassBorder:      "#333338",
            glassStrong:      "#2A2A2E",
            glassStrongBorder:"#3D3D42",
            accentStart:      "#F5A623",
            accentEnd:        "#FF7A59",
            accentCyan:       "#FF7A59",
            textPrimary:      "#EDEDED",
            textSecondary:    "#9A9A9E",
            textMuted:        "#666669",
            textOnAccent:     "#1A1A1E",
            cardBg:           "#2A2A2E",
            cardBorder:       "#3D3D42",
            inputBg:          "#2A2A2E",
            inputBorder:      "#3D3D42",
            sliderTrack:      "#333338",
            hoverOverlay:     "#15F5A623",
            playBorder:       "#40F5A623",
        }
    ]

    readonly property var p: palettes[themeIndex]

    // ── Background ──
    readonly property color bgTop:    p.bgTop
    readonly property color bgMid:    p.bgMid
    readonly property color bgBottom: p.bgBottom
    readonly property color shimmerRight: p.shimmerRight
    readonly property color shimmerLeft:  p.shimmerLeft

    // ── Accent ──
    readonly property color accentStart: p.accentStart
    readonly property color accentEnd:   p.accentEnd
    readonly property color accentCyan:  p.accentCyan

    // ── Glass/Panel surfaces ──
    readonly property color glassFill:         p.glassFill
    readonly property color glassBorder:       p.glassBorder
    readonly property color glassStrong:       p.glassStrong
    readonly property color glassStrongBorder: p.glassStrongBorder

    // ── Text ──
    readonly property color textPrimary:   p.textPrimary
    readonly property color textSecondary: p.textSecondary
    readonly property color textMuted:     p.textMuted
    readonly property color textOnAccent:  p.textOnAccent

    // ── Component-specific tokens ──
    readonly property color cardBg:       p.cardBg
    readonly property color cardBorder:   p.cardBorder
    readonly property color inputBg:      p.inputBg
    readonly property color inputBorder:  p.inputBorder
    readonly property color sliderTrack:  p.sliderTrack
    readonly property color hoverOverlay: p.hoverOverlay
    readonly property color playBorder:   p.playBorder

    // ── Traffic lights (static) ──
    readonly property color trafficRed:    "#ef4444"
    readonly property color trafficYellow: "#eab308"
    readonly property color trafficGreen:  "#22c55e"

    // ── Layout sizes ──
    readonly property int titleBarHeight:  40
    readonly property int sidebarWidth:    220
    readonly property int playerBarHeight: 96
    readonly property int contentPadding:  24
    readonly property int gridColumns:     5
    readonly property int cardRadius:      12
    readonly property int cardGap:         20

    // ── Typography ──
    readonly property string fontFamily: "Inter, Segoe UI, Noto Sans, sans-serif"
    readonly property int pageTitleSize: 28
    readonly property int bodySize:      13
    readonly property int captionSize:   11

    // ── Animation ──
    readonly property int  hoverDuration: 180
    readonly property int  colorDuration: 200
    readonly property real hoverScale:    1.04

    // ── Controls ──
    readonly property int playButtonSize:    48
    readonly property int controlButtonSize: 36
    readonly property int iconButtonSize:    36
    readonly property int thumbSize:         44

    // ── Theme names (for UI display) ──
    readonly property var themeNames: ["Deep Slate", "Midnight Blue", "Warm Charcoal"]
}
