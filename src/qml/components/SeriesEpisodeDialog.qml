import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import Liminal 1.0

Dialog {
    id: root

    property string itemPath: ""

    title: "Chỉnh mùa / tập"
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
        backend.editSeriesEpisodeMetadata(
            itemPath,
            titleField.text,
            seasonField.value,
            episodeField.value
        )
    }

    function openFor(path, title, season, episode) {
        itemPath = path
        titleField.text = title
        seasonField.value = season || 1
        episodeField.value = episode || 1
        open()
    }

    contentItem: ColumnLayout {
        spacing: 12

        Text {
            Layout.fillWidth: true
            text: "Tên tập"
            font.family: Theme.fontFamily
            font.pixelSize: Theme.captionSize
            font.weight: Font.DemiBold
            color: Theme.textSecondary
        }

        TextField {
            id: titleField
            Layout.fillWidth: true
            font.family: Theme.fontFamily
            color: Theme.textPrimary
            placeholderTextColor: Theme.textMuted
            background: Rectangle {
                radius: 8
                color: Theme.inputBg
                border.color: Theme.inputBorder
            }
        }

        RowLayout {
            Layout.fillWidth: true
            spacing: 12

            ColumnLayout {
                Layout.fillWidth: true
                spacing: 6

                Text {
                    text: "Mùa"
                    font.family: Theme.fontFamily
                    font.pixelSize: Theme.captionSize
                    font.weight: Font.DemiBold
                    color: Theme.textSecondary
                }

                SpinBox {
                    id: seasonField
                    Layout.fillWidth: true
                    from: 1
                    to: 99
                }
            }

            ColumnLayout {
                Layout.fillWidth: true
                spacing: 6

                Text {
                    text: "Tập"
                    font.family: Theme.fontFamily
                    font.pixelSize: Theme.captionSize
                    font.weight: Font.DemiBold
                    color: Theme.textSecondary
                }

                SpinBox {
                    id: episodeField
                    Layout.fillWidth: true
                    from: 1
                    to: 999
                }
            }
        }
    }
}
