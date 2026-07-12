import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import Liminal 1.0

Dialog {
    id: root

    title: "Nhập mã chia sẻ"
    modal: true
    anchors.centerIn: parent
    standardButtons: Dialog.Ok | Dialog.Cancel
    padding: 20

    property alias codeField: codeField

    background: Rectangle {
        radius: 14
        color: Theme.glassStrong
        border.color: Theme.glassStrongBorder
        border.width: 1
    }

    onAboutToShow: {
        codeField.text = ""
        codeField.forceActiveFocus()
    }

    onAccepted: shareBridge.redeemCode(codeField.text)

    contentItem: ColumnLayout {
        spacing: 12

        Text {
            Layout.fillWidth: true
            text: "Nhập mã 6 ký tự mà bạn bè đã gửi."
            wrapMode: Text.Wrap
            font.family: Theme.fontFamily
            font.pixelSize: Theme.bodySize
            color: Theme.textSecondary
        }

        TextField {
            id: codeField
            Layout.fillWidth: true
            placeholderText: "VD: K7M2NP"
            font.family: Theme.fontFamily
            font.pixelSize: 20
            font.letterSpacing: 2
            horizontalAlignment: Text.AlignHCenter
            maximumLength: 8
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
