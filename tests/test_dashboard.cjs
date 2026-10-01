const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const source = fs.readFileSync(path.join(__dirname, '../emergence/static/missions.js'), 'utf8');
function dashboard() {
  const pending = [];
  const context = vm.createContext({
    location: {hash: '#overview'},
    setInterval: () => 0,
    api: url => new Promise(resolve => pending.push({url, resolve})),
  });
  context.route = () => context.location.hash.slice(1).split('/');
  vm.runInContext(source, context);
  return {context, pending, load: () => vm.runInContext('loadMissions()', context),
    selected: () => vm.runInContext('missionData.selected', context)};
}

test('an overview response cannot replace a different report after navigation', async () => {
  const d = dashboard();
  const overview = d.load();
  d.context.location.hash = '#reports/older_mission';
  const report = d.load();
  assert.equal(d.pending[1].url, 'missions?id=older_mission');
  d.pending[1].resolve({selected: 'older_mission'});
  assert.equal(await report, true);
  d.pending[0].resolve({selected: 'latest_mission'});
  assert.equal(await overview, false);
  assert.equal(d.selected(), 'older_mission');
});

test('overlapping refreshes of one route keep the newest response', async () => {
  const d = dashboard();
  const old = d.load(), fresh = d.load();
  d.pending[1].resolve({selected: 'new_result'});
  assert.equal(await fresh, true);
  d.pending[0].resolve({selected: 'old_result'});
  assert.equal(await old, false);
  assert.equal(d.selected(), 'new_result');
});
