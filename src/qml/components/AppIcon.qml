import QtQuick
import Liminal 1.0

Text {
    id: root

    property string name: ""
    property bool filled: false

    text: name
    width: Math.ceil(font.pixelSize * 1.25)
    height: width
    color: Theme.textSecondary
    horizontalAlignment: Text.AlignHCenter
    verticalAlignment: Text.AlignVCenter
    wrapMode: Text.NoWrap
    maximumLineCount: 1

    font.family: iconFont.name
    font.pixelSize: 20
    font.variableAxes: ({ "FILL": filled ? 1 : 0, "wght": 400, "GRAD": 0, "opsz": 24 })

    FontLoader {
        id: iconFont
        source: Qt.resolvedUrl("../assets/fonts/MaterialSymbolsOutlined.ttf")
    }
}
