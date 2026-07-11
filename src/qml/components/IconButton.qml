import QtQuick
import QtQuick.Controls
import Liminal 1.0

Rectangle {
    id: root

    property string icon: ""
    property bool filled: false
    property bool active: false
    property int iconSize: 20
    property color iconColor: active ? Theme.accentStart : Theme.textSecondary
    property color hoverColor: active ? Theme.hoverOverlay : Theme.hoverOverlay
    property string tooltipText: {
        var labels = {
            "arrow_back": "Quay lại", "shuffle": active ? "Tắt phát ngẫu nhiên" : "Phát ngẫu nhiên",
            "skip_previous": "Bài trước", "skip_next": "Bài tiếp theo",
            "repeat": "Bật phát lặp", "repeat_one": "Tắt phát lặp",
            "volume_up": "Tắt âm", "volume_down": "Tắt âm", "volume_mute": "Tắt âm",
            "volume_off": "Bật âm", "settings": "Cài đặt", "folder": "Chọn thư mục",
            "remove": "Thu nhỏ", "check_box_outline_blank": "Phóng to", "close": "Đóng"
        }
        return labels[icon] || ""
    }

    signal clicked()

    width: Theme.iconButtonSize
    height: Theme.iconButtonSize
    radius: width / 2
    color: mouse.containsMouse ? hoverColor : "transparent"
    border.color: bordered ? "#1affffff" : "transparent"
    border.width: bordered ? 1 : 0

    property bool bordered: false

    AppIcon {
        anchors.centerIn: parent
        name: root.icon
        filled: root.filled
        color: root.iconColor
        font.pixelSize: root.iconSize

        Behavior on color {
            ColorAnimation {
                duration: Theme.colorDuration
                easing.type: Easing.OutCubic
            }
        }
    }

    MouseArea {
        id: mouse
        anchors.fill: parent
        hoverEnabled: true
        cursorShape: Qt.PointingHandCursor
        onClicked: root.clicked()
    }

    AppToolTip {
        visible: root.enabled && root.tooltipText !== "" && mouse.containsMouse
        text: root.tooltipText
    }
}
