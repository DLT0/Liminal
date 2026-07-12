import QtQuick
import QtQuick.Controls
import Liminal 1.0

Item {
    id: root

    property alias model: grid.model
    property int gridColumns: Theme.gridColumns
    property int horizontalContentMargin: Theme.contentPadding
    property int verticalContentMargin: 8
    property string emptyTitle: "Chưa có phim chia sẻ"
    property string emptyMessage: "Nhập mã chia sẻ từ bạn bè để xem tại đây."

    signal playRequested(int index)
    signal downloadRequested(int index)

    readonly property real cellWidth: Math.floor(
        (width - 2 * horizontalContentMargin - (gridColumns - 1) * Theme.cardGap) / gridColumns
    )
    readonly property real cellHeight: Math.ceil(cellWidth / Theme.videoPosterAspect + 82) + 8

    RedeemShareDialog {
        id: redeemDialog
        parent: Overlay.overlay
        onAccepted: shareBridge.redeemCode(codeField.text)
    }

    Connections {
        target: shareBridge
        function onShareError(message) {
            toast.text = message
            toast.open()
        }
        function onRedeemSuccess() {
            toast.text = "Đã thêm vào danh sách chia sẻ."
            toast.open()
        }
    }

    Popup {
        id: toast
        property string text: ""
        modal: false
        focus: false
        closePolicy: Popup.CloseOnEscape | Popup.CloseOnPressOutside
        anchors.centerIn: Overlay.overlay
        padding: 14
        background: Rectangle {
            radius: 10
            color: Theme.glassStrong
            border.color: Theme.glassStrongBorder
        }
        contentItem: Text {
            text: toast.text
            color: Theme.textPrimary
            font.family: Theme.fontFamily
            font.pixelSize: Theme.bodySize
        }
        Timer {
            id: toastTimer
            interval: 2800
            onTriggered: toast.close()
        }
        onOpened: toastTimer.restart()
    }

    Row {
        id: actionRow
        anchors.top: parent.top
        anchors.right: parent.right
        anchors.rightMargin: horizontalContentMargin
        anchors.topMargin: 4
        spacing: 8

        Rectangle {
            height: 32
            width: redeemLabel.implicitWidth + 24
            radius: 8
            color: redeemMouse.containsMouse ? Theme.hoverOverlay : Theme.inputBg
            border.color: Theme.inputBorder

            Row {
                id: redeemLabel
                anchors.centerIn: parent
                spacing: 6

                AppIcon {
                    anchors.verticalCenter: parent.verticalCenter
                    name: "redeem"
                    font.pixelSize: 16
                    color: Theme.textSecondary
                }

                Text {
                    text: "Nhập mã"
                    color: Theme.textPrimary
                    font.family: Theme.fontFamily
                    font.pixelSize: Theme.captionSize
                    font.weight: Font.DemiBold
                }
            }

            MouseArea {
                id: redeemMouse
                anchors.fill: parent
                hoverEnabled: true
                cursorShape: Qt.PointingHandCursor
                onClicked: redeemDialog.open()
            }
        }
    }

    GridView {
        id: grid
        anchors.top: actionRow.bottom
        anchors.topMargin: 8
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.bottom: parent.bottom
        anchors.leftMargin: horizontalContentMargin
        anchors.rightMargin: horizontalContentMargin
        anchors.bottomMargin: verticalContentMargin
        clip: true
        visible: count > 0
        interactive: false

        property int columns: root.gridColumns
        cellWidth: root.cellWidth
        cellHeight: root.cellHeight

        delegate: Item {
            width: grid.cellWidth - Theme.cardGap
            height: grid.cellHeight - 8

            SharedVideoCard {
                anchors.fill: parent
                title: model.title
                subtitle: model.subtitle
                imageSource: model.imageSource
                downloadPercent: model.downloadPercent
                downloadStatus: model.downloadStatus
                isDownloading: model.isDownloading
                onPlayRequested: root.playRequested(index)
                onDownloadRequested: root.downloadRequested(index)
            }
        }
    }

    Column {
        anchors.centerIn: parent
        spacing: 8
        visible: grid.count === 0
        width: parent.width - 2 * horizontalContentMargin

        Text {
            anchors.horizontalCenter: parent.horizontalCenter
            text: root.emptyTitle
            color: Theme.textPrimary
            font.family: Theme.fontFamily
            font.pixelSize: 18
            font.weight: Font.DemiBold
        }

        Text {
            anchors.horizontalCenter: parent.horizontalCenter
            width: parent.width
            horizontalAlignment: Text.AlignHCenter
            wrapMode: Text.Wrap
            text: root.emptyMessage
            color: Theme.textSecondary
            font.family: Theme.fontFamily
            font.pixelSize: Theme.bodySize
        }
    }
}
