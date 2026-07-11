import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import Liminal 1.0

Item {
    id: root

    property string searchText: ""
    property string pageTitle: "Discover"
    property int currentPage: 0
    property string searchPlaceholder: "Tìm nhạc trên YouTube…"

    signal searchChanged(string text)
    signal searchSubmitted(string text)

    RowLayout {
        anchors.fill: parent
        anchors.leftMargin: Theme.contentPadding
        anchors.rightMargin: Theme.contentPadding
        anchors.topMargin: 20
        anchors.bottomMargin: 12
        spacing: 16

        Text {
            text: root.pageTitle
            font.family: Theme.fontFamily
            font.pixelSize: Theme.pageTitleSize
            font.weight: Font.Bold
            color: Theme.textPrimary
        }

        Item { Layout.fillWidth: true }

        Item {
            Layout.preferredWidth: root.currentPage === 4 ? 0 : 340
            Layout.preferredHeight: 44
            visible: root.currentPage !== 4
            clip: false

            Rectangle {
                id: searchBg
                anchors.fill: parent
                radius: 24
                color: Theme.inputBg
                border.color: headerSearch.activeFocus ? Theme.accentStart : Theme.inputBorder
                border.width: headerSearch.activeFocus ? Theme.focusRingWidth : 1

                Behavior on border.color {
                    ColorAnimation {
                        duration: Theme.colorDuration
                        easing.type: Easing.OutCubic
                    }
                }

                Behavior on border.width {
                    NumberAnimation {
                        duration: Theme.colorDuration
                        easing.type: Easing.OutCubic
                    }
                }
            }

            KeyboardFocusRing {
                anchors.fill: parent
                show: headerSearch.activeFocus
                ringRadius: 24
                ringWidth: Theme.focusRingWidth
                glowOpacity: 0.22
            }

            TextField {
                id: headerSearch
                anchors.fill: parent
                focusPolicy: Qt.ClickFocus
                placeholderText: root.searchPlaceholder
                font.family: Theme.fontFamily
                font.pixelSize: 14
                color: Theme.textPrimary
                placeholderTextColor: Theme.textMuted
                leftPadding: 42
                rightPadding: 20
                topPadding: 10
                bottomPadding: 10

                background: Item {}

                onTextChanged: root.searchChanged(text)

                Keys.onReturnPressed: root.searchSubmitted(text)
            }

            AppIcon {
                anchors.left: parent.left
                anchors.leftMargin: 14
                anchors.verticalCenter: parent.verticalCenter
                name: "search"
                font.pixelSize: 20
                color: Theme.textMuted
            }
        }
    }

    function setSearchText(text) {
        if (headerSearch.text !== text)
            headerSearch.text = text
    }

    function updateForPage(page) {
        searchPlaceholder = "Tìm trong thư viện…"
    }
}
