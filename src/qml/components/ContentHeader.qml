import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import Liminal 1.0

Item {
    id: root

    property string searchText: ""
    property string pageTitle: "Music"
    property int currentPage: 0
    property string searchPlaceholder: uiConfig.searchPlaceholder

    readonly property bool hidePageTitle: false
    readonly property bool showSearch: root.currentPage !== 4
        && root.currentPage !== 5
        && root.currentPage !== 7

    signal searchChanged(string text)
    signal searchSubmitted(string text)
    signal redeemShareClicked()

    Rectangle {
        anchors.fill: parent
        color: Theme.bgElevated
    }

    RowLayout {
        anchors.fill: parent
        anchors.leftMargin: Theme.contentPadding
        anchors.rightMargin: Theme.contentPadding
        anchors.topMargin: 20
        anchors.bottomMargin: 12
        spacing: 16

        RowLayout {
            spacing: 12
            Layout.fillWidth: true
            Layout.minimumWidth: 0

            Text {
                visible: !root.hidePageTitle
                text: root.pageTitle
                font.family: Theme.fontFamily
                font.pixelSize: Theme.pageTitleSize
                font.weight: Font.Bold
                color: Theme.textPrimary
                elide: Text.ElideRight
                Layout.maximumWidth: root.showSearch
                    ? Math.max(80, root.width - uiConfig.searchWidth - 80)
                    : root.width
            }

            Rectangle {
                visible: root.currentPage === 2 || root.currentPage === 3
                Layout.preferredHeight: 32
                Layout.preferredWidth: redeemLabel.implicitWidth + 24
                radius: 8
                color: redeemMouse.containsMouse ? Theme.hoverOverlay : Theme.inputBg
                border.color: Theme.inputBorder
                border.width: 1

                Row {
                    id: redeemLabel
                    anchors.centerIn: parent
                    spacing: 6

                    AppIcon {
                        anchors.verticalCenter: parent.verticalCenter
                        name: "redeem"
                        font.pixelSize: 16
                        color: Theme.textSecondary
                    }

                    Text {
                        text: "Nhập mã"
                        color: Theme.textPrimary
                        font.family: Theme.fontFamily
                        font.pixelSize: Theme.captionSize
                        font.weight: Font.DemiBold
                    }
                }

                MouseArea {
                    id: redeemMouse
                    anchors.fill: parent
                    hoverEnabled: true
                    cursorShape: Qt.PointingHandCursor
                    onClicked: root.redeemShareClicked()
                }
            }

            Item { Layout.fillWidth: true }
        }

        // Search luôn cùng hàng (không wrap) — thu hẹp khi viewport hẹp
        Item {
            visible: root.showSearch
            Layout.alignment: Qt.AlignVCenter | Qt.AlignRight
            Layout.preferredWidth: Math.min(uiConfig.searchWidth, Math.max(180, root.width * 0.38))
            Layout.minimumWidth: 160
            Layout.maximumWidth: uiConfig.searchWidth
            Layout.preferredHeight: 44
            Layout.fillWidth: false
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
        searchPlaceholder = uiConfig.searchPlaceholder
    }
}
