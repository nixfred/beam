pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Layouts
import Quickshell
import qs.Commons
import qs.Ui as Ui

Ui.Panel {
    id: panel
    moduleName: "nixfred.beam"
    manageIpc: false
    required property var widget
    readonly property var svc: widget ? widget.svc : null
    readonly property color foreground: Color.popups.text
    readonly property color secondary: Util.alpha(foreground, 0.76)
    readonly property color hairline: Util.alpha(foreground, 0.15)
    readonly property string fontFamily: widget && widget.bar ? widget.bar.fontFamily : Style.font.family
    readonly property int bodySize: Math.max(13, Style.font.body)
    readonly property int smallSize: Math.max(12, Style.font.bodySmall)
    readonly property string appUrl: "https://apps.apple.com/app/id1000551566"
    readonly property string connectionAddress: svc ? (svc.pairedClients === 0 && svc.lanAddress ? svc.lanAddress : svc.address) : ""
    readonly property var report: svc && svc.actionReport ? svc.actionReport : ({
            state: "idle",
            title: "Ready when you are",
            message: "Choose an action. Beam checks the result for you.",
            next: ""
        })
    readonly property bool fresh: !!(svc && svc.statusFresh)
    readonly property bool hostReady: !!(svc && svc.setupReady)
    readonly property string streamTitle: !svc || !fresh ? "Checking this desktop" : svc.streaming ? "Your desktop is live" : svc.allReady ? "Ready for your iPad" : "Let's get you connected"
    property bool expertMode: false
    property int stepNumber: 2
    property bool initialized: false
    property bool removeConfirmation: false
    property bool ipadConfirmed: false
    property bool prerequisitesConfirmed: false
    readonly property var stepNames: ["What you need", "This computer", "iPad app", "Your login", "Connect", "Watch"]

    function setStep(number) {
        stepNumber = Math.max(1, Math.min(6, number));
        removeConfirmation = false;
    }
    function initialStep() {
        if (!initialized && svc && svc.ready) {
            stepNumber = Math.max(1, Math.min(6, svc.nextStep || 2));
            initialized = true;
        }
    }
    onOpenedChanged: {
        if (opened) {
            initialized = false;
            initialStep();
            if (svc)
                svc.refresh();
        } else
            removeConfirmation = false;
    }
    onExpertModeChanged: removeConfirmation = false
    Connections {
        target: panel.svc
        function onReadyChanged() {
            if (panel.opened)
                panel.initialStep();
        }
        function onAdminConfiguredChanged() {
            if (panel.svc && panel.opened && !panel.expertMode && panel.stepNumber === 4 && panel.svc.adminConfigured)
                panel.setStep(5);
        }
        function onPairedClientsChanged() {
            if (panel.svc && panel.opened && !panel.expertMode && panel.stepNumber === 5 && panel.svc.pairedClients > 0)
                panel.setStep(6);
        }
    }
    function nextStep() {
        if (stepNumber === 1)
            prerequisitesConfirmed = true;
        if (stepNumber === 3)
            ipadConfirmed = true;
        setStep(stepNumber + 1);
    }
    function stepDone(number) {
        if (number === 1) return prerequisitesConfirmed;
        if (number === 3) return ipadConfirmed;
        if (!svc || !fresh) return false;
        if (number === 2) return hostReady;
        if (number === 4) return svc.adminConfigured;
        if (number === 5) return svc.pairedClients > 0;
        return svc.allReady;
    }
    readonly property bool canContinue: stepNumber === 1 || stepNumber === 3 || stepNumber === 6 || (svc && fresh && (stepNumber === 2 ? hostReady : stepNumber === 4 ? svc.adminConfigured : stepNumber === 5 ? svc.pairedClients > 0 : true))
    function primaryAction() {
        if (!svc || svc.busy)
            return;
        if (!svc.installed || !svc.qrAvailable)
            svc.installInTerminal();
        else if (!hostReady)
            svc.repair();
        else if (!svc.adminConfigured)
            svc.admin();
        else
            svc.pinPage();
    }
    readonly property string primaryLabel: !svc || !svc.installed ? "Set up this computer" : !svc.qrAvailable ? "Install QR helper" : !hostReady ? "Make this computer ready" : !svc.adminConfigured ? "Create Sunshine login" : "Open PIN page"

    function focusNext(direction) {
        var current = keyCatcher;
        function focused(item) {
            var children = item.children || [];
            for (var i = 0; i < children.length; i++) {
                var result = focused(children[i]);
                if (result)
                    return result;
            }
            return item.activeFocus ? item : null;
        }
        current = focused(keyCatcher) || keyCatcher;
        var candidate = current;
        for (var i = 0; i < 120; ++i) {
            candidate = candidate.nextItemInFocusChain(direction > 0);
            if (!candidate || candidate === current)
                break;
            if (candidate.visible && candidate.enabled && candidate.activeFocusOnTab) {
                candidate.forceActiveFocus(Qt.TabFocusReason);
                return;
            }
        }
    }
    function geometry() {
        var texts = [];
        var outside = [];
        function inspect(item) {
            if (!item || !item.visible)
                return;
            if (item.text !== undefined && item.contentHeight !== undefined && item.mapToItem) {
                var position = item.mapToItem(content, 0, 0);
                var row = {
                    text: String(item.text),
                    x: position.x,
                    y: position.y,
                    width: item.width,
                    height: item.height,
                    contentWidth: item.contentWidth,
                    contentHeight: item.contentHeight,
                    font: item.font.pixelSize
                };
                texts.push(row);
                if (position.x < -1 || position.y < -1 || position.x + item.width > content.width + 1 || position.y + item.height > content.height + 1 || item.contentHeight > item.height + 1 || item.contentWidth > item.width + 1)
                    outside.push(row);
            }
            var children = item.children || [];
            for (var i = 0; i < children.length; i++)
                inspect(children[i]);
        }
        inspect(content);
        return {
            opened: opened,
            expert: expertMode,
            step: stepNumber,
            screen: [popup.screenW, popup.screenH],
            card: [popup.cardOrigin.x, popup.cardOrigin.y, popup.contentWidth, popup.contentHeight],
            available: [popup.availableCardWidth, popup.availableCardHeight],
            content: [content.width, content.height, content.implicitHeight],
            fits: content.implicitHeight <= keyCatcher.height + 1 && outside.length === 0,
            outside: outside,
            texts: texts
        };
    }

    component Body: Text {
        Layout.fillWidth: true
        textFormat: Text.PlainText
        wrapMode: Text.Wrap
        font.family: panel.fontFamily
        font.pixelSize: panel.bodySize
        color: panel.foreground
    }
    component Caption: Body {
        font.pixelSize: panel.smallSize
        color: panel.secondary
    }
    component Heading: Body {
        font.pixelSize: Math.max(19, Style.font.title)
        font.bold: true
    }
    component ActionButton: Rectangle {
        id: control
        property string text: ""
        property bool prominent: false
        property bool danger: false
        signal clicked
        implicitWidth: buttonText.implicitWidth + 26
        implicitHeight: Math.max(34, buttonText.implicitHeight + 16)
        radius: 6
        color: prominent ? Util.alpha(Color.accent, 0.17) : mouse.containsMouse || activeFocus ? Util.alpha(panel.foreground, 0.08) : "transparent"
        border.width: 1
        border.color: activeFocus ? Color.accent : danger ? Util.alpha(Color.urgent, 0.65) : prominent ? Util.alpha(Color.accent, 0.55) : panel.hairline
        opacity: enabled ? 1 : 0.45
        activeFocusOnTab: enabled && visible
        Accessible.role: Accessible.Button
        Accessible.name: text
        Keys.onReturnPressed: clicked()
        Keys.onSpacePressed: clicked()
        Text {
            id: buttonText
            anchors.centerIn: parent
            text: control.text
            textFormat: Text.PlainText
            color: control.danger ? Color.urgent : panel.foreground
            font.family: panel.fontFamily
            font.pixelSize: panel.smallSize
            font.bold: control.prominent
        }
        MouseArea {
            id: mouse
            anchors.fill: parent
            hoverEnabled: true
            cursorShape: Qt.PointingHandCursor
            onClicked: {
                control.forceActiveFocus(Qt.MouseFocusReason);
                control.clicked();
            }
        }
    }
    component Card: Rectangle {
        id: card
        default property alias contents: inner.data
        property string title: ""
        property bool accented: false
        Layout.fillWidth: true
        implicitHeight: inner.implicitHeight + 24
        radius: 8
        border.width: 1
        border.color: accented ? Util.alpha(Color.accent, 0.4) : panel.hairline
        color: accented ? Util.alpha(Color.accent, 0.05) : Util.alpha(panel.foreground, 0.025)
        ColumnLayout {
            id: inner
            x: 12
            y: 12
            width: parent.width - 24
            spacing: 9
            Body {
                visible: card.title !== ""
                text: card.title
                font.bold: true
            }
        }
    }
    component Fact: RowLayout {
        id: fact
        property string label: ""
        property string value: ""
        property bool good: false
        property bool attention: false
        Layout.fillWidth: true
        spacing: 8
        Rectangle {
            implicitWidth: 5
            implicitHeight: 5
            radius: 3
            border.width: 0
            color: fact.attention ? Color.urgent : fact.good ? Color.accent : Util.alpha(panel.foreground, 0.3)
        }
        Caption {
            Layout.fillWidth: false
            Layout.preferredWidth: 76
            text: fact.label
        }
        Body {
            text: fact.value
            font.pixelSize: panel.smallSize
        }
    }
    component Check: RowLayout {
        property string text: ""
        property bool done: false
        property string note: ""
        Layout.fillWidth: true
        spacing: 10
        Body {
            Layout.fillWidth: false
            Layout.preferredWidth: 18
            text: parent.done ? "✓" : "○"
            color: parent.done ? Color.accent : panel.secondary
        }
        Body {
            text: parent.text
            font.pixelSize: panel.smallSize
        }
        Caption {
            Layout.fillWidth: false
            text: parent.note
        }
    }
    component Instruction: RowLayout {
        property int number: 1
        property string text: ""
        Layout.fillWidth: true
        spacing: 10
        Rectangle {
            implicitWidth: 22
            implicitHeight: 22
            radius: 11
            border.width: 0
            color: Util.alpha(Color.accent, 0.13)
            Text {
                anchors.centerIn: parent
                text: parent.parent.number
                color: panel.foreground
                font.family: panel.fontFamily
                font.pixelSize: panel.smallSize
            }
        }
        Body {
            text: parent.text
        }
    }

    Ui.KeyboardPanel {
        id: popup
        anchorItem: panel.widget.anchorItem
        owner: panel.widget
        bar: panel.widget.bar
        open: panel.opened
        padding: 14
        focusTarget: keyCatcher
        contentWidth: fittedContentWidth(1160)
        // The layout uses its true natural height. The geometry audit detects
        // a too-small display; clipping is never used to make a test pass.
        contentHeight: fittedContentHeight(content.implicitHeight)
        Ui.PanelKeyCatcher {
            id: keyCatcher
            anchors.fill: parent
            onCloseRequested: panel.close()
            onTabRequested: function (direction) {
                panel.focusNext(direction);
            }
            onMoveRequested: function (dx, dy) {
                panel.focusNext(dx || dy);
            }
            onActivateRequested: panel.focusNext(1)
            ColumnLayout {
                id: content
                width: parent.width
                spacing: 12
                RowLayout {
                    Layout.fillWidth: true
                    spacing: 12
                    Rectangle {
                        implicitWidth: 12
                        implicitHeight: 12
                        radius: 6
                        border.width: 0
                        color: panel.svc && panel.svc.warning ? Color.urgent : panel.fresh ? Color.accent : panel.hairline
                    }
                    Heading {
                        Layout.fillWidth: false
                        text: "Beam"
                    }
                    Caption {
                        text: panel.streamTitle
                    }
                    ActionButton {
                        text: "Guided"
                        prominent: !panel.expertMode
                        onClicked: panel.expertMode = false
                    }
                    ActionButton {
                        text: "Expert"
                        prominent: panel.expertMode
                        onClicked: panel.expertMode = true
                    }
                    ActionButton {
                        text: "Close"
                        onClicked: panel.close()
                    }
                }
                Rectangle {
                    Layout.fillWidth: true
                    implicitHeight: 1
                    border.width: 0
                    color: panel.hairline
                }
                RowLayout {
                    visible: !panel.expertMode
                    Layout.fillWidth: true
                    spacing: 6
                    Repeater {
                        model: panel.stepNames
                        ActionButton {
                            required property int index
                            required property string modelData
                            Layout.fillWidth: true
                            Layout.preferredWidth: 1
                            text: (panel.stepDone(index + 1) ? "✓" : index + 1) + "  " + modelData
                            prominent: panel.stepNumber === index + 1
                            onClicked: panel.setStep(index + 1)
                        }
                    }
                }
                // Guided pages are deliberate steps, never overflow tabs.
                Loader {
                    id: guided
                    visible: !panel.expertMode
                    active: visible
                    Layout.fillWidth: true
                    Layout.minimumHeight: 310
                    Layout.preferredHeight: Math.max(310, item ? item.implicitHeight : 0)
                    sourceComponent: [needsPage, hostPage, ipadPage, loginPage, connectPage, watchPage][panel.stepNumber - 1]
                }
                RowLayout {
                    id: expert
                    visible: panel.expertMode
                    Layout.fillWidth: true
                    spacing: 12
                    Card {
                        Layout.alignment: Qt.AlignTop
                        Layout.preferredWidth: 1.05
                        title: "This computer"
                        Fact {
                            label: "Sunshine"
                            value: svc && svc.installed ? "Installed · " + (svc.version || "version unknown") : "Not installed"
                            good: svc && svc.installed
                        }
                        Fact {
                            label: "Processes"
                            value: svc ? String(svc.processes) + (svc.processes === 1 ? " · running" : svc.processes > 1 ? " · repair needed" : " · stopped") : "Checking"
                            good: svc && svc.processes === 1
                            attention: svc && svc.processes > 1
                        }
                        Fact {
                            label: "Firewall"
                            value: panel.firewallText()
                            good: svc && svc.firewallReady
                        }
                        Fact {
                            label: "Autostart"
                            value: svc && svc.autostart ? "Ready" : "Not set"
                            good: svc && svc.autostart
                        }
                        Fact {
                            label: "Unit"
                            value: svc && svc.unit ? svc.unit + (svc.unitEnabled ? " · enabled" : " · disabled") : "No packaged unit"
                            attention: svc && svc.unitEnabled && svc.autostart
                        }
                        Fact {
                            label: "Display"
                            value: svc && svc.displayFound ? "Capture detected" : "Not detected yet"
                            good: svc && svc.displayFound
                        }
                        Fact {
                            label: "Encoder"
                            value: svc && svc.encoder ? svc.encoder + " · " + svc.encoderKind : "Waiting for Sunshine"
                            good: svc && svc.encoder !== ""
                        }
                        Fact {
                            label: "Admin"
                            value: svc && svc.adminConfigured ? "Login created" : svc && svc.adminUp ? "Create your login" : "Not ready"
                            good: svc && svc.adminConfigured
                        }
                        Fact {
                            label: "Paired"
                            value: svc ? String(svc.pairedClients) + " device(s)" : "Checking"
                            good: svc && svc.pairedClients > 0
                        }
                        Fact {
                            label: "Stream"
                            value: svc && svc.streaming ? (svc.locked ? "Locked · unlock this computer" : "Live") : "Waiting for Moonlight"
                            good: svc && svc.streaming && !svc.locked
                            attention: svc && svc.streaming && svc.locked
                        }
                        Fact {
                            label: "Address"
                            value: svc && svc.address ? svc.address : "No address available"
                            good: svc && svc.address !== ""
                        }
                        Fact {
                            label: "LAN"
                            value: svc && svc.lanAddress ? svc.lanAddress : "No LAN address"
                            good: svc && svc.lanAddress !== ""
                        }
                    }
                    Card {
                        Layout.alignment: Qt.AlignTop
                        Layout.preferredWidth: 1.02
                        title: svc && svc.pairedClients > 0 ? "Connect in Moonlight" : "Get connected"
                        accented: true
                        Body {
                            text: panel.connectionAddress || "No address available"
                            font.family: "monospace"
                            font.pixelSize: 19
                            font.bold: true
                        }
                        Caption {
                            text: svc && svc.pairedClients > 0 ? "In Moonlight, choose Full or Safe Area, then Beam Desktop." : "First pairing: iPad and computer on the same network."
                        }
                        RowLayout {
                            Layout.fillWidth: true
                            spacing: 12
                            ColumnLayout {
                                Layout.fillWidth: true
                                QrCode {
                                    Layout.alignment: Qt.AlignHCenter
                                    size: 128
                                    text: panel.appUrl
                                    cli: svc ? svc.cli : ""
                                    active: panel.opened && panel.expertMode
                                }
                                Caption {
                                    text: "Install Moonlight"
                                    horizontalAlignment: Text.AlignHCenter
                                }
                            }
                            ColumnLayout {
                                Layout.fillWidth: true
                                QrCode {
                                    Layout.alignment: Qt.AlignHCenter
                                    size: 128
                                    text: panel.connectionAddress
                                    cli: svc ? svc.cli : ""
                                    active: panel.opened && panel.expertMode
                                }
                                Caption {
                                    text: "Scan to copy address"
                                    horizontalAlignment: Text.AlignHCenter
                                }
                            }
                        }
                        Caption {
                            text: "Add PC (+): paste the address. Tap the PC; enter its PIN on the PIN page here."
                        }
                        Caption {
                            text: "Mouse and keyboard required for Beam; Bluetooth is fine."
                        }
                        Caption {
                            text: panel.settingsText()
                        }
                        ActionButton {
                            visible: !!svc && svc.resolutionActive
                            text: "Restore display"
                            enabled: !!svc && panel.fresh && !svc.busy
                            onClicked: svc.restoreDisplay()
                        }
                    }
                    Card {
                        Layout.alignment: Qt.AlignTop
                        Layout.preferredWidth: 1
                        title: "Make it happen"
                        ActionButton {
                            Layout.fillWidth: true
                            text: panel.primaryLabel
                            prominent: true
                            enabled: !!svc && panel.fresh &&!svc.busy
                            onClicked: panel.primaryAction()
                        }
                        GridLayout {
                            Layout.fillWidth: true
                            columns: 2
                            rowSpacing: 8
                            columnSpacing: 8
                            ActionButton {
                                Layout.fillWidth: true
                                text: "Install"
                                enabled: !!svc && panel.fresh &&!svc.busy && (!svc.installed || !svc.qrAvailable)
                                onClicked: svc.installInTerminal()
                            }
                            ActionButton {
                                Layout.fillWidth: true
                                text: "Repair"
                                enabled: !!svc && panel.fresh &&!svc.busy && svc.installed
                                onClicked: svc.repair()
                            }
                            ActionButton {
                                Layout.fillWidth: true
                                text: "Ports"
                                enabled: !!svc && panel.fresh &&!svc.busy && svc.installed
                                onClicked: svc.ports()
                            }
                            ActionButton {
                                Layout.fillWidth: true
                                text: "Admin"
                                enabled: !!svc && panel.fresh &&!svc.busy && svc.adminUp
                                onClicked: svc.admin()
                            }
                            ActionButton {
                                Layout.fillWidth: true
                                text: "PIN page"
                                enabled: !!svc && panel.fresh &&!svc.busy && svc.adminConfigured && svc.adminUp
                                onClicked: svc.pinPage()
                            }
                            ActionButton {
                                Layout.fillWidth: true
                                text: "Remove"
                                danger: true
                                enabled: !!svc && panel.fresh &&!svc.busy && svc.installed
                                onClicked: panel.removeConfirmation = !panel.removeConfirmation
                            }
                        }
                        Caption {
                            visible: !panel.removeConfirmation
                            text: "Install, repair and removal open a terminal if your computer password is needed."
                        }
                        Caption {
                            visible: !panel.removeConfirmation
                            text: svc && svc.holdAwake ? "Automatic idle is held only during a live stream. Manual locking still hides the desktop." : "Awake hold is off. Automatic idle or locking can interrupt the picture."
                        }
                        ColumnLayout {
                            visible: panel.removeConfirmation
                            Layout.fillWidth: true
                            spacing: 8
                            Body {
                                text: "Remove Sunshine?"
                                font.bold: true
                                color: Color.urgent
                            }
                            Caption {
                                text: "Stops streaming, removes Sunshine, its login and pairings, and Beam's startup, web app and firewall changes. Paired iPads must pair again."
                            }
                            RowLayout {
                                Layout.fillWidth: true
                                ActionButton {
                                    Layout.fillWidth: true
                                    text: "Cancel"
                                    onClicked: panel.removeConfirmation = false
                                }
                                ActionButton {
                                    Layout.fillWidth: true
                                    text: "Remove Sunshine"
                                    danger: true
                                    enabled: !!svc && panel.fresh &&!svc.busy
                                    onClicked: {
                                        panel.removeConfirmation = false;
                                        svc.undo();
                                    }
                                }
                            }
                        }
                    }
                }
                Rectangle {
                    id: issueBox
                    visible: !!(svc && (svc.warning || !svc.statusFresh))
                    Layout.fillWidth: true
                    implicitHeight: issueText.implicitHeight + 18
                    radius: 6
                    color: Util.alpha(Color.urgent, 0.07)
                    border.width: 1
                    border.color: Util.alpha(Color.urgent, 0.35)
                    Caption {
                        id: issueText
                        x: 10
                        y: 9
                        width: parent.width - 20
                        text: svc ? (!svc.statusFresh ? (svc.statusMessage || "Checking fresh status. Actions resume when this computer responds.") : svc.warning) : ""
                        color: panel.foreground
                    }
                }
                Card {
                    id: actionReport
                    title: panel.report.title || (svc && svc.busy ? "Working" : "Ready when you are")
                    visible: panel.expertMode || panel.report.state !== "idle"
                    RowLayout {
                        Layout.fillWidth: true
                        spacing: 16
                        ColumnLayout {
                            Layout.fillWidth: true
                            spacing: 5
                            Caption {
                                text: panel.report.message || "Choose an action. Beam checks the result for you."
                            }
                            Caption {
                                visible: text !== ""
                                text: panel.report.next || ""
                                color: panel.foreground
                            }
                        }
                        ActionButton {
                            text: "Check again"
                            enabled: svc && !svc.busy
                            onClicked: if (svc)
                                svc.refresh()
                        }
                    }
                }
                RowLayout {
                    visible: !panel.expertMode
                    Layout.fillWidth: true
                    ActionButton {
                        text: "Back"
                        enabled: panel.stepNumber > 1
                        onClicked: panel.setStep(panel.stepNumber - 1)
                    }
                    Caption {
                        horizontalAlignment: Text.AlignHCenter
                        text: "Step " + panel.stepNumber + " of 6 · " + (panel.stepNumber === 3 ? "Confirm when Moonlight is installed." : "Your progress is checked live.")
                    }
                    ActionButton {
                        text: panel.stepNumber === 6 ? "Done" : panel.stepNumber === 3 ? "Moonlight is installed" : "Continue"
                        prominent: true
                        enabled: panel.canContinue
                        onClicked: panel.stepNumber === 6 ? panel.close() : panel.nextStep()
                    }
                }
                RowLayout {
                    Layout.fillWidth: true
                    Caption {
                        text: "Beam · Sunshine → Moonlight"
                    }
                    Caption {
                        Layout.fillWidth: false
                        text: "Tab / arrows to move · Enter to select · Esc to close"
                    }
                }
            }
        }
    }
    function firewallText() {
        if (!svc)
            return "Checking";
        if (!svc.ufwPresent)
            return "UFW not installed";
        if (svc.ufwStatus === "unknown")
            return "Not verified · use Ports";
        if (svc.ufwStatus === "inactive")
            return "UFW inactive";
        if (!svc.firewallReady)
            return String(svc.ufwRules) + " rules · incomplete; use Ports";
        return svc.ufwRules > 0 ? String(svc.ufwRules) + " Sunshine rules" : "Not verified · use Ports";
    }
    function settingsText() {
        if (!svc || !svc.encoder)
            return "Encoding: waiting for Sunshine's current log.";
        return svc.recommendedRes + " · " + svc.recommendedBitrate + " Mbps. " + svc.resolutionDetail;
    }

    Component {
        id: needsPage
        ColumnLayout {
            spacing: 16
            Heading {
                text: "Your desktop, on your iPad."
            }
            Body {
                text: "Sunshine sends this desktop. Moonlight shows it on the iPad."
            }
            RowLayout {
                Layout.fillWidth: true
                spacing: 12
                Card {
                    Layout.preferredWidth: 1
                    Layout.alignment: Qt.AlignTop
                    title: "An iPad"
                    Body {
                        text: "Install the free Moonlight app using the QR code in step 3."
                    }
                    Caption {
                        text: "For first pairing, use the same network as this computer."
                    }
                }
                Card {
                    Layout.preferredWidth: 1
                    Layout.alignment: Qt.AlignTop
                    title: "Mouse + keyboard"
                    Body {
                        text: "Both are required for the Beam desktop workflow."
                    }
                    Caption {
                        text: "Connect them to your iPad. Bluetooth is fine."
                    }
                }
                Card {
                    Layout.preferredWidth: 1
                    Layout.alignment: Qt.AlignTop
                    title: "A few minutes"
                    Body {
                        text: "Keep this Omarchy session open and unlocked."
                    }
                    Caption {
                        text: "Installation may ask for your computer password in a visible terminal."
                    }
                }
            }
            Caption {
                text: "Beam assumes this computer is reachable and helps prepare the streaming session."
            }
        }
    }
    Component {
        id: hostPage
        ColumnLayout {
            spacing: 14
            Heading {
                text: "Prepare this computer."
            }
            RowLayout {
                Layout.fillWidth: true
                spacing: 14
                Card {
                    Layout.preferredWidth: 1
                    Layout.alignment: Qt.AlignTop
                    title: "Live checks"
                    Check {
                        text: "Sunshine installed"
                        done: svc && svc.installed
                    }
                    Check {
                        text: "Firewall ready"
                        done: svc && svc.firewallReady
                        note: panel.firewallText()
                    }
                    Check {
                        text: "One startup path"
                        done: svc && svc.autostart && !svc.unitEnabled
                    }
                    Check {
                        text: "One Sunshine running"
                        done: svc && svc.processes === 1
                    }
                    Check {
                        text: "Display + iPad sizing"
                        done: svc && svc.displayFound && svc.resolutionReady
                    }
                }
                Card {
                    Layout.preferredWidth: 1
                    Layout.alignment: Qt.AlignTop
                    title: "One setup action"
                    accented: true
                    Body {
                        text: panel.hostReady ? "This computer is ready for Moonlight." : "Beam installs Sunshine and finishes the required setup."
                    }
                    ActionButton {
                        Layout.fillWidth: true
                        text: panel.hostReady && svc && svc.qrAvailable ? "Check again" : panel.primaryLabel
                        prominent: true
                        enabled: !!svc && panel.fresh &&!svc.busy
                        onClicked: panel.hostReady && svc.qrAvailable ? svc.refresh() : panel.primaryAction()
                    }
                    Caption {
                        text: "A terminal opens when needed. Enter your computer password there; Beam never sees it."
                    }
                    Body {
                        text: svc && svc.encoder ? "Sunshine reports: “" + svc.encoder + "”" : "Waiting for Sunshine to report its encoder."
                        font.pixelSize: panel.smallSize
                    }
                    Caption {
                        text: panel.settingsText()
                    }
                }
            }
        }
    }
    Component {
        id: ipadPage
        RowLayout {
            spacing: 28
            QrCode {
                size: 224
                text: panel.appUrl
                cli: svc ? svc.cli : ""
                active: panel.opened
                Layout.alignment: Qt.AlignVCenter
            }
            ColumnLayout {
                Layout.fillWidth: true
                spacing: 14
                Heading {
                    text: "Install Moonlight on your iPad."
                }
                Instruction {
                    number: 1
                    text: "Open the iPad Camera and scan this QR code."
                }
                Instruction {
                    number: 2
                    text: "Install Moonlight Game Streaming by Diego Waxemberg."
                }
                Instruction {
                    number: 3
                    text: "Open Moonlight and allow Local Network access when asked."
                }
                Caption {
                    text: "Free in the App Store · apps.apple.com/app/id1000551566"
                }
                Caption {
                    text: "Use a connected mouse and keyboard for your Beam desktop. Bluetooth is fine."
                }
                ActionButton {
                    text: "Open App Store page here"
                    enabled: !!svc && !svc.busy
                    onClicked: svc.moonlight()
                }
            }
        }
    }
    Component {
        id: loginPage
        ColumnLayout {
            spacing: 16
            Heading {
                text: "Create your Sunshine login."
            }
            RowLayout {
                Layout.fillWidth: true
                spacing: 14
                Card {
                    Layout.preferredWidth: 1
                    Layout.alignment: Qt.AlignTop
                    title: "A new login, just for Sunshine"
                    accented: true
                    Body {
                        text: "Choose a username and a new password on Sunshine's admin page."
                    }
                    Caption {
                        text: "Beam cannot see, store or recover this password."
                    }
                    ActionButton {
                        Layout.fillWidth: true
                        text: "Open Sunshine admin"
                        prominent: true
                        enabled: !!svc && panel.fresh &&svc.adminUp && !svc.busy
                        onClicked: svc.admin()
                    }
                    Check {
                        text: svc && svc.adminConfigured ? "Login created" : "Waiting for you to create a login"
                        done: svc && svc.adminConfigured
                    }
                }
                Card {
                    Layout.preferredWidth: 1
                    Layout.alignment: Qt.AlignTop
                    title: "About the certificate warning"
                    Body {
                        text: "Sunshine uses a local certificate, so your browser may show a privacy warning."
                    }
                    Caption {
                        text: "Check the page is " + (svc ? svc.adminUrl : "https://localhost:47990") + ", then use the browser's Advanced option to continue."
                    }
                    Caption {
                        text: "Return here after creating your login. Beam checks automatically."
                    }
                }
            }
        }
    }
    Component {
        id: connectPage
        RowLayout {
            spacing: 24
            ColumnLayout {
                Layout.preferredWidth: 260
                Layout.alignment: Qt.AlignTop
                spacing: 10
                QrCode {
                    size: 204
                    text: panel.connectionAddress
                    cli: svc ? svc.cli : ""
                    active: panel.opened
                    Layout.alignment: Qt.AlignHCenter
                }
                Body {
                    text: panel.connectionAddress || "No address available"
                    font.family: "monospace"
                    font.pixelSize: 21
                    font.bold: true
                    horizontalAlignment: Text.AlignHCenter
                }
                Caption {
                    text: "Scan to copy the address. Paste it into Moonlight's Add PC field."
                    horizontalAlignment: Text.AlignHCenter
                }
            }
            ColumnLayout {
                Layout.fillWidth: true
                spacing: 12
                Heading {
                    text: "Pair your iPad."
                }
                Caption {
                    text: "First pairing needs the iPad and computer on the same network. Allow Moonlight Local Network access."
                }
                Instruction {
                    number: 1
                    text: "Open Moonlight. Select this PC, or use + to add the address shown here."
                }
                Instruction {
                    number: 2
                    text: "Tap the PC. Moonlight shows a four-digit PIN."
                }
                Instruction {
                    number: 3
                    text: "Open the PIN page here and enter the PIN from the iPad."
                }
                Instruction {
                    number: 4
                    text: "In Moonlight, choose Full or Safe Area resolution, then tap Beam Desktop."
                }
                RowLayout {
                    Layout.fillWidth: true
                    ActionButton {
                        text: "Open PIN page"
                        prominent: true
                        enabled: !!svc && panel.fresh &&panel.connectionAddress !== "" && svc.adminUp && svc.adminConfigured && !svc.busy
                        onClicked: svc.pinPage()
                    }
                    Caption {
                        text: svc && svc.pairedClients > 0 ? "Paired ✓" : "Waiting for pairing"
                    }
                }
                Caption {
                    text: !panel.connectionAddress ? "No address is available. Beam cannot continue until this computer has one." : svc && svc.addressKind === "tailscale" && panel.connectionAddress === svc.address ? "Tailnet address: usable when the iPad already has access to this tailnet." : "Local address: use while the iPad can reach this network."
                }
            }
        }
    }
    Component {
        id: watchPage
        ColumnLayout {
            spacing: 16
            Heading {
                text: svc && svc.streaming ? "You're live." : "Open Moonlight. Tap Beam Desktop."
            }
            Caption {
                text: svc && svc.streaming ? "Sunshine is sending this desktop to Moonlight." : "Beam will light up when Sunshine detects a stream."
            }
            RowLayout {
                Layout.fillWidth: true
                spacing: 12
                Card {
                    Layout.preferredWidth: 1
                    Layout.alignment: Qt.AlignTop
                    title: "Picture settings"
                    accented: true
                    Body {
                        text: panel.settingsText()
                    }
                    Caption {
                        text: "Beam reads the iPad's requested size at connection. Unsupported modes use the closest fit."
                    }
                }
                Card {
                    Layout.preferredWidth: 1
                    Layout.alignment: Qt.AlignTop
                    title: "Keyboard + mouse"
                    Body {
                        text: "Both are required for your Beam desktop; Bluetooth is fine."
                    }
                    Caption {
                        text: "Moonlight sends the keyboard's Command key as Super."
                    }
                }
                Card {
                    Layout.preferredWidth: 1
                    Layout.alignment: Qt.AlignTop
                    title: "Stay awake"
                    Body {
                        text: svc && svc.holdAwake ? "Beam holds automatic idle while a stream is live." : "Awake hold is disabled in Beam settings."
                    }
                    Caption {
                        text: "Disconnecting releases the hold. If you manually lock, unlock this computer to restore the picture."
                    }
                }
            }
            Caption {
                text: "Ending the stream restores your display. After changing Moonlight resolution, quit the old session and reopen Beam Desktop."
            }
        }
    }
}
