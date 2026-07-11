import QtQuick
import Liminal 1.0

Item {
    id: root

    property int logoSize: 36
    property int cornerRadius: 9
    property string source: backend.appIconUrl

    width: logoSize
    height: logoSize

    Rectangle {
        anchors.fill: parent
        radius: root.cornerRadius
        color: Theme.cardBg
        clip: true
        border.color: Theme.cardBorder
        border.width: 1

        Image {
            anchors.fill: parent
            source: root.source
            fillMode: Image.PreserveAspectFit
            smooth: true
            antialiasing: true
            mipmap: true
        }
    }
}
