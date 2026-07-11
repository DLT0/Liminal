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
            Layout.preferredWidth: 340
            Layout.preferredHeight: 44

            TextField {
                id: headerSearch
                anchors.fill: parent
                placeholderText: root.searchPlaceholder
                font.family: Theme.fontFamily
                font.pixelSize: 14
                color: Theme.textPrimary
                placeholderTextColor: Theme.textMuted
                leftPadding: 42
                rightPadding: 20
                topPadding: 10
                bottomPadding: 10

                background: Rectangle {
                    radius: 24
                    color: Theme.inputBg
                    border.color: Theme.inputBorder
                    border.width: 1
                }

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
