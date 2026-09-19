import QtQuick
import Quickshell
import Quickshell.Io

// A QR code the iPad camera can read.
//
// This exists because the two worst moments in this setup are both typing on a
// touch keyboard: finding the right app in a store full of near-namesakes, and
// entering an IP address. A camera does both perfectly in a second.
//
// The PNG is rendered by qrencode through the CLI and cached by content, so
// reopening the wizard costs nothing.
Item {
  id: root
  property string text: ""
  property string cli: ""
  property int size: 160

  property string path: ""
  readonly property bool loaded: path !== ""

  implicitWidth: size
  implicitHeight: size

  onTextChanged: regen()
  onCliChanged: regen()
  Component.onCompleted: regen()

  function regen() {
    if (!text || !cli) { path = ""; return }
    gen.command = [cli, "qr", text]
    gen.running = true
  }

  Process {
    id: gen
    stdout: StdioCollector {
      waitForEnd: true
      onStreamFinished: {
        var p = String(text).trim()
        root.path = p ? p : ""
      }
    }
  }

  // White quiet zone always, in every theme. A QR on a dark themed background
  // with a themed foreground is a QR that phones refuse to read, and the user
  // has no way to know why.
  Rectangle {
    anchors.fill: parent
    radius: 6
    color: "#ffffff"
    border.width: 0
    visible: root.loaded

    Image {
      anchors.fill: parent
      anchors.margins: 4
      source: root.loaded ? "file://" + root.path : ""
      fillMode: Image.PreserveAspectFit
      smooth: false
      cache: true
    }
  }
}
