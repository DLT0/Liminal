import QtQuick
import Liminal 1.0

Rectangle {
    id: root

    property string path: ""
    property string placeholder: ""

    implicitHeight: 40
    radius: 8
    color: Theme.inputBg
    border.color: Theme.settingsCardBorder
    border.width: 1

    Text {
        anchors.fill: parent
        anchors.margins: 10
        text: root.path || root.placeholder
        font.family: root.path ? Theme.monoFontFamily : Theme.fontFamily
        font.pixelSize: root.path ? 12 : Theme.bodySize
        color: root.path ? Theme.textSecondary : Theme.textMuted
        elide: Text.ElideMiddle
        verticalAlignment: Text.AlignVCenter
    }
}
