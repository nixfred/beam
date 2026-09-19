import QtQuick
import Quickshell
import Quickshell.Io
import Quickshell.Wayland
import qs.Commons
import qs.Ui as Ui

Ui.BarWidget {
    id: root
    moduleName: "nixfred.beam"
    property var anchorItem: button
    readonly property var svc: bar && bar.shell ? bar.shell.serviceFor(moduleName) : null
    readonly property bool streaming: !!(svc && svc.streaming && svc.statusFresh)
    readonly property string state: svc ? svc.state : "checking"
    readonly property color foreground: bar ? bar.foreground : Color.foreground
    readonly property color dotColor: svc && svc.warning ? Color.urgent : streaming ? Color.accent : state === "ready" ? foreground : Util.alpha(foreground, 0.4)
    readonly property bool showLabel: String(setting("showLabel", true)) !== "false"
    readonly property string stateLabel: svc && svc.warning ? "check" : streaming ? "live" : state === "ready" ? "iPad" : state === "checking" ? "…" : "set up"
    readonly property bool opened: panel.opened
    property bool popoutSwitchClosing: false
    implicitWidth: vertical ? barSize : Math.max(Style.space(26), row.implicitWidth + Style.space(14))
    implicitHeight: vertical ? Style.space(30) : barSize

    function open() {
        panel.open();
        if (svc)
            svc.refresh();
    }
    function close() {
        panel.close();
    }
    function toggle() {
        opened ? close() : open();
    }
    function closeForPopoutSwitch() {
        popoutSwitchClosing = true;
        close();
        Qt.callLater(function () {
            root.popoutSwitchClosing = false;
        });
    }

    Binding {
        target: root.svc
        property: "settings"
        value: root.settings
        when: !!root.svc
    }

    // Native compositor inhibition is scoped to this visible surface. Unload,
    // crash, disconnect and turning the setting off all destroy the hold.
    IdleInhibitor {
        window: root.QsWindow.window
        enabled: root.visible && root.streaming && !!(root.svc && root.svc.holdAwake)
    }

    Ui.WidgetButton {
        id: button
        anchors.fill: parent
        bar: root.bar
        text: ""
        labelVisible: false
        hasVisualContent: true
        useActiveColor: false
        tooltipText: "Beam · " + (root.svc && root.svc.warning ? root.svc.warning : root.streaming ? "Streaming to Moonlight" : root.state === "ready" ? "Ready. Open Moonlight on your iPad." : "Set up this desktop for your iPad")
        onPressed: root.toggle()
        Row {
            id: row
            anchors.centerIn: parent
            spacing: Style.space(5)
            Item {
                width: Style.space(16)
                height: width
                anchors.verticalCenter: parent.verticalCenter
                Rectangle {
                    anchors.centerIn: parent
                    width: Style.space(16)
                    height: width
                    radius: width / 2
                    color: root.dotColor
                    border.width: 0
                    visible: root.streaming
                    opacity: 0.1
                    SequentialAnimation on opacity {
                        running: root.visible && root.streaming
                        loops: Animation.Infinite
                        NumberAnimation {
                            to: 0.3
                            duration: 1200
                            easing.type: Easing.InOutSine
                        }
                        NumberAnimation {
                            to: 0.1
                            duration: 1200
                            easing.type: Easing.InOutSine
                        }
                    }
                }
                Rectangle {
                    anchors.centerIn: parent
                    width: Style.space(8)
                    height: width
                    radius: width / 2
                    border.width: 0
                    color: root.dotColor
                    Behavior on color {
                        ColorAnimation {
                            duration: 180
                        }
                    }
                }
            }
            Text {
                visible: root.showLabel && !root.vertical
                anchors.verticalCenter: parent.verticalCenter
                text: root.stateLabel
                textFormat: Text.PlainText
                font.family: root.bar ? root.bar.fontFamily : Style.font.family
                font.pixelSize: Style.font.body
                color: root.foreground
            }
        }
    }
    BeamPanel {
        id: panel
        widget: root
    }
    IpcHandler {
        target: "nixfred.beam"
        function open(): void {
            root.open();
        }
        function close(): void {
            root.close();
        }
        function toggle(): void {
            root.toggle();
        }
        function expert(): void {
            panel.sizingMode = false;
            panel.expertMode = true;
            root.open();
        }
        function guided(): void {
            panel.sizingMode = false;
            panel.expertMode = false;
            root.open();
        }
        function step(number: int): void {
            panel.expertMode = false;
            root.open();
            panel.setStep(number);
        }
        function geometry(): string {
            return JSON.stringify(panel.geometry());
        }
        function ipad(family: string): void {
            root.open();
            panel.showSizing(family);
        }
    }
}
