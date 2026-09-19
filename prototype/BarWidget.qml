import QtQuick
import Quickshell
import Quickshell.Io
import qs.Commons
import qs.Ui

// A dot that answers one question without being asked: can an iPad watch this
// desktop right now, and is one watching?
//
// Grey with a dot-and-dash means nothing is set up yet, and that is the state a
// brand new user sees. It is deliberately not invisible: the whole discovery
// problem with a plugin like this is that installing it tells you nothing about
// what to do next.
BarWidget {
  id: root
  moduleName: "nixfred.beam"
  property var anchorItem: button

  readonly property var svc: bar && bar.shell ? bar.shell.serviceFor(moduleName) : null
  readonly property bool ready: svc ? svc.ready : false
  readonly property string state: svc ? svc.state : "checking"
  readonly property bool streaming: svc ? svc.streaming : false
  readonly property string warning: svc ? svc.warning : ""

  function setting(name, fallback) {
    var v = settings ? settings[name] : undefined
    return v === undefined ? fallback : v
  }
  readonly property bool showLabel: String(setting("showLabel", true)) !== "false"

  readonly property color foreground: bar ? bar.foreground : Color.foreground

  readonly property color dotColor: {
    if (warning) return Color.warning !== undefined ? Color.warning : "#e0a030"
    switch (state) {
      case "live":  return Color.accent
      case "ready": return Util.alpha(foreground, 0.75)
      case "setup": return Util.alpha(foreground, 0.30)
      default:      return Util.alpha(foreground, 0.30)
    }
  }

  readonly property string label: {
    if (warning) return "check"
    switch (state) {
      case "live":  return "live"
      case "ready": return "iPad"
      case "setup": return "set up"
      default:      return ""
    }
  }

  readonly property real contentWidth: Style.space(showLabel ? 54 : 24)

  implicitWidth: vertical ? barSize : contentWidth
  implicitHeight: vertical ? contentWidth : barSize

  WidgetButton {
    id: button
    anchors.fill: parent
    bar: root.bar
    text: ""
    labelVisible: false
    // WidgetButton has no contentItem: children go straight in, and this flag
    // is what tells it there is something to show despite the empty label.
    hasVisualContent: true
    active: false
    useActiveColor: false
    tooltipText: {
      if (!root.ready) return "Beam — checking"
      if (root.warning) return "Beam — " + root.warning
      switch (root.state) {
        case "live":  return "Beam — an iPad is watching this desktop"
        case "ready": return "Beam — ready. Open Moonlight on the iPad."
        default:      return "Beam — not set up yet. Click to start."
      }
    }

    Row {
      anchors.centerIn: parent
      spacing: Style.space(5)

      Item {
        width: Style.space(18)
        height: Style.space(18)
        anchors.verticalCenter: parent.verticalCenter

        // A plain scaled circle at low opacity rather than a blur: a blur on a
        // bar widget repaints every frame and is not worth the GPU at 18px.
        Rectangle {
          visible: root.streaming
          anchors.centerIn: parent
          width: parent.width * 1.6
          height: width
          radius: width / 2
          color: root.dotColor
          border.width: 0
          opacity: pulse.value
          NumberAnimation on opacity { id: pulse; property real value: 0.28
            running: root.streaming; loops: Animation.Infinite
            from: 0.10; to: 0.34; duration: 1400; easing.type: Easing.InOutSine }
        }

        Rectangle {
          anchors.centerIn: parent
          width: parent.width * 0.6
          height: width
          radius: width / 2
          color: root.dotColor
          // Rectangle border defaults to width 1 even when never set, so the
          // hairline has to be pinned off explicitly.
          border.width: 0
          Behavior on color { ColorAnimation { duration: 400 } }
        }
      }

      Text {
        visible: root.showLabel
        anchors.verticalCenter: parent.verticalCenter
        text: root.label
        color: root.state === "setup" ? Util.alpha(root.foreground, 0.55) : root.foreground
        font.family: root.bar ? root.bar.fontFamily : Style.font.family
        font.pixelSize: Style.font.bodySmall
      }
    }

    onPressed: function(code) {
      if (root.bar) root.bar.hideTooltip(root)
      root.toggle()
    }
  }

  readonly property bool opened: panel.opened
  function open() { panel.controller.show(); if (svc) svc.refresh() }
  function close() { panel.controller.hide() }
  function toggle() { opened ? close() : open() }
  function closeForPopoutSwitch() { close() }
  readonly property bool popoutSwitchClosing: false

  BeamPanel {
    id: panel
    widget: root
  }
}
