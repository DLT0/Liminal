import QtQuick
import Liminal 1.0

Text {
    id: root

    property string name: ""
    property bool filled: false

    text: name
    color: Theme.textSecondary
    horizontalAlignment: Text.AlignHCenter
    verticalAlignment: Text.AlignVCenter

    font.family: iconFont.name
    font.pixelSize: 20
    font.variableAxes: ({ "FILL": filled ? 1 : 0, "wght": 400, "GRAD": 0, "opsz": 24 })

    FontLoader {
        id: iconFont
        source: Qt.resolvedUrl("../assets/fonts/MaterialSymbolsOutlined.ttf")
    }
}
