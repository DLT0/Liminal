import QtQuick
import Liminal 1.0

Rectangle {
    id: root

    property bool strong: false

    radius: 0
    color: strong ? Theme.glassStrong : Theme.glassFill
    border.color: strong ? Theme.glassStrongBorder : Theme.glassBorder
    border.width: 1
}
