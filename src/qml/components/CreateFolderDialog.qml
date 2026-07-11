import QtQuick
import QtQuick.Controls
import Liminal 1.0

Dialog {
    id: root

    title: "Tạo thư mục mới"
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

    onAccepted: backend.createFolder(nameField.text)

    function openDialog() {
        nameField.text = "Thư mục mới"
        open()
    }

    contentItem: Column {
        spacing: 12
        width: 320

        Text {
            width: parent.width
            text: "Tên thư mục"
            font.family: Theme.fontFamily
            font.pixelSize: Theme.captionSize
            font.weight: Font.DemiBold
            color: Theme.textSecondary
        }

        TextField {
            id: nameField
            width: parent.width
            placeholderText: "Nhập tên thư mục"
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
