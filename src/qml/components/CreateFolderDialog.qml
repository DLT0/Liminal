import QtQuick
import QtQuick.Controls
import Liminal 1.0

Dialog {
    id: root

    property bool isVideo: false

    title: isVideo ? "Tạo phim bộ mới" : "Tạo playlist mới"
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

    signal folderCreated()

    onAccepted: {
        backend.createFolder(nameField.text)
        folderCreated()
    }

    function openDialog(isVideoContext) {
        isVideo = isVideoContext || false
        nameField.text = isVideo ? "Phim bộ mới" : "Playlist mới"
        open()
    }

    contentItem: Column {
        spacing: 12
        width: 320

        Text {
            width: parent.width
            text: root.isVideo ? "Tên thư mục" : "Tên playlist"
            font.family: Theme.fontFamily
            font.pixelSize: Theme.captionSize
            font.weight: Font.DemiBold
            color: Theme.textSecondary
        }

        TextField {
            id: nameField
            width: parent.width
            placeholderText: root.isVideo ? "Nhập tên thư mục" : "Nhập tên playlist"
            font.family: Theme.fontFamily
            color: Theme.textPrimary
            placeholderTextColor: Theme.textMuted
            background: Rectangle {
                radius: 8
                color: Theme.inputBg
                border.color: Theme.inputBorder
            }
            Keys.onReturnPressed: root.accept()
        }
    }
}
