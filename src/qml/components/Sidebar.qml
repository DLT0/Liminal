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
    property int menuFocusIndex: 0

    signal pageSelected(int index)
    signal searchChanged(string text)
    signal contentFocusRequested()

    readonly property var menuItems: [
        { icon: "music_note", label: "Music", page: 2 },
        { icon: "movie", label: "Videos", page: 3 },
        { icon: "download", label: "Download", page: 4 },
        { icon: "settings", label: "Settings", page: 5 }
    ]

    function focusSidebar() {
        sidebarFocus.forceActiveFocus()
        syncMenuFocusToPage()
    }

    function syncMenuFocusToPage() {
        for (var i = 0; i < menuItems.length; i++) {
            if (menuItems[i].page === currentPage) {
                menuFocusIndex = i
                menuList.positionViewAtIndex(i, ListView.Visible)
                return
            }
        }
    }

    function selectMenuIndex(index) {
        if (index < 0 || index >= menuItems.length)
            return
        sidebarFocus.forceActiveFocus()
        menuFocusIndex = index
        menuList.positionViewAtIndex(index, ListView.Visible)
        pageSelected(menuItems[index].page)
    }

    onCurrentPageChanged: {
        if (sidebarFocus.activeFocus)
            syncMenuFocusToPage()
    }

    FocusScope {
        id: sidebarFocus
        anchors.fill: parent
        focus: false

        Rectangle {
            anchors.left: parent.left
            anchors.top: parent.top
            anchors.bottom: parent.bottom
            anchors.topMargin: 24
            anchors.bottomMargin: 20
            width: 3
            radius: 2
            color: Theme.accentStart
            visible: sidebarFocus.activeFocus
            opacity: 0.85

            Behavior on opacity {
                NumberAnimation {
                    duration: Theme.colorDuration
                    easing.type: Easing.OutCubic
                }
            }
        }

        Keys.onUpPressed: {
            selectMenuIndex((menuFocusIndex - 1 + menuItems.length) % menuItems.length)
            event.accepted = true
        }

        Keys.onDownPressed: {
            selectMenuIndex((menuFocusIndex + 1) % menuItems.length)
            event.accepted = true
        }

        Keys.onReturnPressed: {
            selectMenuIndex(menuFocusIndex)
            event.accepted = true
        }

        Keys.onSpacePressed: {
            selectMenuIndex(menuFocusIndex)
            event.accepted = true
        }

        Keys.onTabPressed: {
            root.contentFocusRequested()
            event.accepted = true
        }

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
                    keyboardFocused: sidebarFocus.activeFocus && root.menuFocusIndex === index
                    onClicked: root.selectMenuIndex(index)
                }
            }
        }
    }
}
