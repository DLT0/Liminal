import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import Liminal 1.0

Popup {
    id: root

    property bool videoMode: false
    property string sourcePath: ""
    property var targets: []

    signal createFolderRequested()
    signal targetSelected(string path)

    modal: false
    focus: true
    padding: 8
    z: 10000
    closePolicy: Popup.CloseOnPressOutside | Popup.CloseOnEscape

    readonly property string createLabel: videoMode ? "Tạo phim bộ mới" : "Tạo playlist mới"
    readonly property string emptyLabel: videoMode ? "Chưa có phim bộ khác" : "Không còn playlist khác"

    background: Rectangle {
        implicitWidth: 220
        color: Theme.glassStrong
        radius: 10
        border.width: 1
        border.color: Theme.glassStrongBorder

        Rectangle {
            anchors.fill: parent
            anchors.margins: 1
            radius: 9
            color: "transparent"
            border.width: 1
            border.color: "#08ffffff"
        }
    }

    function refreshTargets() {
        targets = sourcePath ? backend.foldersForMove(sourcePath) : []
    }

    function openAdjacentTo(item) {
        if (!item)
            return
        refreshTargets()
        var overlay = Overlay.overlay
        if (!overlay)
            return
        var topLeft = item.mapToItem(overlay, item.width, 0)
        root.x = topLeft.x
        root.y = topLeft.y
        root.open()
    }

    contentItem: Column {
        spacing: 0
        width: Math.max(220, implicitWidth)

        MoveTargetMenuRow {
            iconName: "create_new_folder"
            label: root.createLabel
            onActivated: {
                root.createFolderRequested()
                root.close()
            }
        }

        Rectangle {
            width: parent.width
            height: 9
            color: "transparent"

            Rectangle {
                anchors.verticalCenter: parent.verticalCenter
                width: parent.width
                height: 1
                color: Theme.glassStrongBorder
            }
        }

        Repeater {
            model: root.targets

            MoveTargetMenuRow {
                required property var modelData
                iconName: "folder"
                label: modelData.title
                onActivated: {
                    root.targetSelected(modelData.path)
                    root.close()
                }
            }
        }

        MoveTargetMenuRow {
            visible: root.targets.length === 0
            enabled: false
            label: root.emptyLabel
        }
    }
}
