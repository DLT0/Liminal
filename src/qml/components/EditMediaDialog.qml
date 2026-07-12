import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import Liminal 1.0

Dialog {
    id: root

    property string itemPath: ""
    property string initialTitle: ""
    property string initialArtist: ""

    title: "Chỉnh sửa thông tin"
    modal: true
    anchors.centerIn: parent
    standardButtons: Dialog.Ok | Dialog.Cancel
    padding: 20

    background: Rectangle {
        radius: 14
        color: Theme.glassStrong
        border.color: Theme.glassStrongBorder
        border.width: 1
    }

    onAccepted: {
        backend.editMediaMetadataByPath(itemPath, titleField.text, artistField.text)
    }

    function openFor(path, title, artist) {
        itemPath = path
        titleField.text = title
        artistField.text = artist
        open()
    }

    contentItem: ColumnLayout {
        spacing: 12

        Text {
            Layout.fillWidth: true
            text: "Tiêu đề"
            font.family: Theme.fontFamily
            font.pixelSize: Theme.captionSize
            font.weight: Font.DemiBold
            color: Theme.textSecondary
        }

        TextField {
            id: titleField
            Layout.fillWidth: true
            placeholderText: "Nhập tiêu đề cho mục này"
            font.family: Theme.fontFamily
            color: Theme.textPrimary
            placeholderTextColor: Theme.textMuted
            background: Rectangle {
                radius: 8
                color: Theme.inputBg
                border.color: Theme.inputBorder
            }
        }

        Text {
            Layout.fillWidth: true
            text: "Tác giả / nghệ sĩ"
            font.family: Theme.fontFamily
            font.pixelSize: Theme.captionSize
            font.weight: Font.DemiBold
            color: Theme.textSecondary
        }

        TextField {
            id: artistField
            Layout.fillWidth: true
            placeholderText: "Nhập tên tác giả hoặc nghệ sĩ"
            font.family: Theme.fontFamily
            color: Theme.textPrimary
            placeholderTextColor: Theme.textMuted
            background: Rectangle {
                radius: 8
                color: Theme.inputBg
                border.color: Theme.inputBorder
            }
        }
    }
}
