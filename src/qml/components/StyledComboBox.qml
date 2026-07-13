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
        x: control.width - width - 12
        y: (control.height - height) / 2
        text: "▾"
        color: Theme.textSecondary
        font.pixelSize: 16
    }

    background: Rectangle {
        radius: Theme.cardRadius
        color: Theme.inputBg
        border.width: control.activeFocus ? 2 : 1
        border.color: control.activeFocus ? Theme.accent : Theme.inputBorder
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
