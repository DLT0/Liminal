import QtQuick
import QtQuick.Controls
import Liminal 1.0

// Category tab = filter theo thể loại (nhiều-nhiều)
// Playlist tab = collection cố định do collaborator tạo (1-1 với item)
// Các chip: "Tất cả" + fixed categories + "Playlists" (đặc biệt, ở cuối, có separator)
Item {
    id: root
    height: catRow.implicitHeight

    property var categories: []   // Fixed category từ server
    property string selectedId: "all"

    signal categorySelected(string categoryId)

    Row {
        id: catRow
        spacing: 8

        Repeater {
            model: {
                var list = [{ "id": "all", "label": "Tất cả" }]
                var cats = root.categories || []
                for (var i = 0; i < cats.length; i++)
                    list.push(cats[i])
                // Playlists ở cuối, phân cách bởi separator dọc
                list.push({ "id": "separator", "label": "", "isSeparator": true })
                list.push({ "id": "playlists", "label": "Playlists" })
                return list
            }

            delegate: Rectangle {
                // Separator dọc trước Playlists
                visible: !(modelData.isSeparator === true)
                readonly property bool isSep: modelData.isSeparator === true
                readonly property bool selected: String(modelData.id) === root.selectedId
                readonly property bool hovered: chipMa.containsMouse
                height: isSep ? chipLabel.implicitHeight + 12 : chipLabel.implicitHeight + 12
                width: isSep ? 1 : chipLabel.implicitWidth + 20
                radius: isSep ? 0 : (height / 2)
                color: isSep ? Theme.cardBorder : (selected ? Theme.accentStart : Theme.bgElevated)
                border.width: isSep || selected ? 0 : 1
                border.color: {
                    if (isSep || selected) return "transparent"
                    if (hovered) return Qt.rgba(1, 1, 1, 0.35)
                    return Theme.cardBorder
                }

                Behavior on border.color { ColorAnimation { duration: Theme.colorDuration } }
                Behavior on color { ColorAnimation { duration: Theme.colorDuration } }

                Text {
                    id: chipLabel
                    anchors.centerIn: parent
                    text: modelData.label
                    visible: !isSep
                    color: selected ? Theme.textOnAccent : (chipMa.containsMouse ? Theme.textPrimary : Theme.textSecondary)
                    font.family: Theme.fontFamily
                    font.pixelSize: Theme.captionSize
                    font.weight: selected ? Font.DemiBold : Font.Normal
                    Behavior on color { ColorAnimation { duration: Theme.colorDuration } }
                }

                MouseArea {
                    id: chipMa
                    anchors.fill: parent
                    hoverEnabled: !isSep
                    cursorShape: isSep ? Qt.ArrowCursor : Qt.PointingHandCursor
                    onClicked: {
                        if (!isSep) root.categorySelected(String(modelData.id))
                    }
                }
            }
        }
    }
}
