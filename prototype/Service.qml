import QtQuick
import Quickshell
import Quickshell.Io

// Everything Beam knows, from one poll of one CLI.
//
// The CLI in bin/omarchy-beam owns every fact and every action. This service
// only asks it for JSON and relays presses back, so the bar dot, the wizard and
// a terminal can never tell the user three different stories about how far the
// setup got.
//
// Nothing here knows what kind of machine it is on. Laptop, desktop, VM: if
// there is an Omarchy session with a display and an address, Beam works.
Item {
  id: root

  property var settings: ({})

  // The plugin ships its own CLI. Resolving it relative to this file keeps the
  // plugin portable: a hardcoded /home/<someone>/bin path works on exactly one
  // machine, and this one is meant for strangers.
  readonly property string cli: {
    var dir = Qt.resolvedUrl(".").toString().replace(/^file:\/\//, "").replace(/\/$/, "")
    return dir + "/bin/omarchy-beam"
  }

  property bool ready: false
  property bool installed: false
  property bool running: false
  property int processes: 0
  property string unit: ""
  property bool unitEnabled: false
  property int ufwRules: 0
  property bool ufwPresent: true
  property bool autostart: false
  property bool adminUp: false
  property bool adminConfigured: false
  property string adminUrl: "https://localhost:47990"
  property bool displayFound: false
  property string encoder: ""
  property string encoderKind: "unknown"
  property string recommendedRes: "1920x1080 · 60fps"
  property int recommendedBitrate: 20
  property int pairedClients: 0
  property bool streaming: false
  property bool locked: false
  property string address: ""
  property string addressKind: "none"
  property string lanAddress: ""
  property int nextStep: 1
  property bool allReady: false

  // Rolling output of the last action, shown in the expert pane's log box.
  property string log: ""
  property bool busy: false

  readonly property int refreshSec: {
    var n = parseInt(String(settings && settings.refreshSec !== undefined ? settings.refreshSec : 5), 10)
    return isFinite(n) ? Math.max(2, Math.min(120, n)) : 5
  }
  readonly property bool holdAwake: String(settings && settings.holdAwake !== undefined ? settings.holdAwake : true) !== "false"

  // Two Sunshines on one display, or a session that will lock mid-stream, are
  // the two states that look like a broken app and are neither. Name them.
  readonly property string warning: {
    if (installed && processes > 1) return "Two Sunshines are running. Repair fixes it."
    if (installed && unitEnabled && autostart) return "Both launchers are enabled. Repair fixes it."
    if (streaming && locked) return "The session is locked, so the iPad sees a black screen."
    if (installed && running && !displayFound) return "Sunshine has not captured a display yet."
    return ""
  }

  readonly property string state: {
    if (!ready) return "checking"
    if (!installed) return "setup"
    if (streaming) return "live"
    if (allReady) return "ready"
    return "setup"
  }

  function apply(text) {
    var d
    try { d = JSON.parse(text) } catch (e) { return }
    if (!d) return
    var wasStreaming = root.streaming

    installed = !!d.installed
    running = !!d.running
    processes = d.processes || 0
    unit = d.unit || ""
    unitEnabled = !!d.unitEnabled
    ufwRules = d.ufwRules || 0
    ufwPresent = !!d.ufwPresent
    autostart = !!d.autostart
    adminUp = !!d.adminUp
    adminConfigured = !!d.adminConfigured
    adminUrl = d.adminUrl || adminUrl
    displayFound = !!d.displayFound
    encoder = d.encoder || ""
    encoderKind = d.encoderKind || "unknown"
    recommendedRes = d.recommendedRes || recommendedRes
    recommendedBitrate = d.recommendedBitrate || recommendedBitrate
    pairedClients = d.pairedClients || 0
    streaming = !!d.streaming
    locked = !!d.locked
    address = d.address || ""
    addressKind = d.addressKind || "none"
    lanAddress = d.lanAddress || ""
    nextStep = d.nextStep || 1
    allReady = !!d.ready
    ready = true

    // Act on the EDGE, not on the level. Calling hold on every poll would run
    // two processes a second for as long as someone is watching a film.
    if (holdAwake && wasStreaming !== root.streaming) run(["hold", root.streaming ? "on" : "off"])
  }

  Process {
    id: poll
    command: [root.cli, "status"]
    stdout: StdioCollector { waitForEnd: true; onStreamFinished: root.apply(text) }
  }

  // Actions queue rather than drop. A first cut returned early while another
  // action ran, so a second click during an install simply vanished.
  property var pending: []

  Process {
    id: act
    stdout: StdioCollector { waitForEnd: true; onStreamFinished: root.append(text) }
    stderr: StdioCollector { waitForEnd: true; onStreamFinished: root.append(text) }
    onRunningChanged: {
      if (!running) { root.busy = false; root.drain(); settle.restart() }
    }
  }

  function append(text) {
    if (!text) return
    var t = String(text).trim()
    if (!t) return
    // Keep the tail only: the log box is a fixed height by design and an
    // unbounded string here is a slow leak on a long-lived shell.
    var lines = (root.log ? root.log + "\n" + t : t).split("\n")
    root.log = lines.slice(-200).join("\n")
  }

  function drain() {
    if (act.running) return
    var q = root.pending
    if (!q || q.length === 0) return
    // Never mutate a QML var array in place: shift() hands back the item but
    // leaves the property on the original array, so the queue never empties.
    var next = q[0]
    root.pending = q.slice(1)
    act.command = next
    root.busy = true
    act.running = true
  }

  function run(args) {
    var cmd = [root.cli].concat(args)
    var q = root.pending.slice(-3)
    q.push(cmd)
    root.pending = q
    drain()
  }

  function refresh() { if (!poll.running) poll.running = true }
  function clearLog() { root.log = "" }

  function repair()  { append("$ omarchy-beam repair");  run(["repair"]) }
  function ports()   { append("$ omarchy-beam ports");   run(["ports"]) }
  function admin()   { run(["admin"]) }
  function pinPage() { run(["pin"]) }
  function undo()    { append("$ omarchy-beam undo");    run(["undo"]) }

  // The install needs root and prints as it goes, so it belongs in a real
  // terminal the human can watch and type a password into. Beam handles no
  // password itself, and a progress bar in a panel would only hide the part
  // that actually needs a person.
  function installInTerminal() {
    append("$ omarchy-beam install   (opened in a terminal)")
    Quickshell.execDetached(["omarchy-launch-floating-terminal-with-presentation",
                             root.cli, "install"])
    installWatch.restart()
  }

  // An install takes a while and ends outside our process, so poll faster for a
  // couple of minutes rather than making the user close and reopen the wizard.
  Timer {
    id: installWatch
    interval: 2000; repeat: true; running: false
    property int ticks: 0
    onRunningChanged: if (running) ticks = 0
    onTriggered: { ticks++; root.refresh(); if (ticks > 90) running = false }
  }

  Timer { id: settle; interval: 900; onTriggered: root.refresh() }

  // Twice as fast while something is live or mid-change, idle otherwise.
  Timer {
    interval: (root.streaming || root.busy ? 2 : root.refreshSec) * 1000
    running: true
    repeat: true
    triggeredOnStart: true
    onTriggered: root.refresh()
  }

  // Someone who installs a plugin and is then told nothing has no way to find
  // it. One notification, once, and only when there is genuinely nothing set
  // up. The CLI owns the marker so it cannot fire twice.
  Timer {
    interval: 4000; running: true; repeat: false
    onTriggered: root.run(["greet"])
  }
}
