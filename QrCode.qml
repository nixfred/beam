import QtQuick
import Quickshell.Io

// A fixed white quiet zone is part of the code, independent of the shell theme.
Item {
    id: root
    property string text: ""
    property string cli: ""
    property int size: 160
    property bool active: true
    property string path: ""
    property string error: ""
    property string requestText: ""
    property string requestCli: ""
    readonly property bool loaded: image.status === Image.Ready && path !== ""
    readonly property bool busy: generator.running
    implicitWidth: size
    implicitHeight: size
    activeFocusOnTab: visible && active && error !== ""
    Accessible.role: Accessible.Button
    Accessible.name: error ? "Retry QR code" : "QR code"
    Accessible.description: error || text
    onTextChanged: invalidate()
    onCliChanged: invalidate()
    onActiveChanged: if (active)
        schedule.restart()
    onVisibleChanged: if (visible)
        schedule.restart()
    Component.onCompleted: schedule.restart()

    function invalidate() {
        path = "";
        error = "";
        schedule.restart();
    }
    function retry() {
        if (!generator.running) {
            error = "";
            path = "";
            schedule.restart();
        }
    }
    function generate() {
        if (!active || !visible || !text || !cli || generator.running || path)
            return;
        requestText = text;
        requestCli = cli;
        generator.command = [cli, "qr", text];
        generator.running = true;
    }
    Keys.onReturnPressed: retry()
    Keys.onSpacePressed: retry()

    Timer {
        id: schedule
        interval: 1
        onTriggered: root.generate()
    }
    Process {
        id: generator
        stdout: StdioCollector {
            id: output
            waitForEnd: true
        }
        stderr: StdioCollector {
            waitForEnd: true
        }
        onExited: function (exitCode, exitStatus) {
            if (root.requestText !== root.text || root.requestCli !== root.cli) {
                schedule.restart();
                return;
            }
            var result = null;
            try {
                result = JSON.parse(output.text);
            } catch (e) {}
            if (exitCode === 0 && result && result.ok && /^\//.test(result.path || "")) {
                root.path = result.path;
                root.error = "";
            } else {
                root.path = "";
                root.error = "QR unavailable.\nUse Install in Expert, then retry.";
            }
        }
    }
    Rectangle {
        anchors.fill: parent
        color: "white"
        radius: 5
        border.width: root.activeFocus ? 2 : 0
        border.color: "#444444"
        Image {
            id: image
            anchors.fill: parent
            anchors.margins: 8
            source: root.path ? "file://" + encodeURI(root.path) : ""
            fillMode: Image.PreserveAspectFit
            smooth: false
            cache: false
            asynchronous: true
            onStatusChanged: if (status === Image.Error)
                root.error = "QR could not load.\nSelect to retry."
        }
        Text {
            anchors.fill: parent
            anchors.margins: 10
            visible: !root.loaded
            text: root.error || (root.text ? "Preparing QR…" : "No address yet")
            textFormat: Text.PlainText
            wrapMode: Text.WordWrap
            horizontalAlignment: Text.AlignHCenter
            verticalAlignment: Text.AlignVCenter
            font.pixelSize: 12
            color: "#202020"
        }
        MouseArea {
            anchors.fill: parent
            enabled: root.error !== ""
            cursorShape: Qt.PointingHandCursor
            onClicked: {
                root.forceActiveFocus();
                root.retry();
            }
        }
    }
}
