// Extra adversarial ServiceState.js probes for the kimi3 audit.
const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const path = require('node:path');
const model = vm.createContext({});
vm.runInContext(fs.readFileSync(path.join(__dirname, '../ServiceState.js'), 'utf8'), model);
const base = {installed: true, running: true, streaming: true, ready: true, processes: 1, nextStep: 6};

test('streaming requires a live process even with fresh log evidence', () => {
    for (const patch of [{processes: 0}, {running: false}, {streaming: 1}, {streaming: "true"}]) {
        const data = {...base, ...patch};
        if (typeof data.streaming !== 'boolean') {
            assert.throws(() => model.decodeStatus(JSON.stringify(data)));
        } else {
            assert.equal(model.decodeStatus(JSON.stringify(data)).streaming, false);
        }
    }
});

test('nextStep boundaries', () => {
    for (const step of [0, 7, 2.5, '2', null]) {
        assert.throws(() => model.decodeStatus(JSON.stringify({...base, nextStep: step})), String(step));
    }
    for (const step of [1, 6]) {
        assert.equal(model.decodeStatus(JSON.stringify({...base, nextStep: step})).nextStep, step);
    }
});

test('report never trusts ok=true when exit state says working', () => {
    const r = model.report({ok: true, state: 'pending', action: 'terminal', message: 'Opening.'});
    assert.equal(r.state, 'working');
    const unknown = model.report({ok: false, action: 'mystery'});
    assert.equal(unknown.title, 'Beam');
    assert.equal(unknown.state, 'error');
    assert.throws(() => model.report(null));
    assert.throws(() => model.report([1, 2]));
    assert.throws(() => model.report('x'));
});

test('actionTime numeric strings and booleans cannot masquerade as fresh results', () => {
    assert.equal(model.actionTime({updatedAt: '1789840000000'}), 0); // string form rejected
    assert.equal(model.actionTime({updatedAt: true}), 0);
    assert.equal(model.actionTime({updatedAt: 'not-a-date'}), 0);
    assert.equal(model.actionTime({updatedAt: '2026-09-19T12:00:00Z'}), Date.parse('2026-09-19T12:00:00Z'));
});

test('enqueue dedupe is argument-order sensitive and bounded', () => {
    let q = model.enqueue([], ['set-resolution', '2732x2048'], 3);
    assert.equal(model.enqueue(q, ['set-resolution', '2732x2048'], 3).length, 1);
    q = model.enqueue(q, ['set-resolution', 'auto'], 3);
    q = model.enqueue(q, ['admin'], 3);
    assert.equal(model.enqueue(q, ['pin'], 3), null);
    assert.equal(q.length, 3);
});

test('fresh window bounds', () => {
    assert.equal(model.fresh(1000, 1000 + 9999, 2, false), true);   // 10s floor for refreshSec=2
    assert.equal(model.fresh(1000, 1000 + 10000, 2, false), false);
    assert.equal(model.fresh(1000, 1000 + 359999, 120, false), true);
    assert.equal(model.fresh(1000, 1000 + 360000, 120, false), false);
});
