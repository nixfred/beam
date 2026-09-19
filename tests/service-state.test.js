const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const path = require('node:path');
const model = vm.createContext({});
vm.runInContext(fs.readFileSync(path.join(__dirname, '../ServiceState.js'), 'utf8'), model);
const base = {installed: true, running: true, streaming: true, ready: true, processes: 1, nextStep: 6};
test('partial and malformed snapshots cannot refresh an apparently healthy screen', () => {
    for (const data of ['broken', '{}', 'null', '[]', JSON.stringify({...base, processes: '1'}), JSON.stringify({...base, nextStep: 9})])
        assert.throws(() => model.decodeStatus(data));
});
test('dead Sunshine cannot remain live because an old log says connected', () => {
    const data = model.decodeStatus(JSON.stringify({...base, running: false, processes: 0}));
    assert.equal(data.streaming, false);
});
test('failed or expired polls release eligibility for the native idle inhibitor', () => {
    assert.equal(model.fresh(10000, 11000, 5, false), true);
    assert.equal(model.fresh(10000, 11000, 5, true), false);
    assert.equal(model.fresh(10000, 25000, 5, false), false);
    assert.equal(model.fresh(10000, 9000, 5, false), false);
    assert.equal(model.fresh(0, 1000, 5, false), false);
});
test('queue preserves older actions, deduplicates, and reports overflow instead of dropping work', () => {
    let q = model.enqueue([], ['admin'], 2);
    q = model.enqueue(q, ['pin'], 2);
    assert.equal(model.enqueue(q, ['admin'], 2).length, 2);
    assert.equal(model.enqueue(q, ['terminal', 'undo'], 2), null);
    assert.equal(JSON.stringify(q), '[["admin"],["pin"]]');
});
test('launching a setup terminal is progress, not a successful installation', () => {
    const r = model.report({ok: true, action: 'install', state: 'working', message: 'Continue in the terminal.'});
    assert.equal(r.state, 'working');
    assert.equal(r.title, 'Set up this computer');
});
test('action errors keep their explanation and recovery instruction', () => {
    const r = model.report({ok: false, action: 'repair', message: 'Ports could not be opened.', detail: 'Retry in the terminal.', retryAction: 'ports'});
    assert.equal(r.state, 'error');
    assert.equal(r.next, 'Retry in the terminal.');
    assert.equal(r.retryAction, 'ports');
});
test('result timestamps permit rejecting a response from before the current user action', () => {
    assert.equal(model.actionTime({updatedAt: 1789840000000}), 1789840000000);
    assert.equal(model.actionTime({updatedAt: 1789840000}), 1789840000000);
    assert.equal(model.actionTime(null), 0);
});
