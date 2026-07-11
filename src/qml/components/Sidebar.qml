import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import Liminal 1.0

GlassPanel {
    id: root

    width: Theme.sidebarWidth
    radius: 0
    strong: false

    property int currentPage: 2
    property string searchText: ""

    signal pageSelected(int index, bool again)
    signal searchChanged(string text)

    readonly property var menuItems: [
        { icon: "music_note", label: "Music", page: 2 },
        { icon: "movie", label: "Videos", page: 3 },
        { icon: "download", label: "Download", page: 4 },
        { icon: "settings", label: "Settings", page: 5 }
    ]

    ColumnLayout {
        anchors.fill: parent
        anchors.topMargin: 20
        anchors.bottomMargin: 16
        spacing: 16

        // Logo + brand
        RowLayout {
            Layout.leftMargin: 16
            Layout.rightMargin: 16
            spacing: 10

            AppLogo {
                logoSize: 36
                cornerRadius: 9
            }

            ColumnLayout {
                spacing: 0

                Text {
                    text: "Liminal"
                    font.family: Theme.fontFamily
                    font.pixelSize: 15
                    font.weight: Font.Bold
                    color: Theme.textPrimary
                }

                Text {
                    text: "Media Player"
                    font.family: Theme.fontFamily
                    font.pixelSize: Theme.captionSize
                    color: Theme.textMuted
                }
            }
        }

        // Menu list
        ListView {
            id: menuList
            Layout.fillWidth: true
            Layout.fillHeight: true
            Layout.leftMargin: 8
            Layout.rightMargin: 8
            spacing: 2
            clip: true
            interactive: false
            model: root.menuItems

            delegate: SidebarMenuItem {
                width: ListView.view.width
                icon: modelData.icon
                label: modelData.label
                active: root.currentPage === modelData.page
                onClicked: root.pageSelected(modelData.page, false)
                onDoubleClicked: {
                    if (modelData.page === 2 || modelData.page === 3)
                        root.pageSelected(modelData.page, true)
                }
            }
        }
    }
}
