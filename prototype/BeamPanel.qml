import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import Quickshell
import Quickshell.Io
import qs.Commons
import qs.Ui

// Two ways through the same job.
//
// Guided is for someone who has just installed this and has no idea what
// happens next: one screen, one instruction, one button, and the wizard opens
// on whichever step is actually outstanding rather than always at the start.
//
// Expert is one screen with every fact and every action on it, for someone who
// has done this before and wants the thing done.
//
// Neither mode scrolls. The wizard fits because it shows one step at a time;
// expert fits because it is two dense columns. The only scroller in here is the
// log box, which scrolls inside itself while the panel around it stays still.
Panel {
  id: panel
  moduleName: "nixfred.beam"
  manageIpc: false

  required property var widget
  readonly property var svc: widget.svc

  readonly property color foreground: widget.bar ? widget.bar.foreground : Color.foreground
  readonly property color dim: Qt.darker(foreground, 1.5)
  readonly property color faint: Util.alpha(foreground, 0.10)
  readonly property string fontFamily: widget.bar ? widget.bar.fontFamily : Style.font.family
  readonly property color good: Color.accent

  readonly property int panelWidth: Style.space(1120)

  property bool expert: false
  property int step: 1
  // Opening on the first unfinished step is the difference between a wizard and
  // a slideshow. Someone who got as far as pairing yesterday should not have to
  // click through three screens of things they already did.
  property bool stepPinned: false

  readonly property string moonlightUrl: "https://apps.apple.com/app/id1000551566"

  onOpenedChanged: {
    if (!opened) { stepPinned = false; return }
    if (svc) { svc.refresh(); if (!stepPinned) step = Math.max(1, Math.min(6, svc.nextStep)) }
  }

  Connections {
    target: svc
    function onNextStepChanged() {
      // Advance under the user only when they have not taken the wheel, and
      // only forwards. Yanking someone back a step because a poll landed mid
      // action is worse than showing a stale screen for two seconds.
      if (!panel.stepPinned && panel.opened && svc.nextStep > panel.step)
        panel.step = Math.min(6, svc.nextStep)
    }
  }

  readonly property var stepTitles: ["", "What you need", "This computer", "The iPad app",
                                     "Your login", "Connect", "Watch"]

  function go(n) { step = Math.max(1, Math.min(6, n)); stepPinned = true }

  KeyboardPanel {
    id: kpanel
    anchorItem: panel.widget.anchorItem
    owner: panel.widget
    bar: panel.widget.bar
    open: panel.opened
    focusTarget: keyCatcher
    contentWidth: kpanel.fittedContentWidth(panel.panelWidth)
    contentHeight: kpanel.fittedContentHeight(content.implicitHeight, Style.space(640))

    PanelKeyCatcher {
      id: keyCatcher
      anchors.fill: parent
      onCloseRequested: panel.widget.close()

      ColumnLayout {
        id: content
        width: parent.width
        spacing: Style.space(12)

        // ---------------------------------------------------------- header
        RowLayout {
          Layout.fillWidth: true
          spacing: Style.space(10)

          Rectangle {
            width: Style.space(14); height: width; radius: width / 2
            border.width: 0
            color: svc && svc.streaming ? panel.good
                 : svc && svc.allReady ? Util.alpha(panel.foreground, 0.75)
                 : Util.alpha(panel.foreground, 0.3)
            Behavior on color { ColorAnimation { duration: 400 } }
          }

          Text {
            text: "Beam"
            color: panel.foreground
            font.family: panel.fontFamily
            font.pixelSize: Style.font.subtitle
            font.bold: true
          }

          Text {
            text: !svc || !svc.ready ? "checking this machine"
                : svc.streaming ? "an iPad is watching this desktop"
                : svc.allReady ? "ready. Open Moonlight on the iPad."
                : "not set up yet"
            color: panel.dim
            font.family: panel.fontFamily
            font.pixelSize: Style.font.bodySmall
          }

          Item { Layout.fillWidth: true }

          Text {
            visible: svc && svc.warning !== ""
            text: svc ? svc.warning : ""
            color: panel.foreground
            font.family: panel.fontFamily
            font.pixelSize: Style.font.bodySmall
          }

          BeamButton {
            label: panel.expert ? "Guided" : "Expert"
            subtle: true
            onActivated: panel.expert = !panel.expert
          }
        }

        Rectangle { Layout.fillWidth: true; height: 1; color: panel.faint; border.width: 0 }

        // ------------------------------------------------------ step rail
        // Clickable, because a wizard that will not let you go back and look at
        // something is a wizard people fight with.
        RowLayout {
          visible: !panel.expert
          Layout.fillWidth: true
          spacing: Style.space(6)

          Repeater {
            model: 6
            delegate: Rectangle {
              required property int index
              readonly property int n: index + 1
              readonly property bool here: panel.step === n
              readonly property bool done: svc ? svc.nextStep > n : false

              Layout.fillWidth: true
              Layout.preferredWidth: 1
              implicitHeight: Style.space(30)
              radius: Style.space(6)
              border.width: here ? 2 : 1
              border.color: here ? panel.good : panel.faint
              color: here ? Util.alpha(panel.good, 0.14)
                   : done ? Util.alpha(panel.foreground, 0.05) : "transparent"

              Text {
                anchors.centerIn: parent
                text: (done && !here ? "✓  " : n + ".  ") + panel.stepTitles[n]
                color: here ? panel.foreground : panel.dim
                font.family: panel.fontFamily
                font.pixelSize: Style.font.bodySmall
                font.bold: here
                elide: Text.ElideRight
              }

              MouseArea {
                anchors.fill: parent
                cursorShape: Qt.PointingHandCursor
                onClicked: panel.go(n)
              }
            }
          }
        }

        // ------------------------------------------------------- the body
        // One fixed-height stage. Every step draws inside it, so the panel does
        // not jump size as you move through, and nothing ever needs a scrollbar.
        Item {
          visible: !panel.expert
          Layout.fillWidth: true
          implicitHeight: Style.space(330)

          // ---- 1. what you need
          ColumnLayout {
            anchors.fill: parent
            visible: panel.step === 1
            spacing: Style.space(10)

            BeamHeading { text: "Put this desktop on your iPad" }
            BeamBody {
              text: "Beam sets up two free pieces of software: Sunshine on this machine, which "
                  + "sends the picture, and Moonlight on the iPad, which shows it. It works the "
                  + "same whether this is a laptop, a desktop or a virtual machine."
            }

            GridLayout {
              Layout.fillWidth: true
              columns: 3
              columnSpacing: Style.space(10)
              rowSpacing: Style.space(10)

              BeamCard { title: "An iPad"; body: "Any iPad running a current iPadOS. A keyboard is optional and works well." }
              BeamCard { title: "A few minutes"; body: "Five, most of it waiting for a package to install." }
              BeamCard { title: "Your password"; body: "Once, in a terminal you can see. Beam never asks for it and never stores it." }
            }

            Item { Layout.fillHeight: true }

            BeamBody {
              text: "Beam assumes the iPad can already reach this machine. Getting them onto the "
                  + "same network is not something it tries to do for you."
              faded: true
            }
          }

          // ---- 2. this computer
          ColumnLayout {
            anchors.fill: parent
            visible: panel.step === 2
            spacing: Style.space(10)

            BeamHeading { text: "Set up this computer" }
            BeamBody {
              text: "This installs Sunshine, opens the ports it needs on your local network only, "
                  + "and starts it with your desktop from now on. It opens a terminal so you can "
                  + "watch it and type your password."
            }

            RowLayout {
              Layout.fillWidth: true
              spacing: Style.space(8)

              BeamCheck { ok: svc ? svc.installed : false; label: "Sunshine installed" }
              BeamCheck { ok: svc ? (svc.ufwRules > 0 || !svc.ufwPresent) : false; label: "Ports open" }
              BeamCheck { ok: svc ? svc.autostart : false; label: "Starts with the desktop" }
              BeamCheck { ok: svc ? svc.running : false; label: "Running now" }
              BeamCheck { ok: svc ? svc.displayFound : false; label: "Screen captured" }
            }

            RowLayout {
              Layout.fillWidth: true
              spacing: Style.space(8)

              BeamButton {
                label: svc && svc.installed ? "Run it again" : "Set up this computer"
                primary: !(svc && svc.installed)
                onActivated: if (svc) svc.installInTerminal()
              }
              BeamButton {
                label: "Fix what is missing"
                visible: svc && svc.installed
                onActivated: if (svc) svc.repair()
              }
              Item { Layout.fillWidth: true }
              Text {
                visible: svc && svc.version !== ""
                text: svc ? svc.version : ""
                color: panel.dim
                font.family: panel.fontFamily
                font.pixelSize: Style.font.bodySmall
              }
            }

            Item { Layout.fillHeight: true }

            // The encoder question decides what settings to use on the iPad, and
            // it cannot be answered by looking for a GPU: a virtual machine can
            // show a render node that cannot encode a single frame. Sunshine's
            // own log is the only honest source, so it is quoted, not guessed.
            Rectangle {
              Layout.fillWidth: true
              implicitHeight: Style.space(56)
              radius: Style.space(8)
              border.width: 1
              border.color: panel.faint
              color: "transparent"
              visible: svc && svc.installed

              RowLayout {
                anchors.fill: parent
                anchors.margins: Style.space(10)
                spacing: Style.space(10)

                ColumnLayout {
                  spacing: 0
                  Text {
                    text: svc && svc.encoderKind === "hardware" ? "Hardware video encoding"
                        : svc && svc.encoderKind === "software" ? "Software video encoding"
                        : "Video encoding not detected yet"
                    color: panel.foreground
                    font.family: panel.fontFamily
                    font.pixelSize: Style.font.body
                    font.bold: true
                  }
                  Text {
                    text: svc && svc.encoder ? "Sunshine reports " + svc.encoder
                        : "Start Sunshine and this fills in from its own log."
                    color: panel.dim
                    font.family: panel.fontFamily
                    font.pixelSize: Style.font.bodySmall
                  }
                }
                Item { Layout.fillWidth: true }
                Text {
                  visible: svc && svc.encoder !== ""
                  text: "Use " + (svc ? svc.recommendedRes : "")
                  color: panel.foreground
                  font.family: panel.fontFamily
                  font.pixelSize: Style.font.bodySmall
                }
              }
            }
          }

          // ---- 3. the iPad app
          RowLayout {
            anchors.fill: parent
            visible: panel.step === 3
            spacing: Style.space(20)

            ColumnLayout {
              Layout.fillWidth: true
              spacing: Style.space(10)

              BeamHeading { text: "Get Moonlight on the iPad" }
              BeamBody {
                text: "Point the iPad's camera at this code and tap the banner that appears. It "
                    + "opens Moonlight Game Streaming in the App Store, which is free."
              }
              BeamBody {
                text: "There are several apps with similar names. The one you want is by Diego "
                    + "Waxemberg. The code goes straight to it, so there is nothing to search for."
                faded: true
              }
              Item { Layout.fillHeight: true }
              BeamBody { text: "Install it, then come back here."; }
            }

            QrCode {
              Layout.alignment: Qt.AlignVCenter
              size: Style.space(200)
              cli: svc ? svc.cli : ""
              text: panel.moonlightUrl
            }
          }

          // ---- 4. the login
          ColumnLayout {
            anchors.fill: parent
            visible: panel.step === 4
            spacing: Style.space(10)

            BeamHeading { text: "Create your Sunshine login" }
            BeamBody {
              text: "Sunshine keeps its own username and password, which guard the page that "
                  + "approves new devices. You create it, in your browser. Beam does not choose "
                  + "it, does not see it, and cannot recover it, so pick something you will "
                  + "remember or write it down."
            }
            BeamBody {
              text: "Your browser will warn that the page is not trusted. That is expected: the "
                  + "page is on this machine and its certificate is self-signed. Continue past it."
              faded: true
            }

            RowLayout {
              Layout.fillWidth: true
              spacing: Style.space(8)
              BeamButton {
                label: "Open the login page"
                primary: !(svc && svc.adminConfigured)
                onActivated: if (svc) svc.admin()
              }
              BeamCheck { ok: svc ? svc.adminConfigured : false; label: "Login created" }
              Item { Layout.fillWidth: true }
              Text {
                text: svc ? svc.adminUrl : ""
                color: panel.dim
                font.family: panel.fontFamily
                font.pixelSize: Style.font.bodySmall
              }
            }

            Item { Layout.fillHeight: true }
          }

          // ---- 5. connect
          RowLayout {
            anchors.fill: parent
            visible: panel.step === 5
            spacing: Style.space(20)

            ColumnLayout {
              Layout.fillWidth: true
              spacing: Style.space(8)

              BeamHeading { text: "Connect the iPad" }

              BeamStep { n: 1; text: "Open Moonlight on the iPad and tap the + in the corner." }
              BeamStep { n: 2; text: "Scan this code with the iPad camera, or type the address below." }
              BeamStep { n: 3; text: "Moonlight shows a four digit PIN. Type it on the page this opens." }
              BeamStep { n: 4; text: "Tap this computer in Moonlight, then tap Desktop." }

              RowLayout {
                Layout.fillWidth: true
                spacing: Style.space(8)

                Rectangle {
                  implicitWidth: addr.implicitWidth + Style.space(20)
                  implicitHeight: Style.space(38)
                  radius: Style.space(6)
                  border.width: 1
                  border.color: panel.faint
                  color: Util.alpha(panel.foreground, 0.04)
                  Text {
                    id: addr
                    anchors.centerIn: parent
                    text: svc && svc.address ? svc.address : "no address"
                    color: panel.foreground
                    font.family: "monospace"
                    font.pixelSize: Style.font.subtitle
                    font.bold: true
                  }
                }

                BeamButton {
                  label: "Enter the PIN"
                  primary: true
                  onActivated: if (svc) svc.pinPage()
                }
                BeamCheck { ok: svc ? svc.pairedClients > 0 : false
                            label: svc && svc.pairedClients > 0
                                   ? svc.pairedClients + " paired" : "none paired" }
              }

              Text {
                // Which address this is matters. A tailnet address keeps working
                // from a coffee shop; a LAN address stops at the front door.
                text: svc && svc.addressKind === "tailscale"
                      ? "This is your Tailscale address, so it works from anywhere the iPad has signal."
                      : svc && svc.addressKind === "lan"
                        ? "This is a local network address, so it works while the iPad is on the same network."
                        : "No address found. This machine needs to be on a network."
                color: panel.dim
                font.family: panel.fontFamily
                font.pixelSize: Style.font.bodySmall
                wrapMode: Text.WordWrap
                Layout.fillWidth: true
              }

              Item { Layout.fillHeight: true }
            }

            QrCode {
              Layout.alignment: Qt.AlignVCenter
              size: Style.space(200)
              cli: svc ? svc.cli : ""
              text: svc && svc.address ? svc.address : ""
            }
          }

          // ---- 6. watch
          ColumnLayout {
            anchors.fill: parent
            visible: panel.step === 6
            spacing: Style.space(10)

            BeamHeading {
              text: svc && svc.streaming ? "Your iPad is watching this desktop"
                                         : "Ready when you are"
            }
            BeamBody {
              text: svc && svc.streaming
                    ? "Everything is working. These settings are worth knowing."
                    : "Setup is finished. Open Moonlight on the iPad, tap this computer, then tap Desktop."
            }

            GridLayout {
              Layout.fillWidth: true
              columns: 3
              columnSpacing: Style.space(10)
              rowSpacing: Style.space(10)

              BeamCard {
                title: "Settings to use"
                body: svc ? svc.recommendedRes + ", around " + svc.recommendedBitrate + " Mbps"
                          : ""
              }
              BeamCard {
                title: "The keyboard"
                body: "Moonlight sends Cmd as Super, which is the key Omarchy uses for nearly everything."
              }
              BeamCard {
                title: "Staying awake"
                body: svc && svc.holdAwake
                      ? "Beam holds this session awake while the iPad is connected, and lets it idle again after."
                      : "Awake-holding is off, so a locked session will show the iPad a black screen."
              }
            }

            Item { Layout.fillHeight: true }

            BeamBody {
              text: "To stop, end the stream from Moonlight's own menu. Nothing here needs turning off."
              faded: true
            }
          }
        }

        // ------------------------------------------------------ expert mode
        // Everything on one screen, two columns, nothing behind a gesture. The
        // log box is the only thing that scrolls, and it scrolls inside itself.
        RowLayout {
          visible: panel.expert
          Layout.fillWidth: true
          spacing: Style.space(14)

          ColumnLayout {
            Layout.fillWidth: true
            Layout.preferredWidth: 1
            Layout.alignment: Qt.AlignTop
            spacing: Style.space(6)

            BeamHeading { text: "State" }

            BeamRow { k: "Sunshine";   v: svc && svc.installed ? (svc.version || "installed") : "not installed"; ok: svc ? svc.installed : false }
            BeamRow { k: "Processes";  v: svc ? String(svc.processes) : "0"; ok: svc ? svc.processes === 1 : false }
            BeamRow { k: "Firewall";   v: svc ? (svc.ufwPresent ? svc.ufwRules + " rules" : "no ufw") : ""; ok: svc ? (svc.ufwRules > 0 || !svc.ufwPresent) : false }
            BeamRow { k: "Autostart";  v: svc && svc.autostart ? "hyprland" : "missing"; ok: svc ? svc.autostart : false }
            BeamRow { k: "Unit";       v: svc && svc.unit ? (svc.unitEnabled ? svc.unit + " (enabled)" : svc.unit + " (disabled)") : "none"; ok: svc ? !svc.unitEnabled : true }
            BeamRow { k: "Display";    v: svc && svc.displayFound ? "captured" : "not captured"; ok: svc ? svc.displayFound : false }
            BeamRow { k: "Encoder";    v: svc && svc.encoder ? svc.encoder + "  (" + svc.encoderKind + ")" : "unknown"; ok: svc ? svc.encoder !== "" : false }
            BeamRow { k: "Admin";      v: svc && svc.adminConfigured ? "configured" : "not configured"; ok: svc ? svc.adminConfigured : false }
            BeamRow { k: "Paired";     v: svc ? String(svc.pairedClients) : "0"; ok: svc ? svc.pairedClients > 0 : false }
            BeamRow { k: "Streaming";  v: svc && svc.streaming ? "yes" : "no"; ok: svc ? svc.streaming : false; neutral: true }
            BeamRow { k: "Address";    v: svc ? (svc.address + "  (" + svc.addressKind + ")") : ""; ok: svc ? svc.address !== "" : false }
            BeamRow { k: "LAN";        v: svc && svc.lanAddress ? svc.lanAddress : "none"; ok: svc ? svc.lanAddress !== "" : false; neutral: true }
          }

          ColumnLayout {
            Layout.fillWidth: true
            Layout.preferredWidth: 1
            Layout.alignment: Qt.AlignTop
            spacing: Style.space(8)

            BeamHeading { text: "Do it" }

            GridLayout {
              Layout.fillWidth: true
              columns: 3
              columnSpacing: Style.space(6)
              rowSpacing: Style.space(6)

              BeamButton { label: "Install";  primary: !(svc && svc.installed); onActivated: if (svc) svc.installInTerminal() }
              BeamButton { label: "Repair";   onActivated: if (svc) svc.repair() }
              BeamButton { label: "Ports";    onActivated: if (svc) svc.ports() }
              BeamButton { label: "Admin";    onActivated: if (svc) svc.admin() }
              BeamButton { label: "PIN page"; onActivated: if (svc) svc.pinPage() }
              BeamButton { label: "Remove";   danger: true; onActivated: confirmRemove.open = true }
            }

            // Removing is the one action here that throws work away, so it asks
            // first and says exactly what goes.
            Rectangle {
              id: confirmRemove
              property bool open: false
              visible: open
              Layout.fillWidth: true
              implicitHeight: Style.space(62)
              radius: Style.space(8)
              border.width: 1
              border.color: panel.faint
              color: Util.alpha(panel.foreground, 0.05)

              ColumnLayout {
                anchors.fill: parent
                anchors.margins: Style.space(8)
                spacing: Style.space(6)
                Text {
                  Layout.fillWidth: true
                  text: "Removes Sunshine, its firewall rules, its autostart line and its web app. Paired iPads will need pairing again."
                  color: panel.foreground
                  font.family: panel.fontFamily
                  font.pixelSize: Style.font.bodySmall
                  wrapMode: Text.WordWrap
                }
                RowLayout {
                  spacing: Style.space(6)
                  BeamButton { label: "Remove it"; danger: true
                               onActivated: { confirmRemove.open = false; if (svc) svc.undo() } }
                  BeamButton { label: "Keep it"; subtle: true; onActivated: confirmRemove.open = false }
                  Item { Layout.fillWidth: true }
                }
              }
            }

            RowLayout {
              Layout.fillWidth: true
              spacing: Style.space(8)
              Text {
                text: "Log"
                color: panel.dim
                font.family: panel.fontFamily
                font.pixelSize: Style.font.bodySmall
              }
              Item { Layout.fillWidth: true }
              Text {
                visible: svc && svc.busy
                text: "working"
                color: panel.good
                font.family: panel.fontFamily
                font.pixelSize: Style.font.bodySmall
              }
              BeamButton { label: "Clear"; subtle: true; onActivated: if (svc) svc.clearLog() }
            }

            // The one scroller in the whole plugin. Fixed height, scrolls in
            // place, the panel around it never moves.
            Rectangle {
              Layout.fillWidth: true
              implicitHeight: Style.space(150)
              radius: Style.space(6)
              border.width: 1
              border.color: panel.faint
              color: Util.alpha(panel.foreground, 0.04)

              ScrollView {
                id: logView
                anchors.fill: parent
                anchors.margins: Style.space(8)
                clip: true

                Text {
                  width: logView.availableWidth
                  text: svc && svc.log ? svc.log : "Nothing run yet."
                  color: svc && svc.log ? panel.foreground : panel.dim
                  font.family: "monospace"
                  font.pixelSize: Style.font.caption
                  wrapMode: Text.Wrap
                  onTextChanged: logView.ScrollBar.vertical.position = 1.0
                }
              }
            }
          }
        }

        Rectangle { Layout.fillWidth: true; height: 1; color: panel.faint; border.width: 0; visible: !panel.expert }

        // ---------------------------------------------------------- footer
        RowLayout {
          visible: !panel.expert
          Layout.fillWidth: true
          spacing: Style.space(8)

          BeamButton {
            label: "Back"
            subtle: true
            visible: panel.step > 1
            onActivated: panel.go(panel.step - 1)
          }
          Item { Layout.fillWidth: true }
          Text {
            text: "Step " + panel.step + " of 6"
            color: panel.dim
            font.family: panel.fontFamily
            font.pixelSize: Style.font.bodySmall
          }
          BeamButton {
            label: panel.step === 6 ? "Done" : "Next"
            primary: true
            onActivated: panel.step === 6 ? panel.widget.close() : panel.go(panel.step + 1)
          }
        }
      }
    }
  }

  // ------------------------------------------------------ small components
  // Inline so the plugin stays four files. Each one exists because the same
  // shape appears three or more times above.

  component BeamHeading: Text {
    Layout.fillWidth: true
    color: panel.foreground
    font.family: panel.fontFamily
    font.pixelSize: Style.font.subtitle
    font.bold: true
    wrapMode: Text.WordWrap
  }

  component BeamBody: Text {
    property bool faded: false
    Layout.fillWidth: true
    color: faded ? panel.dim : Qt.lighter(panel.dim, 1.15)
    font.family: panel.fontFamily
    font.pixelSize: Style.font.bodySmall
    wrapMode: Text.WordWrap
  }

  component BeamStep: RowLayout {
    property int n: 0
    property string text: ""
    Layout.fillWidth: true
    spacing: Style.space(8)

    Rectangle {
      width: Style.space(20); height: width; radius: width / 2
      border.width: 1; border.color: panel.faint; color: "transparent"
      Text {
        anchors.centerIn: parent
        text: parent.parent.n
        color: panel.dim
        font.family: panel.fontFamily
        font.pixelSize: Style.font.caption
      }
    }
    Text {
      Layout.fillWidth: true
      text: parent.text
      color: Qt.lighter(panel.dim, 1.15)
      font.family: panel.fontFamily
      font.pixelSize: Style.font.bodySmall
      wrapMode: Text.WordWrap
    }
  }

  component BeamCard: Rectangle {
    property string title: ""
    property string body: ""
    Layout.fillWidth: true
    Layout.preferredWidth: 1
    implicitHeight: Style.space(74)
    radius: Style.space(8)
    border.width: 1
    border.color: panel.faint
    color: "transparent"

    ColumnLayout {
      anchors.fill: parent
      anchors.margins: Style.space(9)
      spacing: Style.space(2)
      Text {
        text: parent.parent.title
        color: panel.foreground
        font.family: panel.fontFamily
        font.pixelSize: Style.font.body
        font.bold: true
      }
      Text {
        Layout.fillWidth: true
        Layout.fillHeight: true
        text: parent.parent.body
        color: panel.dim
        font.family: panel.fontFamily
        font.pixelSize: Style.font.bodySmall
        wrapMode: Text.WordWrap
        elide: Text.ElideRight
      }
    }
  }

  component BeamCheck: RowLayout {
    property bool ok: false
    property string label: ""
    spacing: Style.space(5)

    Rectangle {
      width: Style.space(10); height: width; radius: width / 2
      border.width: 0
      color: parent.ok ? panel.good : Util.alpha(panel.foreground, 0.25)
      Behavior on color { ColorAnimation { duration: 300 } }
    }
    Text {
      text: parent.label
      color: parent.ok ? panel.foreground : panel.dim
      font.family: panel.fontFamily
      font.pixelSize: Style.font.bodySmall
    }
  }

  component BeamRow: RowLayout {
    property string k: ""
    property string v: ""
    property bool ok: false
    property bool neutral: false
    Layout.fillWidth: true
    spacing: Style.space(8)

    Rectangle {
      width: Style.space(8); height: width; radius: width / 2
      border.width: 0
      color: parent.neutral ? Util.alpha(panel.foreground, 0.35)
           : parent.ok ? panel.good : Util.alpha(panel.foreground, 0.25)
    }
    Text {
      Layout.preferredWidth: Style.space(90)
      text: parent.k
      color: panel.dim
      font.family: panel.fontFamily
      font.pixelSize: Style.font.bodySmall
    }
    Text {
      Layout.fillWidth: true
      text: parent.v
      color: panel.foreground
      font.family: panel.fontFamily
      font.pixelSize: Style.font.bodySmall
      elide: Text.ElideRight
    }
  }

  component BeamButton: Rectangle {
    property string label: ""
    property bool primary: false
    property bool subtle: false
    property bool danger: false
    signal activated()

    implicitWidth: btnText.implicitWidth + Style.space(22)
    implicitHeight: Style.space(30)
    radius: Style.space(6)
    border.width: primary ? 2 : 1
    border.color: primary ? panel.good : panel.faint
    color: primary ? Util.alpha(panel.good, 0.16)
         : hover.hovered ? Util.alpha(panel.foreground, 0.08) : "transparent"

    Text {
      id: btnText
      anchors.centerIn: parent
      text: parent.label
      color: parent.subtle ? panel.dim : panel.foreground
      font.family: panel.fontFamily
      font.pixelSize: Style.font.bodySmall
      font.bold: parent.primary
    }

    // Pointer handlers do not fire reliably inside these panels. MouseArea is
    // the one that works, and hoverEnabled on it is what drives the hover tint.
    MouseArea {
      id: hover
      property bool hovered: containsMouse
      anchors.fill: parent
      hoverEnabled: true
      cursorShape: Qt.PointingHandCursor
      onClicked: parent.activated()
    }
  }
}
