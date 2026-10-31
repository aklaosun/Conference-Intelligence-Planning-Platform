'use strict';
// Keep each source-backed row intact while presenting ordinary form controls.
window.CCSERows = Object.freeze({ mount });
function mount(id) {
  const storage = document.getElementById(id);
  const host = document.getElementById(id + '-editor');
  const isDeadline = id === 'deadlines';
  let rows = JSON.parse(storage.value || '[]');
  host.replaceChildren();
  const list = document.createElement('div');
  host.append(list);
  const sync = () => {
    storage.value = JSON.stringify(rows);
    storage.dispatchEvent(new Event('input', { bubbles: true }));
  };
  function field(parent, row, key, labelText, type = 'text', index) {
    const wrap = document.createElement('div');
    const label = document.createElement('label');
    const input = document.createElement(type === 'textarea' ? 'textarea' : 'input');
    input.id = `${id}-${index}-${key}`;
    label.htmlFor = input.id;
    label.textContent = labelText;
    if (type !== 'textarea') input.type = type;
    if (type === 'number') { input.min = '0'; input.step = '0.01'; }
    input.value = row[key] ?? '';
    input.placeholder = 'Unknown';
    input.addEventListener('input', () => {
      row[key] = input.value.trim() || null;
      sync();
    });
    wrap.append(label, input);
    parent.append(wrap);
  }
  function draw() {
    list.replaceChildren();
    if (!rows.length) {
      const empty = document.createElement('p');
      empty.className = 'muted';
      empty.textContent = isDeadline ? 'No deadlines found. Add a row only when supported by a source.' : 'Registration prices are unknown.';
      list.append(empty);
    }
    rows.forEach((row, index) => {
      const card = document.createElement('div');
      card.className = 'row-card';
      const top = document.createElement('div');
      top.className = 'row-tools';
      const title = document.createElement('strong');
      title.textContent = `${isDeadline ? 'Deadline' : 'Price'} ${index + 1}`;
      const remove = document.createElement('button');
      remove.type = 'button'; remove.className = 'remove-row';
      remove.textContent = 'Remove';
      remove.setAttribute('aria-label', `Remove ${isDeadline ? 'deadline' : 'price'} ${index + 1}`);
      remove.onclick = () => { rows.splice(index, 1); sync(); draw(); };
      top.append(title, remove); card.append(top);
      const grid = document.createElement('div'); grid.className = 'row-grid'; card.append(grid);
      if (isDeadline) {
        if (!row.type && row.name) row.type = row.name;
        field(grid, row, 'type', 'Deadline / track', 'text', index);
        field(grid, row, 'date', 'Date', 'date', index);
        field(grid, row, 'time', 'Time (optional)', 'time', index);
        field(grid, row, 'timezone', 'Timezone / AoE', 'text', index);
      } else {
        field(grid, row, 'category', 'Registration category', 'text', index);
        field(grid, row, 'rate_type', 'Rate / tier', 'text', index);
        field(grid, row, 'amount', 'Amount', 'number', index);
        field(grid, row, 'currency', 'Currency (e.g. EUR)', 'text', index);
      }
      const source = document.createElement('details');
      const summary = document.createElement('summary'); summary.textContent = 'Evidence & source';
      source.append(summary);
      field(source, row, 'source_url', 'Source URL', 'url', index);
      field(source, row, 'evidence', 'Supporting source text', 'textarea', index);
      card.append(source); list.append(card);
    });
  }
  const add = document.createElement('button'); add.type = 'button';
  add.textContent = isDeadline ? '+ Add deadline' : '+ Add registration price';
  add.onclick = () => {
    if (rows.length >= 200) return;
    rows.push(isDeadline ? {type:'',date:null,time:null,timezone:null,source_url:null,evidence:''}
      : {category:'',rate_type:'',amount:null,currency:'',source_url:null,evidence:''});
    sync(); draw();
  };
  host.append(add); draw();
}
