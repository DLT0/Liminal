import QtQuick
import Liminal 1.0

Item {
    id: root

    property string text: ""
    property int horizontalMargin: Theme.contentPadding

    // Width do parent/Layout quyết định — không tự gán parent.width (xung đột ColumnLayout)
    height: titleLabel.implicitHeight + 8
    z: 2

    Rectangle {
        anchors.fill: parent
        anchors.leftMargin: -horizontalMargin
        anchors.rightMargin: -horizontalMargin
        color: Theme.bgElevated
    }

    Text {
        id: titleLabel
        anchors.left: parent.left
        anchors.verticalCenter: parent.verticalCenter
        width: parent.width
        text: root.text
        font.family: Theme.fontFamily
        font.pixelSize: 24
        font.weight: Font.Bold
        color: Theme.textPrimary
        elide: Text.ElideRight
    }
}
