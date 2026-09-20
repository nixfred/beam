const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const path = require('node:path');
const model = vm.createContext({});
vm.runInContext(fs.readFileSync(path.join(__dirname, '../ServiceState.js'), 'utf8'), model);

const base = {installed: true, running: true, streaming: true, ready: true, processes: 1, nextStep: 6};

test('decodeStatus accepts a lastAction array that report() later rejects', () => {
    const data = model.decodeStatus(JSON.stringify({...base, lastAction: []}));
    assert.equal(Array.isArray(data.lastAction) && data.lastAction.length === 0, true);
    assert.throws(() => model.report(data.lastAction, 'repair'));
});

test('decodeStatus accepts a lastAction string that report() later rejects', () => {
    const data = model.decodeStatus(JSON.stringify({...base, lastAction: 'working'}));
    assert.equal(data.lastAction, 'working');
    assert.throws(() => model.report(data.lastAction, 'repair'));
});

test('report treats pending as working even when ok is true', () => {
    const r = model.report({ok: true, action: 'ports', state: 'pending', message: 'Opening.'});
    assert.equal(r.state, 'working');
});

test('queue overflow is null rather than dropping the oldest action', () => {
    let q = model.enqueue([], ['terminal', 'install'], 1);
    assert.equal(model.enqueue(q, ['terminal', 'repair'], 1), null);
    assert.deepEqual(q, [['terminal', 'install']]);
});

test('fresh uses a 10s floor even for a 2 second refresh', () => {
    assert.equal(model.fresh(10000, 19999, 2, false), true);
    assert.equal(model.fresh(10000, 20000, 2, false), false);
});
