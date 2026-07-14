import QtQuick
import QtQuick.Layouts
import Liminal 1.0

Item {
    id: root

    property string iconName: "settings"
    property string title: ""
    property string subtitle: ""
    default property alias content: bodyLayout.data

    implicitWidth: 320
    implicitHeight: card.implicitHeight

    Rectangle {
        id: shadow
        anchors.fill: card
        anchors.topMargin: 2
        z: -1
        radius: card.radius
        color: Theme.settingsShadow
        opacity: 0.35
    }

    Rectangle {
        id: card
        width: parent.width
        implicitHeight: innerColumn.implicitHeight + 40
        radius: Theme.cardRadius
        color: Theme.settingsCardBg
        border.color: Theme.settingsCardBorder
        border.width: 1

        ColumnLayout {
            id: innerColumn
            anchors.left: parent.left
            anchors.right: parent.right
            anchors.top: parent.top
            anchors.margins: 20
            spacing: 18

            RowLayout {
                Layout.fillWidth: true
                spacing: 14

                Rectangle {
                    Layout.preferredWidth: 32
                    Layout.preferredHeight: 32
                    radius: 16
                    color: Theme.settingsIconBg

                    AppIcon {
                        anchors.centerIn: parent
                        name: root.iconName
                        color: Theme.textSecondary
                        font.pixelSize: 18
                    }
                }

                ColumnLayout {
                    Layout.fillWidth: true
                    Layout.minimumWidth: 0
                    spacing: 4

                    Text {
                        Layout.fillWidth: true
                        text: root.title
                        font.family: Theme.fontFamily
                        font.pixelSize: Theme.bodySize + 1
                        font.weight: Font.Medium
                        color: Theme.textPrimary
                        wrapMode: Text.WordWrap
                    }

                    Text {
                        Layout.fillWidth: true
                        visible: root.subtitle !== ""
                        text: root.subtitle
                        font.family: Theme.fontFamily
                        font.pixelSize: Theme.settingsSubtitleSize
                        color: Theme.textSecondary
                        wrapMode: Text.WordWrap
                    }
                }
            }

            ColumnLayout {
                id: bodyLayout
                Layout.fillWidth: true
                spacing: 12
            }
        }
    }
}
