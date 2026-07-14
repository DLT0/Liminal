import QtQuick
import QtQuick.Controls
import Liminal 1.0

ComboBox {
    id: control

    implicitHeight: 40
    font.family: Theme.fontFamily
    font.pixelSize: Theme.bodySize

    contentItem: Text {
        leftPadding: 12
        rightPadding: 36
        text: control.displayText
        font: control.font
        color: Theme.textPrimary
        verticalAlignment: Text.AlignVCenter
        elide: Text.ElideRight
    }

    indicator: Text {
        x: control.width - width - 14
        y: (control.height - height) / 2
        text: "▾"
        color: control.hovered ? Theme.textPrimary : Theme.textMuted
        font.pixelSize: 11

        Behavior on color {
            ColorAnimation {
                duration: Theme.colorDuration
                easing.type: Easing.OutCubic
            }
        }
    }

    background: Rectangle {
        radius: 8
        color: control.pressed
            ? Theme.bgHighlight
            : (control.hovered ? Theme.bgCardHover : Theme.inputBg)
        border.width: 1
        border.color: control.activeFocus ? Theme.accent : Theme.settingsCardBorder

        Behavior on color {
            ColorAnimation {
                duration: Theme.colorDuration
                easing.type: Easing.OutCubic
            }
        }
    }

    delegate: ItemDelegate {
        required property int index
        width: control.width
        height: 38
        highlighted: control.highlightedIndex === index

        contentItem: Text {
            leftPadding: 12
            text: control.textAt(index)
            font.family: Theme.fontFamily
            font.pixelSize: Theme.bodySize
            color: Theme.textPrimary
            verticalAlignment: Text.AlignVCenter
            elide: Text.ElideRight
        }

        background: Rectangle {
            color: parent.highlighted ? Theme.hoverOverlay : Theme.bgElevated
        }
    }

    popup: Popup {
        y: control.height + 4
        width: control.width
        padding: 1
        background: Rectangle {
            radius: Theme.cardRadius
            color: Theme.bgElevated
            border.color: Theme.glassBorder
            border.width: 1
        }
        contentItem: ListView {
            clip: true
            implicitHeight: Math.min(contentHeight, 240)
            model: control.delegateModel
            currentIndex: control.highlightedIndex
        }
    }
}
