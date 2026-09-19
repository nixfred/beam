// Shared pure state rules; exercised with malformed, stale and racing responses.
function decodeStatus(text) {
    var data = JSON.parse(text)
    if (!data || Array.isArray(data) || typeof data !== "object")
        throw new Error("The status response is not an object.")
    var flags = ["installed", "running", "streaming", "ready"]
    for (var i = 0; i < flags.length; i++)
        if (typeof data[flags[i]] !== "boolean")
            throw new Error("The status response is incomplete.")
    if (!Number.isInteger(data.processes) || data.processes < 0 ||
        !Number.isInteger(data.nextStep) || data.nextStep < 1 || data.nextStep > 6)
        throw new Error("The status response contains invalid counts or steps.")
    // A stale log can never overrule current process evidence.
    data.streaming = data.streaming && data.running && data.processes > 0
    return data
}

function fresh(lastSuccess, now, refreshSec, failure) {
    return !failure && lastSuccess > 0 && now >= lastSuccess &&
        now - lastSuccess < Math.max(10000, refreshSec * 3000)
}

function report(result, fallbackAction) {
    if (!result || typeof result !== "object" || Array.isArray(result))
        throw new Error("No action result was returned.")
    var action = String(result.action || fallbackAction || "action")
    var labels = {install: "Set up this computer", repair: "Repair setup", ports: "Check ports",
                  undo: "Remove Sunshine", admin: "Sunshine login", pin: "Pair your iPad",
                  moonlight: "Get Moonlight", "copy-address": "Copy address", terminal: "Setup"}
    var state = result.state === "working" || result.state === "pending" ? "working"
              : result.ok === true ? "success" : "error"
    return {state: state, title: labels[action] || "Beam", action: action,
            message: String(result.message || (state === "success" ? "Complete." : "Action did not finish.")),
            next: String(result.detail || ""), retryAction: String(result.retryAction || "")}
}

function actionTime(result) {
    if (!result) return 0
    var value = result.updatedAt || result.timestamp || result.at || 0
    return typeof value === "number" ? (value < 100000000000 ? value * 1000 : value)
                                    : (Date.parse(String(value)) || 0)
}

function enqueue(queue, args, limit) {
    var key = JSON.stringify(args)
    for (var i = 0; i < queue.length; i++)
        if (JSON.stringify(queue[i]) === key) return queue.slice()
    if (queue.length >= limit) return null
    return queue.concat([args.slice()])
}
