import QtQuick
import QtQuick.Controls
import Liminal 1.0

Item {
    id: root

    property string title: ""
    property string subtitle: ""
    property string imageSource: ""
    property string resolvedImageSource: {
        if (!imageSource)
            return ""
        if (imageSource.startsWith("http://") || imageSource.startsWith("https://") || imageSource.startsWith("file://"))
            return imageSource
        return "file://" + imageSource
    }
    property color accentColor: Theme.accentEnd
    property bool widescreen: false
    property bool clickEnabled: true

    signal clicked()

    readonly property real posterAspect: widescreen ? Theme.videoPosterAspect : 1

    readonly property real cardScale: hoverMa.containsMouse ? Theme.hoverScale : 1.0

    width: implicitWidth
    height: poster.height + titleLabel.implicitHeight + subtitleLabel.implicitHeight + 12

    scale: cardScale
    transformOrigin: Item.Center

    Behavior on scale {
        NumberAnimation {
            duration: Theme.hoverDuration
            easing.type: Easing.OutCubic
        }
    }

    // Poster
    Item {
        id: poster
        width: parent.width
        height: width / posterAspect

        Rectangle {
            id: clipRect
            anchors.fill: parent
            radius: Theme.libraryCardRadius
            clip: true
            color: Theme.cardBg

            Image {
                anchors.fill: parent
                source: root.resolvedImageSource
                fillMode: Image.PreserveAspectCrop
                visible: root.imageSource !== ""
            }

            // Placeholder gradient when no image
            Rectangle {
                anchors.fill: parent
                visible: root.imageSource === ""
                gradient: Gradient {
                    orientation: Gradient.Vertical
                    GradientStop { position: 0; color: Qt.lighter(root.accentColor, 1.3) }
                    GradientStop { position: 1; color: Qt.darker(root.accentColor, 1.4) }
                }

                Text {
                    anchors.centerIn: parent
                    text: root.title.length > 0 ? root.title.charAt(0).toUpperCase() : "?"
                    font.family: Theme.fontFamily
                    font.pixelSize: 42
                    font.weight: Font.Bold
                    color: "#50ffffff"
                }
            }

            // Bottom gradient overlay
            Rectangle {
                anchors.left: parent.left
                anchors.right: parent.right
                anchors.bottom: parent.bottom
                height: parent.height * 0.45

                gradient: Gradient {
                    orientation: Gradient.Vertical
                    GradientStop { position: 0; color: "transparent" }
                    GradientStop { position: 1; color: "#cc000000" }
                }
            }

            Column {
                anchors.left: parent.left
                anchors.right: parent.right
                anchors.bottom: parent.bottom
                anchors.margins: 10
                spacing: 2

                Text {
                    id: overlayTitle
                    width: parent.width
                    text: root.title
                    font.family: Theme.fontFamily
                    font.pixelSize: Theme.bodySize
                    font.weight: Font.Bold
                    color: Theme.textPrimary
                    elide: Text.ElideRight
                }

                Text {
                    id: overlaySubtitle
                    width: parent.width
                    text: root.subtitle
                    font.family: Theme.fontFamily
                    font.pixelSize: Theme.captionSize
                    color: Theme.textSecondary
                    elide: Text.ElideRight
                }
            }
        }

        Rectangle {
            anchors.fill: parent
            radius: Theme.libraryCardRadius
            color: "transparent"
            border.color: Theme.cardBorder
            border.width: 1
        }
    }

    // Labels below poster (hidden — info shown in overlay)
    Text {
        id: titleLabel
        visible: false
        text: root.title
    }

    Text {
        id: subtitleLabel
        visible: false
        text: root.subtitle
    }

    MouseArea {
        id: hoverMa
        anchors.fill: poster
        enabled: root.clickEnabled
        hoverEnabled: true
        acceptedButtons: Qt.LeftButton | Qt.RightButton
        cursorShape: Qt.PointingHandCursor
        onClicked: function(mouse) {
            if (mouse.button === Qt.LeftButton)
                root.clicked()
            else if (mouse.button === Qt.RightButton)
                root.contextMenuRequested(mouse.x, mouse.y)
        }
    }

    signal contextMenuRequested(real x, real y)
}
