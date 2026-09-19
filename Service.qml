import QtQuick
import Quickshell
import Quickshell.Io
import "ServiceState.js" as State

Item {
    id: root
    property var settings: ({})
    readonly property string cli: decodeURIComponent(Qt.resolvedUrl("bin/omarchy-beam").toString().replace(/^file:\/\//, ""))
    property var snapshot: ({})
    property bool ready: false
    property double lastSuccess: 0
    property double now: Date.now()
    property string pollError: ""
    property bool pollInFlight: false
    property bool actionInFlight: false
    property bool terminalPending: false
    property double actionRequestedAt: 0
    property var pending: []
    property var currentArgs: []
    property var actionReport: ({state: "idle", title: "Ready to help", message: "Choose an action when you need it.", next: "", retryAction: ""})

    readonly property int refreshSec: {
        var value = Number(settings.refreshSec === undefined ? 5 : settings.refreshSec)
        return isFinite(value) ? Math.max(2, Math.min(120, value)) : 5
    }
    readonly property bool holdAwake: settings.holdAwake !== false && settings.holdAwake !== "false"
    readonly property bool statusFresh: State.fresh(lastSuccess, now, refreshSec, pollError !== "")
    readonly property string statusMessage: pollError || (!ready ? "Checking this computer..." : !statusFresh ? "Status is out of date. Check again." : "")
    readonly property bool installed: snapshot.installed === true
    readonly property string version: String(snapshot.version || "")
    readonly property bool running: statusFresh && snapshot.running === true
    readonly property int processes: Number(snapshot.processes || 0)
    readonly property string unit: String(snapshot.unit || "")
    readonly property bool unitEnabled: snapshot.unitEnabled === true
    readonly property int ufwRules: Number(snapshot.ufwRules || 0)
    readonly property bool ufwPresent: snapshot.ufwPresent === true
    readonly property string firewallState: String(snapshot.firewallState || "unknown")
    readonly property bool firewallKnown: snapshot.firewallKnown === true
    readonly property bool firewallReady: snapshot.firewallReady === true
    readonly property string ufwState: firewallState
    readonly property string ufwStatus: firewallState
    readonly property bool setupReady: statusFresh && snapshot.setupReady === true
    readonly property bool autostart: snapshot.autostart === true
    readonly property bool adminUp: statusFresh && snapshot.adminUp === true
    readonly property bool adminConfigured: snapshot.adminConfigured === true
    readonly property string adminUrl: String(snapshot.adminUrl || "https://localhost:47990")
    readonly property bool displayFound: statusFresh && snapshot.displayFound === true
    readonly property string encoder: String(snapshot.encoder || "")
    readonly property string encoderKind: String(snapshot.encoderKind || "unknown")
    readonly property string recommendedRes: String(snapshot.recommendedRes || "Full · 60 fps")
    readonly property string resolutionDetail: String(snapshot.resolutionDetail || "Choose Full in Moonlight.")
    readonly property bool resolutionActive: snapshot.resolutionActive === true
    readonly property string moonlightSetting: String(snapshot.moonlightSetting || "Full")
    readonly property bool resolutionReady: snapshot.resolutionReady === true
    readonly property bool nativeResolution: snapshot.nativeResolution === true
    readonly property var ipadProfiles: snapshot.ipadProfiles || []
    readonly property string ipadProfile: String(snapshot.ipadProfile || "")
    readonly property int recommendedBitrate: Number(snapshot.recommendedBitrate || 20)
    readonly property int pairedClients: Number(snapshot.pairedClients || 0)
    readonly property bool streaming: statusFresh && snapshot.streaming === true && running && processes > 0
    readonly property bool locked: snapshot.locked === true
    readonly property string address: String(snapshot.address || "")
    readonly property string addressKind: String(snapshot.addressKind || "none")
    readonly property string lanAddress: String(snapshot.lanAddress || "")
    readonly property string hostName: String(snapshot.hostName || "This computer")
    readonly property int nextStep: Number(snapshot.nextStep || 2)
    readonly property bool allReady: statusFresh && snapshot.ready === true
    readonly property bool inputReady: snapshot.inputReady === true
    readonly property bool qrAvailable: snapshot.qrAvailable === true
    readonly property var checks: Array.isArray(snapshot.checks) ? snapshot.checks : []
    readonly property var issues: Array.isArray(snapshot.issues) ? snapshot.issues : []
    readonly property bool busy: actionInFlight || terminalPending || snapshot.actionBusy === true
    readonly property string warning: {
        if (statusMessage) return statusMessage
        if (streaming && locked) return "Unlock this computer to show its desktop."
        if (processes > 1) return "More than one Sunshine process is running. Open Repair."
        for (var i = 0; i < issues.length; i++) {
            var issue = issues[i]
            var code = typeof issue === "string" ? "" : String(issue.code || "")
            if (code === "missing" || code === "qr") continue
            return typeof issue === "string" ? issue : String(issue.message || issue.detail || issue.label || "Setup needs attention.")
        }
        return ""
    }
    readonly property string state: !ready ? "checking" : !statusFresh ? "error" : streaming ? "live" : allReady ? "ready" : "setup"

    function failPoll(message) {
        pollInFlight = false
        pollError = message
        now = Date.now()
    }

    function apply(text) {
        try {
            var data = State.decodeStatus(text)
            snapshot = data
            lastSuccess = Date.now()
            now = lastSuccess
            pollError = ""
            ready = true
            var actionAt = State.actionTime(data.lastAction)
            if (actionAt > 0 && actionAt >= actionRequestedAt) {
                actionReport = State.report(data.lastAction)
                terminalPending = data.actionBusy === true
            }
            if (!data.actionBusy && terminalPending && Date.now() - actionRequestedAt > 10000)
                terminalPending = false
        } catch (e) {
            failPoll("Beam could not read its status. Check again.")
        }
    }

    function refresh() {
        if (pollInFlight) return
        pollInFlight = true
        poll.launched = false
        poll.stdoutText = ""
        poll.running = true
        pollDeadline.restart()
    }

    Process {
        id: poll
        command: [root.cli, "status"]
        property bool launched: false
        property string stdoutText: ""
        stdout: StdioCollector { waitForEnd: true; onStreamFinished: poll.stdoutText = text }
        onStarted: launched = true
        onRunningChanged: {
            if (!running && !launched && root.pollInFlight) {
                pollDeadline.stop()
                root.failPoll("Beam's helper could not start. Check that Python 3 is installed.")
            }
        }
        onExited: function(code) {
            pollDeadline.stop()
            if (!root.pollInFlight) return
            Qt.callLater(function() {
                if (code === 0) root.apply(poll.stdoutText)
                else root.failPoll("Beam's status check failed. Check again.")
                root.pollInFlight = false
            })
        }
    }
    Timer {
        id: pollDeadline
        interval: 15000
        onTriggered: {
            root.failPoll("The status check took too long. Check again.")
            poll.running = false
        }
    }

    function actionError(message, retryAction) {
        actionReport = {state: "error", title: "Action needs attention", message: message,
                        next: "", retryAction: retryAction || ""}
    }

    function run(args) {
        if (!args || args.length === 0) return
        var queue = State.enqueue(pending, args, 4)
        if (queue === null) {
            actionError("Finish the current action before starting another.", "")
            return
        }
        pending = queue
        drain()
    }

    function drain() {
        if (actionInFlight || pending.length === 0) return
        currentArgs = pending[0]
        pending = pending.slice(1)
        actionInFlight = true
        act.launched = false
        act.stdoutText = ""
        if (currentArgs[0] !== "greet") {
            actionRequestedAt = Date.now()
            actionReport = {state: "working", title: "Working", message: "Opening the next step...", next: "", retryAction: ""}
        }
        act.command = [cli].concat(currentArgs)
        act.running = true
        actionDeadline.restart()
    }

    function finishAction(code) {
        if (!actionInFlight) return
        actionInFlight = false
        if (currentArgs[0] !== "greet") {
            try {
                var result = JSON.parse(act.stdoutText)
                actionReport = State.report(result, currentArgs[currentArgs.length - 1])
                if (code !== 0 && result.ok === true)
                    actionError("The action ended unexpectedly. Check its terminal for details.", "")
                terminalPending = currentArgs[0] === "terminal" && result.ok === true && actionReport.state === "working"
            } catch (e) {
                actionError("The action returned no usable result. Check its terminal for details.", "")
                terminalPending = false
            }
        }
        settle.restart()
        Qt.callLater(drain)
    }

    Process {
        id: act
        property bool launched: false
        property string stdoutText: ""
        stdout: StdioCollector { waitForEnd: true; onStreamFinished: act.stdoutText = text }
        onStarted: launched = true
        onRunningChanged: {
            if (!running && !launched && root.actionInFlight) {
                actionDeadline.stop()
                root.actionInFlight = false
                root.terminalPending = false
                if (root.currentArgs[0] !== "greet")
                    root.actionError("Beam's helper could not start. Check that Python 3 is installed.", "")
                Qt.callLater(root.drain)
            }
        }
        onExited: function(code) {
            actionDeadline.stop()
            Qt.callLater(function() { root.finishAction(code) })
        }
    }
    Timer {
        id: actionDeadline
        interval: 15000
        onTriggered: {
            root.actionInFlight = false
            root.terminalPending = false
            act.running = false
            root.actionError("The action took too long. Check its terminal before trying again.", "")
            root.refresh()
            Qt.callLater(root.drain)
        }
    }

    function terminal(action) {
        if (busy || pending.some(function(args) { return args[0] === "terminal" })) return
        run(["terminal", action])
    }
    function installInTerminal() { terminal("install") }
    function repair() { terminal("repair") }
    function ports() { terminal("ports") }
    function undo() { terminal("undo") }
    function admin() { run(["admin"]) }
    function pinPage() { run(["pin"]) }
    function moonlight() { run(["moonlight"]) }
    function copyAddress() { run(["copy-address"]) }
    function restoreDisplay() { run(["restore-display"]) }
    function selectIpad(identifier) { run(["select-ipad", identifier]) }
    function useMoonlightFull() { run(["set-resolution", "auto"]) }
    function retry() {
        var action = actionReport.retryAction
        if (["install", "repair", "ports", "undo"].indexOf(action) >= 0) terminal(action)
        else if (["admin", "pin", "moonlight", "copy-address", "restore-display"].indexOf(action) >= 0) run([action])
        else refresh()
    }
    function clearReport() {
        if (busy) return
        actionRequestedAt = Date.now()
        actionReport = {state: "idle", title: "Ready to help", message: "Choose an action when you need it.", next: "", retryAction: ""}
    }

    Timer { interval: 1000; running: true; repeat: true; onTriggered: root.now = Date.now() }
    Timer { id: settle; interval: 600; onTriggered: root.refresh() }
    Timer {
        interval: (root.streaming || root.busy ? 2 : root.refreshSec) * 1000
        running: true; repeat: true; triggeredOnStart: true
        onTriggered: root.refresh()
    }
    Timer { interval: 4000; running: true; onTriggered: root.run(["greet"]) }
}
