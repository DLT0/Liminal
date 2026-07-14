import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import Liminal 1.0

Item {
    id: root

    property string label: ""
    property string description: ""
    property bool checked: true
    property bool interactive: false

    signal toggled(bool checked)

    implicitHeight: row.implicitHeight

    RowLayout {
        id: row
        anchors.fill: parent
        spacing: 14

        ColumnLayout {
            Layout.fillWidth: true
            Layout.minimumWidth: 0
            spacing: 4

            Text {
                Layout.fillWidth: true
                text: root.label
                font.family: Theme.fontFamily
                font.pixelSize: Theme.bodySize
                font.weight: Font.Medium
                color: Theme.textPrimary
                wrapMode: Text.WordWrap
            }

            Text {
                Layout.fillWidth: true
                visible: root.description !== ""
                text: root.description
                font.family: Theme.fontFamily
                font.pixelSize: Theme.settingsSubtitleSize
                color: Theme.textSecondary
                wrapMode: Text.WordWrap
            }
        }

        Switch {
            id: toggle
            Layout.alignment: Qt.AlignTop
            checked: root.checked
            enabled: root.interactive
            onToggled: root.toggled(checked)

            indicator: Rectangle {
                implicitWidth: 44
                implicitHeight: 24
                radius: 12
                color: toggle.checked ? Theme.accent : Qt.rgba(1, 1, 1, 0.12)
                border.color: toggle.checked
                    ? Theme.accent
                    : Qt.rgba(1, 1, 1, 0.08)
                border.width: 1

                Behavior on color {
                    ColorAnimation {
                        duration: Theme.colorDuration
                        easing.type: Easing.OutCubic
                    }
                }

                Rectangle {
                    x: toggle.checked ? parent.width - width - 3 : 3
                    anchors.verticalCenter: parent.verticalCenter
                    width: 18
                    height: 18
                    radius: 9
                    color: toggle.checked ? Theme.textPrimary : Theme.textSecondary

                    Behavior on x {
                        NumberAnimation {
                            duration: Theme.colorDuration
                            easing.type: Easing.OutCubic
                        }
                    }
                }
            }
        }
    }
}
