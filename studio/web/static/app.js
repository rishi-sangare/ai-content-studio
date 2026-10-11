/* Studio cockpit. One page, hash routes, live updates over server-sent events.
   Rule of thumb: live refreshes only replace [data-live] sections, and never one you're typing in. */
'use strict';

// ---------- tiny helpers ----------
const $ = (s, el = document) => el.querySelector(s);
const $$ = (s, el = document) => [...el.querySelectorAll(s)];
const esc = (s) => String(s ?? '').replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
const j = (o) => esc(JSON.stringify(o));
const plural = (n, w) => `${n} ${w}${n === 1 ? '' : 's'}`;
const money = (n) => '$' + (Number(n) || 0).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 });
const num = (n) => (Number(n) || 0).toLocaleString();

const ICON = {
  play: '<svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true"><path d="M7 4v16l13-8z"/></svg>',
  pause: '<svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true"><path d="M6 4h4v16H6zM14 4h4v16h-4z"/></svg>',
  mic: '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" aria-hidden="true"><rect x="9" y="3" width="6" height="11" rx="3"/><path d="M5 11a7 7 0 0 0 14 0M12 18v3"/></svg>',
  flame: '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linejoin="round" aria-hidden="true"><path d="M12 3c2 4 6 5 6 10a6 6 0 0 1-12 0c0-3 2-4 3-6 1 2 2 2 3 2 0-2-1-4 0-6z"/></svg>',
  clock: '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" aria-hidden="true"><circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/></svg>',
  ask: '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" aria-hidden="true"><path d="M4 5h16v11H9l-5 4z"/></svg>',
  upload: '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" aria-hidden="true"><path d="M12 16V4M6 10l6-6 6 6M5 20h14"/></svg>',
  x: '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" aria-hidden="true"><path d="M6 6l12 12M18 6L6 18"/></svg>',
};

// ---------- time ----------
const clock = (iso) => new Date(iso).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', hour12: false });
function when(iso) {
  if (!iso) return '';
  const d = new Date(iso), now = new Date();
  if (d.toDateString() === now.toDateString()) return clock(iso);
  const y = new Date(now); y.setDate(now.getDate() - 1);
  if (d.toDateString() === y.toDateString()) return 'yest';
  return d.toLocaleDateString([], { day: 'numeric', month: 'short' });
}
function ago(iso) {
  if (!iso) return '';
  const s = Math.round((Date.now() - new Date(iso)) / 1000);
  if (s < 60) return 'just now';
  if (s < 3600) return `${Math.floor(s / 60)} min ago`;
  if (s < 86400) return `${Math.floor(s / 3600)} h ago`;
  return `${Math.floor(s / 86400)} d ago`;
}
const tc = (t) => { t = Math.max(0, t || 0); return `${Math.floor(t / 60)}:${(t % 60).toFixed(1).padStart(4, '0')}`; };

const STATUS = { joined: 'active', candidate: 'deciding', skipped: 'skipped', ended: 'ended' };

// ---------- state ----------
const S = {
  state: null, route: null, data: null, version: null, conn: 'connecting',
  filter: 'all', room: 'hq', editing: null, showSkipped: false, loadSeq: 0,
};

// ---------- network ----------
async function get(path) {
  const r = await fetch('/api/' + path, { cache: 'no-store' });
  const body = await r.json().catch(() => ({ error: 'The server sent something unreadable.' }));
  if (!r.ok) throw new Error(body.error || `HTTP ${r.status}`);
  return body;
}
async function act(action, btn) {
  if (btn) btn.classList.add('busy');
  try {
    const r = await fetch('/api/action', {
      method: 'POST', headers: { 'Content-Type': 'application/json', 'X-Studio': '1' }, body: JSON.stringify(action),
    });
    const body = await r.json().catch(() => ({ ok: false, error: 'The server sent something unreadable.' }));
    if (!r.ok || !body.ok) throw new Error(body.error || `HTTP ${r.status}`);
    if (body.message) toast(body.message);
    await refresh();
    return body;
  } catch (e) {
    toast(e.message === 'Failed to fetch' ? 'Can’t reach the Studio server. Is it running?' : e.message, true);
    throw e;
  } finally {
    if (btn) btn.classList.remove('busy');
  }
}

// ---------- toasts & banner ----------
function toast(msg, err = false) {
  let box = $('.toasts');
  if (!box) { box = document.createElement('div'); box.className = 'toasts'; box.setAttribute('role', 'status'); document.body.append(box); }
  const t = document.createElement('div');
  t.className = 'toast ' + (err ? 'err' : 'ok');
  t.textContent = msg;
  box.append(t);
  setTimeout(() => t.remove(), err ? 7000 : 3500);
}
function banner(msg) {
  let b = $('.banner');
  if (!msg) { if (b) b.remove(); return; }
  if (!b) { b = document.createElement('div'); b.className = 'banner'; b.setAttribute('role', 'alert'); document.body.append(b); }
  b.textContent = msg;
}

// ---------- clipboard ----------
async function copy(text, label = 'Copied') {
  try {
    await navigator.clipboard.writeText(text);
  } catch {
    const ta = document.createElement('textarea');
    ta.value = text; ta.style.position = 'fixed'; ta.style.opacity = '0';
    document.body.append(ta); ta.select(); document.execCommand('copy'); ta.remove();
  }
  toast(label);
}

// ---------- live sections ----------
function typingIn(el) {
  const a = document.activeElement;
  return a && el.contains(a) && a.matches('input, textarea, select');
}
function patch(map) {
  for (const [key, html] of Object.entries(map || {})) {
    if (html == null) continue;
    const el = $(`[data-live="${key}"]`);
    if (!el || el._html === html) continue;
    if (typingIn(el)) { S.pending = true; continue; }
    el.innerHTML = html;
    el._html = html;
  }
}

// ---------- routing ----------
function parseRoute() {
  const parts = location.hash.replace(/^#\/?/, '').split('/').filter(Boolean).map(decodeURIComponent);
  const [a, b, c] = parts;
  if (!a) return { name: 'today' };
  if (a === 'campaign' && b) return { name: 'campaign', id: b, tab: c || 'pipeline' };
  if (a === 'review' && b) return { name: 'review', id: b, v: c ? Number(c) : null };
  if (a === 'room' && b) return { name: 'room', id: b };
  if (['rooms', 'library', 'money', 'accounts', 'analytics', 'finds', 'schedule', 'links'].includes(a)) return { name: a };
  return { name: 'notfound' };
}
const href = {
  today: '#/', campaign: (id, tab) => `#/campaign/${encodeURIComponent(id)}${tab && tab !== 'pipeline' ? '/' + tab : ''}`,
  review: (id, v) => `#/review/${encodeURIComponent(id)}${v ? '/' + v : ''}`, room: (id) => `#/room/${encodeURIComponent(id)}`,
};

// ---------- shell ----------
function shell() {
  $('#app').innerHTML = `
  <div class="shell" id="shell">
    <nav class="rail" id="rail" aria-label="Studio"></nav>
    <main class="main" id="main" tabindex="-1"></main>
    <aside class="dock" id="dock" aria-label="Claude">${dockStatic()}</aside>
  </div>`;
}

function rail() {
  const st = S.state; if (!st) return '';
  const r = S.route || {};
  const on = (cond) => (cond ? ' on' : '');
  const n = st.inbox.length;
  const urgent = st.inbox.some((i) => i.urgent);
  const camps = st.campaigns.filter((c) => c.status !== 'skipped');
  const skipped = st.campaigns.filter((c) => c.status === 'skipped');
  const campLink = (c) => `<a class="nav-a sub${on(r.name === 'campaign' && r.id === c.id)}" href="${href.campaign(c.id)}">
      <span style="display:flex;align-items:center;gap:8px;min-width:0"><span class="dot${c.status === 'joined' ? '' : c.status === 'skipped' ? ' off' : ' hollow'}"></span>
      <span style="overflow:hidden;text-overflow:ellipsis;white-space:nowrap">${esc(c.name)}</span></span></a>`;
  return `
    <div class="brand"><div class="brand-mark">S</div><div class="brand-text"><div class="brand-name">Studio</div><div class="brand-sub">Rishi's content cockpit</div></div></div>
    <button class="jump" data-palette><span>Jump to anything…</span><kbd>⌘K</kbd></button>
    <a class="nav-a${on(r.name === 'today')}" href="#/"><span>Today</span>${n ? `<span class="badge${urgent ? ' amber' : ''}">${n}</span>` : ''}</a>
    <div class="nav-label">Streams</div>
    <div class="nav-a dim" style="cursor:default">Clipping</div>
    ${camps.map(campLink).join('')}
    ${skipped.length ? `<button class="nav-a sub dim" data-toggle-skipped style="background:none;border:0;text-align:left">${S.showSkipped ? 'Hide' : 'Show'} skipped (${skipped.length})</button>` : ''}
    ${S.showSkipped ? skipped.map(campLink).join('') : ''}
    <a class="nav-a dim${on(r.name === 'room' && r.id === 'influencer')}" href="${href.room('influencer')}"><span>AI influencer</span><span class="tag">paused</span></a>
    <div class="nav-a dim" style="cursor:default"><span>Faceless YouTube</span><span class="tag">later</span></div>
    <div class="nav-label">Studio</div>
    <a class="nav-a${on(r.name === 'rooms' || (r.name === 'room' && r.id !== 'influencer'))}" href="#/rooms">Rooms and memory</a>
    <a class="nav-a${on(r.name === 'schedule')}" href="#/schedule">Schedule</a>
    <a class="nav-a${on(r.name === 'links')}" href="#/links">Links to submit</a>
    <a class="nav-a${on(r.name === 'analytics')}" href="#/analytics">Analytics</a>
    <a class="nav-a${on(r.name === 'money')}" href="#/money">Money</a>
    <a class="nav-a${on(r.name === 'accounts')}" href="#/accounts">Accounts</a>
    <a class="nav-a${on(r.name === 'library')}" href="#/library">Library</a>
    <a class="nav-a${on(r.name === 'finds')}" href="#/finds">Finds</a>
    <div class="rail-foot"><div class="conn"><span class="dot${S.conn === 'live' ? '' : ' amber'}"></span>${S.conn === 'live' ? 'Live · updates by itself' : 'Reconnecting…'}</div></div>`;
}

// ---------- dock (Claude) ----------
const QUICK = [                                   // [label, message, room]
  ['What needs me?', 'What needs me today? Go through the inbox with me.', 'hq'],
  ['Next RAG clip', 'Make the next Roll Anime Girls clip in the meme style.', 'roll-anime-girls'],
  ['API audit draft', 'Draft my answers for the YouTube API audit form.', 'lab'],
  ['Wrap up', 'Wrap up the day: update each room\'s memory and tell me what\'s next.', 'hq'],
];
function dockStatic() {
  const speech = window.SpeechRecognition || window.webkitSpeechRecognition;
  return `
    <div class="dock-head"><span class="dock-title">Claude</span><button class="btn ghost dock-toggle" data-dock-close aria-label="Close">${ICON.x}</button></div>
    <div class="dock-block"><span class="dock-k">Waiting on Claude</span><div data-live="working"></div></div>
    <div class="dock-block"><span class="dock-k">Recent</span><div class="feed" data-live="feed"></div></div>
    <div style="flex:1"></div>
    <div class="dock-block"><span class="dock-k">Quick asks</span>
      <div class="quick">${QUICK.map(([l, t, room]) => `<button data-fill="${esc(t)}" data-fill-room="${esc(room)}">${esc(l)}</button>`).join('')}</div></div>
    <form class="talk" data-form="tell" autocomplete="off">
      <div class="talk-top"><label for="talk-room">Tell Claude in</label><select id="talk-room" name="room" data-live-select="rooms"></select></div>
      <label for="talk-text" class="sr-only">Message for Claude</label>
      <textarea id="talk-text" name="text" rows="3" placeholder="Make rag-003, the rarest-pull challenge"></textarea>
      <div class="talk-bottom">
        ${speech ? `<button type="button" class="mic" data-mic aria-label="Speak instead of typing">${ICON.mic}</button>` : '<span class="faint" style="font-size:12px">Tip: press Fn twice to dictate</span>'}
        <button class="btn primary" type="submit">Send</button>
      </div>
      <span class="faint" style="font-size:12px">Claude reads it the next time you chat in that room.</span>
    </form>`;
}
function roomOptions() {
  const st = S.state;
  const opts = [['hq', 'HQ'], ['lab', 'Studio Lab']];
  for (const c of st.campaigns) if (c.status !== 'skipped') opts.push([c.id, c.name]);
  const sel = $('#talk-room');
  if (!sel) return;
  if (!opts.some(([v]) => v === S.room)) S.room = 'hq';
  const html = opts.map(([v, l]) => `<option value="${esc(v)}"${v === S.room ? ' selected' : ''}>${esc(l)}</option>`).join('');
  if (sel._html !== html && document.activeElement !== sel) { sel.innerHTML = html; sel._html = html; }
}
function dockLive() {
  const st = S.state;
  const work = st.working.length
    ? st.working.map((w) => `<div class="work"><span class="dot amber" style="margin-top:6px"></span><div><div>${esc(w.text)}</div>
        <div class="faint" style="font-size:12px">${w.room ? esc(w.room) + ' · ' : ''}${esc(ago(w.at))}</div></div>
        ${w.kind === 'request' ? `<button class="btn ghost x" style="height:26px;padding:0 6px" data-do="${j({ type: 'request_cancel', request: w.id })}" data-confirm="Remove this message for Claude?" aria-label="Remove">${ICON.x}</button>` : ''}</div>`).join('')
    : '<div class="work"><span class="faint">Nothing queued. Messages you send below wait here until Claude picks them up.</span></div>';
  const feed = st.activity.slice(0, 9).map((a) => `<div class="feed-row"><time datetime="${esc(a.at)}">${esc(when(a.at))}</time><span>${esc(a.text)}</span></div>`).join('')
    || '<span class="faint">Nothing yet.</span>';
  return { working: work, feed };
}

// ---------- views ----------
const V = {};

// Today
V.today = {
  title: 'Today',
  skeleton() {
    const h = new Date().getHours();
    const hello = h < 5 ? 'Up late, Rishi' : h < 12 ? 'Good morning, Rishi' : h < 17 ? 'Good afternoon, Rishi' : 'Good evening, Rishi';
    return `<div class="page">
      <div class="page-head">
        <div><div class="eyebrow">${esc(new Date().toLocaleDateString([], { weekday: 'long', day: 'numeric', month: 'long' }))}</div><h1>${hello}</h1></div>
        <div style="display:flex;gap:10px;align-items:flex-end">
          <div data-live="nextslot" style="text-align:right"></div>
          <button class="btn dock-toggle" data-dock-open>Claude</button>
        </div>
      </div>
      <section class="card brief" data-live="brief" aria-label="Brief"></section>
      <div class="stat-row" data-live="kpis"></div>
      <section class="section" aria-label="Needs you">
        <div class="section-head"><h2 data-live="inbox-title"></h2>
          <div class="chips" role="group" aria-label="Filter" data-live="filters"></div></div>
        <div class="list" data-live="inbox"></div>
      </section>
      <section class="section" aria-label="Posting slots"><h2>Next posting slots</h2><div class="slots" data-live="slots"></div></section>
    </div>`;
  },
  live() {
    const st = S.state;
    const b = st.brief;
    const items = st.inbox.filter((i) => S.filter === 'all' || i.kind === S.filter || (S.filter === 'review' && i.kind === 'post'));
    const kinds = [['all', 'All'], ['review', 'Review'], ['submit', 'Submit'], ['decide', 'Decide'], ['warmup', 'Warm-up'], ['ask', 'Questions']]
      .filter(([k]) => k === 'all' || st.inbox.some((i) => i.kind === k || (k === 'review' && i.kind === 'post')));
    const warming = st.accounts.filter((a) => a.status === 'warming');
    const s0 = st.slots[0];
    return {
      nextslot: s0 ? `<div class="stat-k">Next posting slot</div><div class="mono" style="font-size:15px">${esc(s0.label)}</div>` : '',
      brief: `<span class="by">${b.by === 'claude' ? `Claude's brief · ${esc(when(b.at))}` : 'Where things stand · worked out from the Studio just now'}</span>
        <p>${esc(b.text)}</p>`,
      kpis: `
        <div class="stat"><span class="stat-k">Earned, estimated</span><span class="stat-v">${money(st.kpis.est)}</span></div>
        <div class="stat"><span class="stat-k">Views on submitted posts</span><span class="stat-v">${num(st.kpis.views)}</span></div>
        <div class="stat"><span class="stat-k">Posts this week</span><span class="stat-v">${st.kpis.posts_week}</span></div>
        <div class="stat"><span class="stat-k">${warming.length ? 'Warm-up days · ' + esc(warming[0].handle) : 'Accounts ready to post'}</span>
          <span class="stat-v">${warming.length ? `${warming[0].warmup.days_logged} of ${warming[0].warmup.needed}` : st.accounts.filter((a) => a.status === 'active').length}</span></div>`,
      'inbox-title': `Needs you <span class="muted" style="font-weight:500">· ${st.inbox.length}</span>`,
      filters: kinds.length > 2 ? kinds.map(([k, l]) => `<button class="chip${S.filter === k ? ' on' : ''}" data-filter="${k}" aria-pressed="${S.filter === k}">${l}</button>`).join('') : '',
      inbox: items.length ? items.map(inboxRow).join('') : `<div class="empty">${st.inbox.length ? 'Nothing of this kind.' : 'All clear. Nothing needs you right now.'}</div>`,
      slots: st.slots.map((s) => {
        const [day, et] = s.label.split(' · ');
        const head = `<div class="mono">${esc(day)} <span class="faint">· ${esc(et || '')}</span></div>`;
        if (!s.clip) return `<div class="slot"><div>${head}<div class="muted" style="font-size:13px">Free. Approve a clip to book it.</div></div></div>`;
        const live = s.clip_status === 'posted' || s.clip_status === 'submitted';
        return `<a class="slot filled" href="${href.review(s.clip)}"><div>${head}<div class="muted" style="font-size:13px">${esc(s.clip)} ${live ? 'went live' : 'is booked'}</div></div>
          <span class="pill green">${live ? 'live' : 'booked'}</span></a>`;
      }).join(''),
    };
  },
};

function inboxRow(i) {
  const lead = i.thumb ? `<img class="thumb" src="${esc(i.thumb)}" alt="" loading="lazy">`
    : `<div class="icon-box${i.kind === 'submit' || i.kind === 'warmup' ? ' amber' : ''}">${{ submit: ICON.clock, warmup: ICON.flame, ask: ICON.ask, post: ICON.upload, decide: '<span style="font:600 12px var(--display)">?</span>' }[i.kind] || ''}</div>`;
  const acts = (i.actions || []).map((a) => a.href
    ? `<a class="btn${a.primary ? ' primary' : ''}" href="${esc(a.href)}">${esc(a.label)}</a>`
    : `<button class="btn${a.primary ? ' primary' : ''}" data-do="${j(a.do)}"${a.do.type === 'campaign_decide' ? ` data-confirm="${esc(a.label)} this campaign?"` : ''}>${esc(a.label)}</button>`).join('');
  const extra = i.kind === 'submit'
    ? `<span class="countdown" data-deadline="${esc(i.deadline)}"></span>${i.url ? `<button class="btn" data-copy="${esc(i.url)}" data-copy-label="Link copied">Copy link</button>` : ''}` : '';
  const title = i.link ? `<a href="${esc(i.link)}" class="row-title">${esc(i.title)}</a>` : `<span class="row-title">${esc(i.title)}</span>`;
  return `<div class="row${i.urgent ? ' urgent' : ''}">${lead}<div class="row-body">${title}<span class="row-detail">${esc(i.detail)}</span></div>
    <div class="row-actions">${extra}${acts}</div></div>`;
}

// Campaign
V.campaign = {
  title: (r, d) => d?.name || 'Campaign',
  load: (r) => get('campaign/' + encodeURIComponent(r.id)),
  skeleton(r, d) {
    const tabs = [['pipeline', 'Pipeline'], ['footage', `Footage · ${d.footage.length}`], ['rules', 'Brief and rules'], ['memory', 'Memory']];
    const facts = [d.cpm != null ? `${money(d.cpm)} per 1K views` : null, d.max_payout ? `max $${Number(d.max_payout).toLocaleString()} per post` : null,
      d.owner ? `by ${d.owner}` : null].filter(Boolean).join(' · ');
    const pill = { joined: '<span class="pill green">Active</span>', candidate: '<span class="pill amber">Deciding</span>', skipped: '<span class="pill">Skipped</span>' }[d.status] || `<span class="pill">${esc(d.status)}</span>`;
    const decide = d.status === 'candidate' ? `<button class="btn" data-do="${j({ type: 'campaign_decide', campaign: d.id, decision: 'skip' })}" data-confirm="Skip ${esc(d.name)}?">Skip</button>
      <button class="btn primary" data-do="${j({ type: 'campaign_decide', campaign: d.id, decision: 'join' })}" data-confirm="Join ${esc(d.name)}?">Join</button>` : '';
    const make = d.status === 'joined' ? `<button class="btn primary" data-do="${j({ type: 'tell', room: d.id, text: `Make the next ${d.name} clip in the house style.` })}">Ask for the next clip</button>` : '';
    return `<div class="page" style="max-width:1320px">
      <div class="eyebrow">Clipping / ${esc(d.name)}</div>
      <div class="page-head">
        <div style="display:flex;flex-direction:column;gap:8px"><div style="display:flex;align-items:center;gap:12px;flex-wrap:wrap"><h1>${esc(d.name)}</h1>${pill}</div>
          <span class="muted">${esc(facts)}</span></div>
        <div style="display:flex;gap:10px;flex-wrap:wrap"><button class="btn" data-tell-room="${esc(d.id)}">Tell this room</button>${decide}${make}</div>
      </div>
      <div class="tabs" role="tablist">${tabs.map(([k, l]) => `<a class="tab${r.tab === k ? ' on' : ''}" role="tab" aria-selected="${r.tab === k}" href="${href.campaign(d.id, k)}">${esc(l)}</a>`).join('')}</div>
      ${r.tab === 'pipeline' ? `<div class="board" data-live="board"></div><div class="grid3" data-live="cards"></div>` : ''}
      ${r.tab === 'footage' ? `<p class="muted" style="margin:0">The campaign's own footage. Click a clip to watch it.</p><div class="footage">${d.footage.map((f) => `
        <button class="foot" data-watch="${esc(f.video)}" data-watch-title="${esc(f.name)}"><img src="${esc(f.thumb)}" alt="" loading="lazy"><span>${esc(f.name)}</span></button>`).join('') || '<div class="empty">No footage folder.</div>'}</div>` : ''}
      ${r.tab === 'rules' ? `<div class="grid3" style="grid-template-columns:minmax(0,1fr) minmax(0,1.3fr)">
        <div class="card"><h3 style="margin-bottom:10px">Rules every clip must pass</h3><ul class="rules">${d.requirements.map((x) => `<li>${esc(x)}</li>`).join('') || '<li class="muted">None recorded.</li>'}</ul></div>
        <div class="card"><h3 style="margin-bottom:10px">The brief, as pasted</h3><pre class="brief-text">${esc(d.brief) || 'No brief saved.'}</pre></div></div>` : ''}
      ${r.tab === 'memory' ? memoryBlock(d.id) : ''}
    </div>`;
  },
  live(r, d) {
    const out = {};
    if (r.tab === 'pipeline') {
      out.board = d.stages.map((s) => `<div class="col"><span class="col-k">${esc(s.label)} · ${s.key === 'ideas' ? d.ideas.length : s.clips.length}</span>
        ${s.key === 'ideas' ? d.ideas.map((x) => `<div class="idea">${esc(x)}</div>`).join('') : ''}
        ${s.clips.map((c) => `<a class="kcard${s.key === 'review' ? ' hi' : ''}" href="${href.review(c.id)}">
          ${c.thumb ? `<img src="${esc(c.thumb)}" alt="" loading="lazy">` : ''}
          <span class="kc-t">${esc(c.id)}${c.version ? ' v' + c.version : ''}</span>
          <span class="kc-d">${esc([c.style, c.duration ? c.duration.toFixed(1) + ' s' : null, c.status === 'changes_requested' ? 'changes asked' : null, c.slot && c.status === 'approved' ? 'booked' : null].filter(Boolean).join(' · '))}</span></a>`).join('')}
        ${!s.clips.length && s.key !== 'ideas' ? `<span class="col-hint">${{ making: 'Scripts, voice and renders in progress show here.', review: 'Nothing to review.', scheduled: 'Approved clips wait here for their slot.', live: 'A 30-minute submit timer starts when a post goes live.', paid: 'Submitted, approved, paid.' }[s.key]}</span>` : ''}
        ${s.key === 'ideas' ? '<span class="col-hint">Add ideas by telling this room.</span>' : ''}</div>`).join('');
      const rules = d.requirements.slice(0, 5).map((x) => `<div style="font-size:13px;color:var(--ink-2)">${esc(x)}</div>`).join('');
      out.cards = `
        <div class="card" style="display:flex;flex-direction:column;gap:8px"><div style="display:flex;justify-content:space-between"><h3>What Claude remembers here</h3><a href="${href.campaign(d.id, 'memory')}" style="color:var(--green);font-size:13px">Open</a></div>
          <div style="font-size:13px;color:var(--ink-2)">${esc(memoryExcerpt(d.memory))}</div>
          ${d.next ? `<div style="font-size:13px"><span class="muted">Next:</span> ${esc(d.next)}</div>` : ''}</div>
        <div class="card" style="display:flex;flex-direction:column;gap:8px"><div style="display:flex;justify-content:space-between"><h3>Rules</h3><a href="${href.campaign(d.id, 'rules')}" style="color:var(--green);font-size:13px">All ${d.requirements.length}</a></div>${rules || '<span class="muted">None recorded.</span>'}</div>
        <div class="card"><h3 style="margin-bottom:8px">Numbers</h3>
          <div class="kv"><span>Views</span><span>${num(d.money.views)}</span></div>
          <div class="kv"><span>Earned, estimated</span><span>${money(d.money.est)}</span></div>
          <div class="kv"><span>Clips made</span><span>${d.clips.length}</span></div>
          <div class="kv"><span>Posted</span><span>${d.clips.filter((c) => c.post).length}</span></div></div>`;
    }
    if (r.tab === 'memory') Object.assign(out, memoryLive(d.id, d.memory, d.memory_path));
    return out;
  },
};
function memoryExcerpt(md) {
  const m = /##\s*House style[^\n]*\n([\s\S]*?)(\n##|$)/i.exec(md || '');
  const text = (m ? m[1] : (md || '')).replace(/^\s*[-*]\s+/gm, '').replace(/[`*#|]/g, '').replace(/\s+/g, ' ').trim();
  return text.length > 260 ? text.slice(0, 257) + '…' : text || 'No memory yet.';
}

// Memory (shared by campaign tab and room page)
function memoryBlock(room) {
  return `<div class="card" style="display:flex;flex-direction:column;gap:12px" data-live="memory"></div>`;
}
function memoryLive(room, text, path) {
  if (S.editing && S.editing.room === room) return {};        // never overwrite an open editor
  return {
    memory: `<div style="display:flex;justify-content:space-between;align-items:center;gap:10px;flex-wrap:wrap">
        <div><h3>What Claude remembers</h3><div class="faint mono" style="font-size:12px">${esc(path || '')}</div></div>
        <button class="btn" data-edit-memory="${esc(room)}">Edit</button></div>
      <div class="md">${md(text) || '<p class="muted">Empty. Claude writes this as the room gets going.</p>'}</div>`,
  };
}
function openEditor(room) {
  const cur = S.data && (S.data.memory ?? S.data.text);
  const el = $('[data-live="memory"]');
  if (!el) return;
  S.editing = { room, base: cur ?? '' };
  el._html = null;
  el.innerHTML = `<form data-form="memory" style="display:flex;flex-direction:column;gap:10px">
      <div style="display:flex;justify-content:space-between;align-items:center"><h3>Editing memory</h3>
        <span class="faint" style="font-size:12px">Plain text. Claude reads this at the start of every chat in the room.</span></div>
      <label for="mem-text" class="sr-only">Memory</label>
      <textarea id="mem-text" class="editor" name="text" spellcheck="false">${esc(cur ?? '')}</textarea>
      <div style="display:flex;gap:8px;justify-content:flex-end"><button type="button" class="btn" data-cancel-edit>Cancel</button><button class="btn primary" type="submit">Save memory</button></div>
    </form>`;
  $('#mem-text').focus();
}

// minimal, safe markdown for memory files
function md(src) {
  if (!src) return '';
  const inline = (s) => esc(s).replace(/`([^`]+)`/g, '<code>$1</code>').replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>');
  const lines = src.split('\n');
  let out = '', list = false, table = [];
  const flushList = () => { if (list) { out += '</ul>'; list = false; } };
  const flushTable = () => {
    if (!table.length) return;
    const rows = table.filter((r) => !/^[\s|:-]+$/.test(r));       // drop the |---|---| separator row
    const cells = (r) => r.trim().replace(/^\||\|$/g, '').split('|').map((c) => c.trim());
    out += '<table>' + rows.map((r, i) => `<tr>${cells(r).map((c) => (i === 0 ? `<th>${inline(c)}</th>` : `<td>${inline(c)}</td>`)).join('')}</tr>`).join('') + '</table>';
    table = [];
  };
  for (const raw of lines) {
    const line = raw.trimEnd();
    if (/^\s*\|/.test(line)) { flushList(); table.push(line); continue; }
    flushTable();
    let m;
    if ((m = /^(#{1,3})\s+(.*)$/.exec(line))) { flushList(); out += `<h${m[1].length}>${inline(m[2])}</h${m[1].length}>`; continue; }
    if ((m = /^\s*[-*]\s+(.*)$/.exec(line))) { if (!list) { out += '<ul>'; list = true; } out += `<li>${inline(m[1])}</li>`; continue; }
    if (/^\s{2,}\S/.test(line) && list) { out = out.replace(/<\/li>$/, ' ' + inline(line.trim()) + '</li>'); continue; }
    flushList();
    if (line.trim()) out += `<p>${inline(line)}</p>`;
  }
  flushList(); flushTable();
  return out;
}

// Review
V.review = {
  focus: true,
  title: (r) => `Review ${r.id}`,
  load: (r) => get('clip/' + encodeURIComponent(r.id)),
  pickVersion(r, d) {
    const rendered = d.versions_list.filter((v) => v.rendered);
    const want = r.v || d.approved_version || (rendered.length ? rendered[rendered.length - 1].n : null);
    return rendered.find((v) => v.n === want) || rendered[rendered.length - 1] || null;
  },
  skeleton(r, d) {
    const v = this.pickVersion(r, d);
    const rendered = d.versions_list.filter((x) => x.rendered);
    const back = d.campaign ? href.campaign(d.campaign) : '#/';
    if (!v) return `<div class="page"><a href="${back}" class="muted">← Back</a><h1>${esc(d.id)}</h1><div class="empty">No rendered version yet.</div></div>`;
    const dur = v.duration || 1;
    const beats = (v.beats || []).map((b) => `<button class="tl-beat" style="left:${(b.t / dur) * 100}%" data-seek="${b.t}" title="${esc(tc(b.t) + ' · ' + b.label)}" aria-label="${esc('Jump to ' + b.label + ' at ' + tc(b.t))}"></button>`).join('');
    return `<div class="review">
      <header class="review-bar">
        <div class="left"><a href="${back}" class="muted" style="font-size:13px;white-space:nowrap">← ${esc(d.campaign_name || 'Back')}</a>
          <span class="review-title">${esc(d.id)}${d.style ? ' · ' + esc(d.style) : ''}</span>
          <nav class="seg" aria-label="Versions">${rendered.map((x) => `<a href="${href.review(d.id, x.n)}" class="${x.n === v.n ? 'on' : ''}" title="${esc((x.n === rendered[rendered.length - 1].n ? 'Latest. ' : '') + x.note)}"${x.n === v.n ? ' aria-current="page"' : ''}>v${x.n}${x.n === rendered[rendered.length - 1].n ? ' <span class="dot" style="vertical-align:1px"></span>' : ''}</a>`).join('')}</nav></div>
        <span class="keys">space play · ←→ frame · shift ←→ 1 s · N note</span>
      </header>
      <div class="review-body">
        <section class="player-col" aria-label="Player">
          <div class="video-wrap"><video id="vid" src="${esc(v.video)}" preload="auto" playsinline></video><span class="tc" id="tc">0:00.0 / ${tc(dur)}</span></div>
          <div class="timeline" id="tl" role="slider" aria-label="Position" aria-valuemin="0" aria-valuemax="${dur}" aria-valuenow="0" tabindex="0">
            <div class="tl-track"></div><div class="tl-fill" id="tl-fill"></div>${beats}<div data-live="tl-notes"></div><div class="tl-head" id="tl-head"></div></div>
          <div class="tl-legend"><span>${(v.beats || []).length ? '<span style="color:var(--amber)">●</span> meme beats · click to jump' : 'Click the bar to jump anywhere'}</span><span>${v.note ? esc(v.note.split(':')[0]) : ''}</span></div>
          <div class="transport"><button class="btn" data-step="-1">−1 s</button><button class="btn primary" id="playbtn" data-playpause>${ICON.play} Play</button><button class="btn" data-step="1">+1 s</button><button class="btn ghost" data-speed>1×</button><a class="btn" href="${esc(v.video)}" download="${esc(d.id)}_v${v.n}.mp4">Download v${v.n}</a></div>
        </section>
        <section class="details" aria-label="Details">
          <div class="stat-row" style="grid-template-columns:repeat(3,minmax(0,1fr))" data-live="r-stats"></div>
          <div class="section"><div class="section-head"><h2>Notes at a moment</h2><span class="faint" style="font-size:12px">Claude gets the clip, version and exact time</span></div>
            <form class="note-form" data-form="note" autocomplete="off"><span class="at" id="note-at">@ 0:00.0</span>
              <label for="note-text" class="sr-only">Note</label><input id="note-text" name="text" placeholder="Pause anywhere, then say what to change"><button class="btn" type="submit">Add note</button></form>
            <div data-live="r-notes"></div></div>
          <div class="section" data-live="r-actions"></div>
          <div class="section" data-live="r-kit"></div>
          <details class="section"><summary class="muted" style="cursor:pointer">Automated checks and version notes</summary><div data-live="r-checks" style="margin-top:10px"></div></details>
        </section>
      </div></div>`;
  },
  live(r, d) {
    const v = this.pickVersion(r, d);
    if (!v) return {};
    const dur = v.duration || 1;
    const notes = d.notes.filter((n) => !n.resolved_at);
    const checks = v.checks;
    const passed = checks ? checks.filter((c) => c.ok).length : null;
    const statusPill = { needs_review: ['amber', 'Needs your review'], approved: ['green', 'Approved'], changes_requested: ['amber', 'Changes asked'], rejected: ['red', 'Rejected'], posted: ['green', 'Live'], submitted: ['green', 'Submitted'] }[d.status] || ['', d.status];
    return {
      'tl-notes': notes.filter((n) => !n.version || n.version === v.n).map((n) => `<button class="tl-note" style="left:${(n.t / dur) * 100}%" data-seek="${n.t}" title="${esc(tc(n.t) + ' · ' + n.text)}" aria-label="${esc('Note at ' + tc(n.t))}"></button>`).join(''),
      'r-stats': `
        <div class="stat"><span class="stat-k">Status</span><span style="padding-top:4px"><span class="pill ${statusPill[0]}" style="white-space:normal;display:inline-block">${esc(statusPill[1])}</span></span></div>
        <div class="stat"><span class="stat-k">Length</span><span class="stat-v">${v.duration ? v.duration.toFixed(1) + ' s' : '—'}</span></div>
        <div class="stat"><span class="stat-k">Automated checks</span><span class="stat-v" style="${passed === checks?.length ? 'color:var(--green)' : ''}">${checks ? `${passed} of ${checks.length}` : 'from v' + (d.version || '?')}</span></div>`,
      'r-notes': notes.length ? notes.map((n) => `<div class="note"><button class="at" data-seek="${n.t}">${tc(n.t)}</button><div style="flex:1">${esc(n.text)}${n.version && n.version !== v.n ? ` <span class="faint">(v${n.version})</span>` : ''}</div>
          <button class="btn ghost" style="height:26px;padding:0 6px" data-do="${j({ type: 'note_delete', note: n.id })}" aria-label="Delete note">${ICON.x}</button></div>`).join('')
        : '<div class="faint" style="font-size:13px;padding:4px 0">No notes. They go to Claude when you press Request changes.</div>',
      'r-actions': actionsFor(d, v),
      'r-kit': kitFor(d),
      'r-checks': (checks ? `<ul class="checks">${checks.map((c) => `<li><span class="${c.ok ? 'ok' : 'bad'}">${c.ok ? '✓' : '✗'}</span><span>${esc(c.check)}: <span class="muted">${esc(c.detail)}</span></span></li>`).join('')}</ul>`
        : `<p class="muted" style="font-size:13px;margin:0">Checks are saved for the latest render only (v${d.version}).</p>`)
        + `<div style="margin-top:12px;display:flex;flex-direction:column;gap:6px">${d.versions_list.slice().reverse().map((x) => `<div style="font-size:13px"><span class="mono">v${x.n}</span> <span class="muted">${esc(x.note || '')}</span></div>`).join('')}</div>`,
    };
  },
  mount(r, d) { mountPlayer(d, this.pickVersion(r, d)); },
  unmount() { unmountPlayer(); },
};

function actionsFor(d, v) {
  const slots = d.slots.map((s) => `<option value="${esc(s.value)}"${d.slot === s.value ? ' selected' : ''}>${esc(s.label)}</option>`).join('');
  if (['needs_review', 'changes_requested', 'rejected'].includes(d.status)) {
    const waiting = d.status === 'changes_requested' ? '<div class="work"><span class="dot amber" style="margin-top:6px"></span><span>You asked for changes. Claude will make a new version; it appears here when it\'s rendered.</span></div>' : '';
    return `<h2>Decision</h2>${waiting}
      <form class="action-bar" data-form="approve"><input type="hidden" name="version" value="${v.n}">
        <label for="slot" class="sr-only">Posting slot</label><select id="slot" name="slot"><option value="">No slot yet</option>${slots}</select>
        <button class="btn primary big" type="submit">Approve v${v.n}</button>
        <button class="btn big" type="button" data-toggle="changes-form">Request changes</button>
        <button class="btn big ghost danger" type="button" data-do="${j({ type: 'reject', clip: d.id })}" data-confirm="Reject ${esc(d.id)}? It won't be posted.">Reject</button></form>
      <form data-form="changes" id="changes-form" hidden style="display:flex;flex-direction:column;gap:8px">
        <label for="changes-text" class="muted" style="font-size:13px">What should change? Your notes at a moment are sent along too.</label>
        <textarea id="changes-text" class="field" name="text" placeholder="Make the ending shorter and swap the gulp for a slurp"></textarea>
        <div><button class="btn primary" type="submit">Send to Claude</button></div></form>`;
  }
  if (d.status === 'approved') {
    return `<h2>Approved v${d.approved_version || v.n}${d.slot ? ' · ' + esc(d.slots.find((s) => s.value === d.slot)?.label || d.slot) : ''}</h2>
      <ol style="margin:0;padding-left:20px;display:flex;flex-direction:column;gap:6px;font-size:13px;color:var(--ink-2)">
        <li>Download the video and copy the posting kit below.</li>
        <li>${d.kit && d.kit.platform === 'instagram' ? 'Post it as a Reel on Instagram and paste the caption exactly. Don\'t add music in Instagram.' : 'Upload it in YouTube Studio as a Short. Paste the title and description, turn on the altered-content and paid-promotion labels.'}</li>
        <li>Paste the link here the moment it's live. Your 30-minute submit timer starts then.</li></ol>
      <div style="display:flex;gap:8px;flex-wrap:wrap"><a class="btn" href="${esc(v.video)}" download="${esc(d.id)}_v${v.n}.mp4">Download video</a>
        ${d.kit && d.kit.platform === 'instagram' ? '' : '<a class="btn" href="https://studio.youtube.com" target="_blank" rel="noopener">Open YouTube Studio ↗</a>'}
        <button class="btn ghost" data-do="${j({ type: 'unapprove', clip: d.id })}">Move back to review</button></div>
      <form class="note-form" data-form="posted" autocomplete="off"><label for="post-url" class="sr-only">Link to the live Short</label>
        <input id="post-url" name="url" inputmode="url" placeholder="${d.kit && d.kit.platform === 'instagram' ? 'https://instagram.com/reel/…' : 'https://youtube.com/shorts/…'}"><button class="btn primary" type="submit">It's live</button></form>`;
  }
  if (['posted', 'submitted'].includes(d.status) && (d.posts || []).length) {
    const now = Date.now();
    const rows = d.posts.map((p) => {
      const plat = p.platform === 'instagram' ? 'Instagram' : 'YouTube';
      if (p.submitted_at) return `<div class="kit-row"><div><div class="kv-k">${plat}</div><div class="kv-v">Submitted ${esc(when(p.submitted_at))} · <a href="${esc(p.url)}" target="_blank" rel="noopener" class="muted">${esc(p.url)} ↗</a></div></div></div>`;
      const deadline = new Date(new Date(p.posted_at).getTime() + 30 * 60000).toISOString();
      return `<div class="row urgent" style="border-radius:12px"><div class="row-body"><span class="row-title">Submit the ${plat} post on Content Rewards</span>
        <span class="row-detail">Within 30 minutes of it going live · <a href="${esc(p.url)}" target="_blank" rel="noopener">${esc(p.url)} ↗</a></span></div>
        <div class="row-actions"><span class="countdown" data-deadline="${esc(deadline)}"></span><button class="btn" data-copy="${esc(p.url)}" data-copy-label="Link copied">Copy link</button>
        <button class="btn amber" data-do="${j({ type: 'submitted', post: p.id })}">I submitted it</button></div></div>`;
    }).join('');
    const hasIg = d.posts.some((p) => p.platform === 'instagram'), hasYt = d.posts.some((p) => p.platform === 'youtube');
    const other = !hasIg ? 'Instagram' : !hasYt ? 'YouTube' : null;
    return `<h2>Live on ${d.posts.map((p) => (p.platform === 'instagram' ? 'Instagram' : 'YouTube')).join(' + ')}</h2>${rows}
      ${other ? `<form class="note-form" data-form="posted" autocomplete="off"><label for="post-url" class="sr-only">Link</label>
        <input id="post-url" name="url" inputmode="url" placeholder="Posted it on ${other} too? Paste the ${other === 'Instagram' ? 'Reel' : 'Short'} link"><button class="btn" type="submit">Add</button></form>` : ''}`;
  }
  if (d.status === 'posted' && d.post) {
    const deadline = new Date(new Date(d.post.posted_at).getTime() + 30 * 60000).toISOString();
    return `<h2>Live · submit it now</h2>
      <div class="row urgent" style="border-radius:12px"><div class="row-body"><span class="row-title">Submit on Content Rewards</span><span class="row-detail">It only counts if you submit within 30 minutes of going live.</span></div>
        <div class="row-actions"><span class="countdown" data-deadline="${esc(deadline)}"></span><button class="btn" data-copy="${esc(d.post.url)}" data-copy-label="Link copied">Copy link</button>
        <button class="btn amber" data-do="${j({ type: 'submitted', post: d.post.id })}">I submitted it</button></div></div>
      <a href="${esc(d.post.url)}" target="_blank" rel="noopener" class="muted" style="font-size:13px">${esc(d.post.url)} ↗</a>`;
  }
  if (d.status === 'submitted' && d.post) {
    return `<h2>Submitted</h2><div class="muted" style="font-size:13px">Went live ${esc(when(d.post.posted_at))}, submitted ${esc(when(d.post.submitted_at))}. Views are tracked from here.</div>
      <a href="${esc(d.post.url)}" target="_blank" rel="noopener" class="muted" style="font-size:13px">${esc(d.post.url)} ↗</a>`;
  }
  return `<h2>${esc(d.status)}</h2>`;
}
function kitFor(d) {
  const k = d.kit;
  if (!k) return '<h2>Posting kit</h2><div class="faint" style="font-size:13px">No post.json yet. Ask Claude to write the posting kit.</div>';
  const row = (label, value, copyable = true) => value ? `<div class="kit-row"><div style="min-width:0"><div class="kv-k">${esc(label)}</div><div class="kv-v">${esc(value)}</div></div>
    ${copyable ? `<button class="btn" data-copy="${esc(value)}" data-copy-label="${esc(label)} copied">Copy</button>` : ''}</div>` : '';
  const flags = [k.synthetic_media ? 'Altered or synthetic content: Yes' : null, k.paid_promotion ? 'Paid promotion: on' : null,
    /Music:/.test(k.description || '') ? 'Music credit in description' : null].filter(Boolean);
  if (k.platform === 'instagram') {
    return `<h2>Posting kit · Instagram</h2><div class="card" style="padding:4px 16px">
      ${row('Caption (paste as-is, line breaks matter)', k.caption)}${row('On-screen text (already in the video)', k.on_screen_text, false)}
      ${(k.checklist || []).length ? `<div class="kit-row"><div><div class="kv-k">Before you post</div><ul class="rules" style="margin-top:6px;font-size:13px">${k.checklist.map((c) => `<li>${esc(c)}</li>`).join('')}</ul></div></div>` : ''}</div>`;
  }
  return `<h2>Posting kit</h2><div class="card" style="padding:4px 16px">
    ${row('Title', k.title)}${row('Description', k.description)}${row('Tags', [].concat(k.tags || []).join(', '))}${row('Pinned comment (you pin it)', k.pinned_comment)}
    ${row('Instagram caption (same video as a Reel)', k.instagram_caption)}
    ${flags.length ? `<div class="kit-row"><div><div class="kv-k">Settings to tick in YouTube Studio</div><div class="chips" style="margin-top:6px">${flags.map((f) => `<span class="pill">${esc(f)}</span>`).join('')}</div></div></div>` : ''}</div>`;
}

// player
const P = { vid: null, raf: 0, noteT: null, dur: 1, key: null, version: null, clip: null };
function mountPlayer(d, v) {
  if (!v) return;
  const vid = $('#vid');
  P.vid = vid; P.dur = v.duration || 1; P.version = v.n; P.clip = d.id; P.noteT = null;
  const tick = () => {
    const t = vid.currentTime || 0, dur = vid.duration || P.dur;
    const pct = Math.min(100, (t / dur) * 100);
    $('#tl-fill').style.width = pct + '%';
    $('#tl-head').style.left = pct + '%';
    $('#tc').textContent = `${tc(t)} / ${tc(dur)}`;
    $('#tl').setAttribute('aria-valuenow', t.toFixed(1));
    if (P.noteT == null) $('#note-at').textContent = '@ ' + tc(t);
    P.raf = requestAnimationFrame(tick);
  };
  P.raf = requestAnimationFrame(tick);
  const setBtn = () => { $('#playbtn').innerHTML = vid.paused ? `${ICON.play} Play` : `${ICON.pause} Pause`; };
  vid.addEventListener('play', setBtn); vid.addEventListener('pause', setBtn); vid.addEventListener('ended', setBtn);
  vid.addEventListener('loadedmetadata', () => { P.dur = vid.duration || P.dur; });
  vid.addEventListener('click', () => (vid.paused ? vid.play() : vid.pause()));
  vid.addEventListener('error', () => toast('This video file couldn’t be loaded. It may have been re-rendered or moved.', true));
  $('#tl').addEventListener('pointerdown', (e) => {
    if (e.target.closest('.tl-beat, .tl-note')) return;
    const rect = $('#tl').getBoundingClientRect();
    const seek = (x) => { vid.currentTime = Math.max(0, Math.min(1, (x - rect.left) / rect.width)) * (vid.duration || P.dur); P.noteT = null; };
    seek(e.clientX);
    const move = (ev) => seek(ev.clientX);
    const up = () => { removeEventListener('pointermove', move); removeEventListener('pointerup', up); };
    addEventListener('pointermove', move); addEventListener('pointerup', up);
  });
  const noteInput = $('#note-text');
  noteInput.addEventListener('focus', () => { vid.pause(); P.noteT = vid.currentTime; $('#note-at').textContent = '@ ' + tc(P.noteT); });
  noteInput.addEventListener('blur', () => { if (!noteInput.value.trim()) P.noteT = null; });
  P.key = (e) => {
    if (e.target.closest('input, textarea, select, [contenteditable]') || e.metaKey || e.ctrlKey || e.altKey) return;
    const step = e.shiftKey ? 1 : 1 / 30;
    if (e.code === 'Space') { e.preventDefault(); vid.paused ? vid.play() : vid.pause(); }
    else if (e.key === 'ArrowLeft') { e.preventDefault(); vid.pause(); vid.currentTime = Math.max(0, vid.currentTime - step); }
    else if (e.key === 'ArrowRight') { e.preventDefault(); vid.pause(); vid.currentTime = Math.min(vid.duration || P.dur, vid.currentTime + step); }
    else if (e.key === 'n' || e.key === 'N') { e.preventDefault(); noteInput.focus(); }
  };
  addEventListener('keydown', P.key);
}
function unmountPlayer() {
  cancelAnimationFrame(P.raf);
  if (P.key) removeEventListener('keydown', P.key);
  if (P.vid) { P.vid.pause(); P.vid.removeAttribute('src'); P.vid.load(); }
  Object.assign(P, { vid: null, raf: 0, key: null, noteT: null });
}

// Rooms
V.rooms = {
  title: 'Rooms and memory',
  load: () => get('rooms'),
  skeleton: () => `<div class="page">
    <div class="page-head"><div><h1>Rooms and memory</h1><p class="muted" style="margin:6px 0 0;max-width:720px">Each room is its own chat with Claude and its own memory file, so nothing leaks between campaigns.
      To start a room: open a new chat in the Claude app, paste the room's starter message, and name the chat after the room.</p></div></div>
    <div class="rooms" data-live="rooms"></div>
    <div class="card" style="display:flex;flex-direction:column;gap:10px"><h3>Say it short</h3>
      <div class="grid3" style="gap:10px 20px;font-size:13px">
        ${[['what needs me', 'the inbox, in order'], ['approve rag-002', 'same as the green button'], ['rag-002 at 8 seconds, move the emoji', 'clip + moment + change'],
          ['make 3 more for RAG', 'queued for that room'], ['new campaign + paste', 'scored, then join or skip'], ['wrap up', 'Claude saves the room memory']]
          .map(([a, b]) => `<div><div class="mono" style="color:var(--green)">${esc(a)}</div><div class="muted">${esc(b)}</div></div>`).join('')}</div></div>
  </div>`,
  live: (r, rooms) => ({
    rooms: rooms.map((m) => `<div class="card room${m.id === 'hq' ? ' here' : ''}">
      <div class="room-top"><span class="room-name">${esc(m.name)}</span><span class="pill${m.status === 'joined' ? ' green' : m.status === 'candidate' ? ' amber' : ''}">${esc({ home: 'home', joined: 'active', candidate: 'deciding', skipped: 'skipped', paused: 'paused', building: 'building' }[m.status] || m.status)}</span></div>
      <span style="font-size:13px;color:var(--ink-2)">${esc(m.about)}</span>
      ${m.next ? `<span style="font-size:13px"><span class="muted">Next:</span> ${esc(m.next)}</span>` : ''}
      <span class="room-meta">${m.memory_lines ? `memory: ${m.memory_lines} lines · updated ${esc(ago(m.memory_updated))}` : 'no memory yet'}${m.open_requests ? ` · ${plural(m.open_requests, 'message')} waiting` : ''}</span>
      <div class="btns"><button class="btn" data-copy="${esc(m.starter)}" data-copy-label="Starter message copied. Paste it in a new chat.">Copy starter message</button>
        <a class="btn" href="${m.kind === 'campaign' ? href.campaign(m.id, 'memory') : href.room(m.id)}">Memory</a>
        <button class="btn ghost" data-tell-room="${esc(m.id)}">Tell this room</button></div></div>`).join(''),
  }),
};

V.room = {
  title: (r) => ({ hq: 'HQ', lab: 'Studio Lab', influencer: 'AI influencer' }[r.id] || r.id) + ' memory',
  load: (r) => get('memory/' + encodeURIComponent(r.id)),
  skeleton: (r) => `<div class="page"><a href="#/rooms" class="muted" style="font-size:13px">← Rooms</a>
    <div class="page-head"><h1>${esc({ hq: 'HQ', lab: 'Studio Lab', influencer: 'AI influencer' }[r.id] || r.id)}</h1>
      <button class="btn" data-tell-room="${esc(r.id)}">Tell this room</button></div>${memoryBlock(r.id)}</div>`,
  live: (r, d) => memoryLive(r.id, d.text, d.path),
};

// Library
const audio = new Audio();
V.library = {
  title: 'Library',
  load: () => get('library'),
  unmount: () => { audio.pause(); $$('audio').forEach((a) => a.pause()); },
  skeleton: (r, d) => `<div class="page">
    <div class="page-head"><div><h1>Library</h1><p class="muted" style="margin:6px 0 0">Everything clips are built from. Click a sound to hear it.</p></div></div>
    <section class="section"><h2>Meme sounds · ${d.memes.length}</h2><div class="sounds">${d.memes.map((m) => `
      <button class="sound" data-sound="${esc(m.url)}"><span class="play">${ICON.play}</span><span style="min-width:0"><span style="display:block">${esc(m.name)}</span>
        <span class="faint" style="font-size:12px">${m.duration ? m.duration.toFixed(1) + ' s' : ''} · <span class="mono">${esc(m.id)}</span></span></span></button>`).join('') || '<div class="empty">No meme sounds imported.</div>'}</div></section>
    <section class="section"><h2>Background music</h2>${d.music.map((m) => `<div class="card" style="display:flex;align-items:center;gap:16px;flex-wrap:wrap;padding:12px 16px">
      <div style="min-width:220px"><div>${esc(m.name)}</div><div class="faint" style="font-size:12px">${esc(m.credit)}</div></div><audio controls preload="none" src="${esc(m.url)}" style="flex:1;min-width:240px"></audio></div>`).join('')}</section>
    <section class="section"><h2>Voice</h2>${d.voices.map((v) => v.url ? `<div class="card" style="display:flex;align-items:center;gap:16px;flex-wrap:wrap;padding:12px 16px"><div style="min-width:220px">${esc(v.name)}</div><audio controls preload="none" src="${esc(v.url)}" style="flex:1;min-width:240px"></audio></div>` : '').join('')}</section>
    <section class="section"><h2>Emoji stickers · ${d.emoji.length}</h2><div class="emoji">${d.emoji.map((e) => `<img src="${esc(e.url)}" alt="${esc(e.char)}" title="${esc(e.id)}">`).join('')}</div></section>
  </div>`,
};

// Money
V.money = {
  title: 'Money',
  load: () => get('money'),
  skeleton: (r, d) => {
    const est = d.campaigns.reduce((a, c) => a + c.est, 0), views = d.campaigns.reduce((a, c) => a + c.views, 0);
    return `<div class="page"><div class="page-head"><div><h1>Money</h1><p class="muted" style="margin:6px 0 0">Estimates use each campaign's rate and cap. Real payouts are what Content Rewards pays.</p></div></div>
    <div class="stat-row"><div class="stat"><span class="stat-k">Earned, estimated</span><span class="stat-v">${money(est)}</span></div>
      <div class="stat"><span class="stat-k">Views</span><span class="stat-v">${num(views)}</span></div>
      <div class="stat"><span class="stat-k">Posts</span><span class="stat-v">${d.posts.length}</span></div>
      <div class="stat"><span class="stat-k">Paid out</span><span class="stat-v">${money(d.posts.reduce((a, p) => a + (p.payout || 0), 0))}</span></div></div>
    <section class="section"><h2>By campaign</h2><div class="card" style="padding:4px 8px"><table class="tbl"><thead><tr><th>Campaign</th><th>Status</th><th>Rate</th><th>Views</th><th>Estimated</th></tr></thead><tbody>
      ${d.campaigns.map((c) => `<tr><td><a href="${href.campaign(c.id)}">${esc(c.name)}</a></td><td>${esc(STATUS[c.status] || c.status)}</td><td>${c.cpm != null ? money(c.cpm) + ' / 1K' : '—'}</td><td>${num(c.views)}</td><td>${money(c.est)}</td></tr>`).join('')}</tbody></table></div></section>
    <section class="section"><h2>Posts</h2>${d.posts.length ? `<div class="card" style="padding:4px 8px"><table class="tbl"><thead><tr><th>Clip</th><th>Live</th><th>Submitted</th><th>Views</th><th>Likes</th></tr></thead><tbody>
      ${d.posts.map((p) => `<tr><td><a href="${href.review(p.clip)}">${esc(p.clip)}</a></td><td>${esc(when(p.posted_at))}</td><td>${p.submitted_at ? esc(when(p.submitted_at)) : '<span class="pill amber">not yet</span>'}</td><td>${p.views != null ? num(p.views) : '—'}</td><td>${p.likes != null ? num(p.likes) : '—'}</td></tr>`).join('')}</tbody></table></div>`
      : '<div class="list"><div class="empty">No posts yet. Your first one shows up here the moment you mark it live.</div></div>'}</section></div>`;
  },
};

// Accounts
V.accounts = {
  title: 'Accounts',
  skeleton: () => `<div class="page"><div class="page-head"><div><h1>Accounts</h1><p class="muted" style="margin:6px 0 0">Channels the Studio posts to. Sign-ins live in your Mac's Keychain, never here.</p></div></div>
    <div class="rooms" data-live="accounts"></div></div>`,
  live: () => ({
    accounts: S.state.accounts.map((a) => {
      const w = a.warmup, pct = Math.min(100, (w.days_logged / w.needed) * 100);
      return `<div class="card room"><div class="room-top"><span class="room-name">${esc(a.handle)}</span><span class="pill${a.status === 'active' ? ' green' : ' amber'}">${a.status === 'active' ? 'ready to post' : esc(a.status)}</span></div>
        <span class="muted" style="font-size:13px">${esc(a.platform)}${a.channel ? ' · ' + esc(a.channel) : ''} · ${a.connected ? '<span class="ok">uploader connected</span>' : 'uploader not connected'}</span>
        ${a.status === 'warming' ? `<div style="display:flex;flex-direction:column;gap:6px"><div class="kv"><span>Warm-up</span><span>${w.days_logged} of ${w.needed} days</span></div><div class="progress"><i style="width:${pct}%"></i></div></div>
          <div class="btns">${w.done_today ? '<span class="muted" style="font-size:13px">Today is logged. Come back tomorrow.</span>' : `<button class="btn" data-do="${j({ type: 'warmup_done', account: a.id })}">Day ${w.days_logged + 1} done</button>`}</div>` : ''}</div>`;
    }).join('') || '<div class="empty">No accounts yet.</div>',
  }),
};

// Analytics: who watched, how long, from where, and what they said (YouTube; refreshed every 20 min)
const pctTone = (p, good, ok) => (p == null ? '' : p >= good ? 't-green' : p >= ok ? 't-amber' : 't-red');
function bars(list, key, val, { hl = () => false, unit = '%' } = {}) {
  if (!list || !list.length) return '<p class="muted" style="font-size:13px;margin:0">Not enough data yet.</p>';
  const max = Math.max(...list.map((x) => x[val]), 1);
  return `<div class="bars">${list.map((x) => `<div class="bar-row${hl(x) ? ' hl' : ''}"><span class="bar-k">${esc(x[key])}</span>
    <span class="bar"><i style="width:${Math.max(2, (x[val] / max) * 100)}%"></i></span><span class="bar-v">${unit === '%' ? x[val] + '%' : num(x[val])}</span></div>`).join('')}</div>`;
}
const T1 = new Set(['US', 'GB', 'CA', 'AU']);
function audienceCards(a) {
  return `<div class="an-grid">
    <div class="card"><h3 class="an-h">Countries</h3>${bars(a.countries, 'name', 'pct', { hl: (c) => T1.has(c.code) })}
      <p class="muted an-foot">Highlighted = tier 1 (US, UK, Canada, Australia): <b>${a.tier1_pct ?? '—'}%</b></p></div>
    <div class="card"><h3 class="an-h">Ages</h3>${bars(a.ages, 'group', 'pct', { hl: (x) => x.group === '13-17' || x.group === '18-24' })}
      <p class="muted an-foot">Our target is 13–17. Only signed-in viewers YouTube knows the age of are counted.</p></div>
    <div class="card"><h3 class="an-h">How people found it</h3>${bars(a.sources, 'name', 'views', { unit: 'n' })}</div></div>`;
}
function videoCard(v) {
  const a = v.analytics, eng = v.views ? ((v.likes + v.comments) / v.views) * 100 : null;
  const pill = v.privacy !== 'public' ? `<span class="pill amber">${v.privacy === 'private' && v.published_at ? 'scheduled ' + esc(when(v.published_at)) : esc(v.privacy)}</span>` : '';
  const stats = a ? `<div class="an-stats">
      <div class="kv"><span>Engaged views</span><span>${num(a.engaged)} <span class="muted">of ${num(a.views)}</span></span></div>
      <div class="kv"><span>Average watched</span><span class="${pctTone(a.avg_pct, 70, 55)}">${a.avg_pct}% · ${a.avg_s}s</span></div>
      <div class="kv"><span>Tier 1 viewers</span><span class="${pctTone(a.tier1_pct, 50, 30)}">${a.tier1_pct ?? '—'}%</span></div>
      <div class="kv"><span>Under 25</span><span class="${pctTone(a.under25_pct, 50, 30)}">${a.under25_pct ?? '—'}%</span></div>
      <div class="kv"><span>Shares · new subs</span><span>${num(a.shares)} · ${num(a.subs)}</span></div>
      <div class="kv"><span>Top countries</span><span>${(a.countries || []).slice(0, 3).map((c) => esc(c.name) + ' ' + c.pct + '%').join(' · ') || '—'}</span></div>
    </div>` : v.privacy === 'public' ? '<p class="muted" style="font-size:13px;margin:0">Audience numbers arrive 1–3 days after posting (YouTube’s delay). Views, likes and comments above are live.</p>' : '';
  const flags = (v.flags || []).map((f) => `<div class="flag ${f.level}">${esc(f.text)}</div>`).join('');
  const cl = v.comment_list || [];
  const cm = (c) => `<div class="cmt"><span class="cmt-a">${esc(c.author)}</span><span>${esc(c.text)}</span><span class="muted">${esc(ago(c.at))}${c.likes ? ' · ♥ ' + c.likes : ''}</span></div>`;
  const comments = cl.length ? `<div class="cmts">${cl.slice(0, 4).map(cm).join('')}${cl.length > 4 ? `<details><summary class="muted">All ${cl.length} comments</summary>${cl.slice(4).map(cm).join('')}</details>` : ''}</div>` : '';
  return `<div class="card an-video">
    <div class="an-top">${v.thumb ? `<img class="an-thumb" src="${esc(v.thumb)}" alt="" loading="lazy">` : ''}
      <div style="min-width:0;flex:1"><a class="an-title" href="${esc(v.url)}" target="_blank" rel="noopener">${esc(v.title)}</a>
        <div class="muted" style="font-size:13px">${v.published_at ? esc(when(v.published_at)) : ''}${v.clip ? ` · <a href="${href.review(v.clip)}">${esc(v.clip)}</a>` : ''} ${pill}</div>
        <div class="an-live"><b>${num(v.views)}</b> views · <b>${num(v.likes)}</b> likes · <b>${num(v.comments)}</b> comments${eng != null ? ` · <span class="${pctTone(eng, 2, 1)}">${eng.toFixed(1)}% engagement</span>` : ''}</div></div></div>
    ${flags}${stats}${comments}</div>`;
}
V.analytics = {
  title: 'Analytics',
  load: () => get('analytics'),
  skeleton: () => `<div class="page"><div class="page-head"><div><h1>Analytics</h1>
      <p class="muted" style="margin:6px 0 0">YouTube, read-only. Views, likes and comments are live; audience numbers run 1–3 days behind.</p></div>
      <button class="btn" data-do="${j({ type: 'analytics_refresh' })}">Refresh now</button></div><div data-live="an"></div></div>`,
  live: (r, d) => {
    const s = d && d.snapshot;
    const status = d.error ? `<div class="flag red">Couldn’t reach YouTube: ${esc(d.error)}</div>` : d.refreshing ? '<p class="muted" style="font-size:13px">Pulling fresh numbers from YouTube…</p>' : '';
    if (!s) return { an: status || '<div class="empty">No numbers yet. Click Refresh now.</div>' };
    const days = s.days || [], v7 = days.slice(-7).reduce((x, y) => x + y.views, 0);
    return { an: `${status}<p class="muted" style="font-size:13px;margin:0 0 12px">${esc(s.channel)} · updated ${esc(ago(s.taken_at))} · audience data through ${esc(s.data_through || '—')}</p>
      <div class="stat-row"><div class="stat"><span class="stat-k">Channel views</span><span class="stat-v">${num(s.totals.views)}</span></div>
        <div class="stat"><span class="stat-k">Subscribers</span><span class="stat-v">${num(s.totals.subs)}</span></div>
        <div class="stat"><span class="stat-k">Tier 1 viewers (28 days)</span><span class="stat-v ${pctTone(s.audience.tier1_pct, 50, 30)}">${s.audience.tier1_pct ?? '—'}%</span></div>
        <div class="stat"><span class="stat-k">Aged 13–17 (28 days)</span><span class="stat-v ${pctTone(s.audience.teen_pct, 30, 15)}">${s.audience.teen_pct ?? '—'}%</span></div></div>
      <section class="section"><h2>Your Shorts</h2><div class="an-list">${s.videos.map(videoCard).join('') || '<div class="empty">No uploads yet.</div>'}</div></section>
      <section class="section"><h2>Who’s watching the channel <span class="muted" style="font-weight:400;font-size:14px">last 28 days</span></h2>${audienceCards(s.audience)}</section>` };
  },
};

// Finds: links and ideas Rishi spots while scrolling. Saved for later; nothing is acted on.
V.finds = {
  title: 'Finds',
  load: () => get('finds'),
  skeleton: () => `<div class="page"><div class="page-head"><div><h1>Finds</h1>
      <p class="muted" style="margin:6px 0 0">Things you spot online (repos, tools, reels). Kept for later. Nothing here is acted on until you ask.</p></div></div>
    <form class="note-form" data-form="find" autocomplete="off" style="margin-bottom:16px">
      <label for="find-url" class="sr-only">Link</label><input id="find-url" name="url" placeholder="Paste a link (optional)" style="flex:1">
      <label for="find-note" class="sr-only">Note</label><input id="find-note" name="note" placeholder="What is it / why save it?" style="flex:2">
      <button class="btn" type="submit">Save</button></form>
    <div class="an-list" data-live="finds"></div></div>`,
  live: (r, d) => ({
    finds: d.finds.map((f) => `<div class="card" style="display:flex;flex-direction:column;gap:8px">
      <div style="display:flex;justify-content:space-between;gap:12px;align-items:baseline">
        ${f.url ? `<a class="an-title" href="${esc(f.url)}" target="_blank" rel="noopener">${esc(f.title)} ↗</a>` : `<span class="an-title">${esc(f.title)}</span>`}
        <span class="muted" style="font-size:12px;white-space:nowrap">${esc(ago(f.added_at))}</span></div>
      ${f.note ? `<div style="font-size:14px;color:var(--ink-2);white-space:pre-wrap">${esc(f.note)}</div>` : ''}
      <div style="display:flex;gap:6px;flex-wrap:wrap;align-items:center">${f.tags.map((t) => `<span class="pill">${esc(t)}</span>`).join('')}
        ${f.source ? `<span class="muted" style="font-size:12px">from ${esc(f.source)}</span>` : ''}
        <button class="btn ghost" style="margin-left:auto;height:28px" data-do="${j({ type: 'find_archive', find: f.id })}" data-confirm="Archive this find?">Archive</button></div></div>`).join('')
      || '<div class="empty">Nothing saved yet. Paste a link above, or just send it to Claude in chat.</div>',
  }),
};


// Schedule: every post for the night, each field ready to copy, a box for the link once it's scheduled
const copyBox = (label, text, big) => `<div class="sc-field"><div class="sc-k"><span>${esc(label)}</span>
  <button class="btn" style="height:28px" data-copy="${esc(text)}" data-copy-label="${esc(label)} copied">Copy</button></div>
  <div class="sc-v${big ? ' big' : ''}">${esc(text)}</div></div>`;
const platBlock = (e, plat) => {
  const p = e[plat], yt = plat === 'youtube';
  const acct = yt ? e.account_youtube : e.account_instagram;
  const fields = yt ? copyBox('Title', p.title, true) + copyBox('Description', p.description) + copyBox('Tags', p.tags)
    : copyBox('Caption', p.caption);
  const file = yt ? e.yt_file : e.ig_file, ok = yt ? e.yt_file_ok : e.ig_file_ok;
  return `<div class="sc-plat">
    <div class="sc-plat-head"><b>${yt ? 'YouTube' : 'Instagram'}</b> <span class="muted">${esc(acct)}</span>
      ${p.submitted ? '<span class="pill">submitted ✓</span>' : p.link ? '<span class="pill">scheduled ✓</span>' : '<span class="pill amber">to do</span>'}</div>
    <div class="sc-file"><span class="mono">${esc(file.split('/').slice(-2).join('/'))}</span>
      <button class="btn" style="height:28px" data-do="${j({ type: 'reveal', path: file })}"${ok ? '' : ' disabled'}>Show in Finder</button></div>
    ${fields}
    <details class="sc-set"><summary>Settings checklist (${p.settings.length})</summary><ol>${p.settings.map((x) => `<li>${esc(x)}</li>`).join('')}</ol></details>
    ${copyBox('Pinned comment (post it after it goes live)', p.pinned_comment)}
    <form class="sc-link" data-form="sched_link" data-post="${esc(e.id)}" data-platform="${plat}" autocomplete="off">
      <input name="url" value="${esc(p.link || '')}" inputmode="url" placeholder="${yt ? 'Paste the YouTube link once it’s scheduled' : 'Paste the reel link once it’s live'}">
      <button class="btn primary" type="submit">Save link</button></form>
  </div>`;
};
V.schedule = {
  title: 'Schedule',
  load: () => get('schedule'),
  skeleton: (r, d) => `<div class="page"><div class="page-head"><div><h1>Schedule</h1>
    <p class="muted" style="margin:6px 0 0">Schedule each post on YouTube and Instagram with the text below, then paste its link here. When they go live, open <a href="#/links">Links to submit</a> for Content Rewards.</p></div></div>
    <div data-live="sched"></div></div>`,
  live: (r, d) => ({
    sched: d.posts.length ? d.posts.map((e) => `<section class="card sc-card" id="${esc(e.id)}">
      <div class="sc-head">
        <div class="sc-time"><span class="sc-big">${esc(e.label)}</span><span class="muted">${esc(e.day)} · ${esc(e.at_ny)} New York</span></div>
        <div class="sc-who"><span class="pill">${esc(e.account_name)}</span><span class="pill">${esc(e.campaign_name)}</span><span class="mono faint">${esc(e.clip)} v${e.version}</span></div>
      </div>
      <div class="sc-body">
        <div class="sc-vid">${e.preview_url ? `<video src="${esc(e.preview_url)}" controls preload="none" poster="${esc(e.thumb || '')}" playsinline></video>` : ''}</div>
        <div class="sc-plats">${(e.platforms || ['youtube', 'instagram']).map((p) => platBlock(e, p)).join('')}</div>
      </div>
      <div class="faint" style="font-size:12px">${esc(e.submit_rule)}</div>
    </section>`).join('') : '<div class="empty">Nothing scheduled. Ask Claude to plan tonight.</div>',
  }),
};
V.links = {
  title: 'Links to submit',
  load: () => get('schedule'),
  skeleton: () => `<div class="page"><div class="page-head"><div><h1>Links to submit</h1>
    <p class="muted" style="margin:6px 0 0">Grouped by campaign. Submit each on Content Rewards within 30 minutes of it going live, then tick it.</p></div></div>
    <div data-live="links"></div></div>`,
  live: (r, d) => {
    const camps = [...new Set(d.posts.map((e) => e.campaign_name))];
    return { links: camps.map((c) => {
      const rows = d.posts.filter((e) => e.campaign_name === c).sort((a, b) => a.at.localeCompare(b.at))
        .flatMap((e) => (e.platforms || ['youtube', 'instagram']).map((plat) => ({ e, plat, p: e[plat] })));
      const all = rows.filter((x) => x.p.link).map((x) => x.p.link).join('\n');
      return `<section class="section"><div class="section-head"><h2>${esc(c)}</h2>${all ? `<button class="btn" data-copy="${esc(all)}" data-copy-label="All ${esc(c)} links copied">Copy all</button>` : ''}</div>
        <div class="card" style="padding:4px 8px"><table class="tbl"><thead><tr><th>Live at</th><th>Account</th><th>Where</th><th>Clip</th><th>Link</th><th></th></tr></thead><tbody>
        ${rows.map(({ e, plat, p }) => `<tr><td>${esc(e.label)}${e.live ? '' : ` <span class="faint">(in ${e.mins_to_live} min)</span>`}</td><td>${esc(e.account_name)}</td><td>${plat === 'youtube' ? 'YouTube' : 'Instagram'}</td><td class="mono">${esc(e.clip)}</td>
          <td>${p.link ? `<a href="${esc(p.link)}" target="_blank" rel="noopener" class="mono">${esc(p.link.replace(/^https:\/\/(www\.)?/, ''))}</a>` : `<a href="#/schedule" class="faint">add link</a>`}</td>
          <td style="white-space:nowrap">${p.link ? `<button class="btn" style="height:28px" data-copy="${esc(p.link)}" data-copy-label="Link copied">Copy</button>
            <button class="btn${p.submitted ? '' : ' amber'}" style="height:28px" data-do="${j({ type: 'sched_tick', post: e.id, platform: plat, field: 'submitted', value: !p.submitted })}">${p.submitted ? 'Submitted ✓' : 'I submitted it'}</button>` : ''}</td></tr>`).join('')}
        </tbody></table></div></section>`;
    }).join('') || '<div class="empty">No posts yet.</div>' };
  },
};

V.notfound = { title: 'Not found', skeleton: () => '<div class="page"><h1>That page doesn’t exist</h1><a class="btn" href="#/">Back to Today</a></div>' };

// ---------- render loop ----------
async function go() {
  const r = parseRoute();
  const prev = S.route && V[S.route.name];
  if (prev && prev.unmount) prev.unmount();
  S.route = r; S.editing = null;
  const view = V[r.name] || V.notfound;
  const shellEl = $('#shell');
  shellEl.classList.toggle('focus', !!view.focus);
  shellEl.classList.remove('dock-open');
  const seq = ++S.loadSeq;
  const main = $('#main');
  renderChrome();
  // never leave the previous page on screen while this one loads
  const slow = view.load ? setTimeout(() => { if (seq === S.loadSeq) main.innerHTML = '<p class="skeleton">Loading…</p>'; }, 120) : 0;
  try {
    S.data = view.load ? await view.load(r) : null;
    clearTimeout(slow);
    if (seq !== S.loadSeq) return;                    // a newer navigation won
    main.innerHTML = view.skeleton(r, S.data);
    document.title = `${typeof view.title === 'function' ? view.title(r, S.data) : view.title} · Studio`;
    renderChrome();
    if (view.live) patch(view.live(r, S.data));
    if (view.mount) view.mount(r, S.data);
    main.scrollTop = 0;
    tickCountdowns();
  } catch (e) {
    clearTimeout(slow);
    if (seq !== S.loadSeq) return;
    main.innerHTML = `<div class="page"><h1>Couldn’t open this page</h1><p class="muted">${esc(e.message)}</p><div style="display:flex;gap:8px"><button class="btn" data-retry>Try again</button><a class="btn" href="#/">Back to Today</a></div></div>`;
    renderChrome();
  }
}

function renderChrome() {
  if (!S.state) return;
  const rl = $('#rail'); const h = rail();
  if (rl._html !== h) { rl.innerHTML = h; rl._html = h; }
  roomOptions();
  patch(dockLive());
}

let refreshing = null, again = false;
async function refresh() {
  if (refreshing) { again = true; return refreshing; }      // one more pass after this one finishes
  refreshing = (async () => {
    try {
      S.state = await get('state');
      banner(null);
      const view = V[S.route?.name];
      if (view && view.load && S.route) {
        try { S.data = await view.load(S.route); } catch { /* page data vanished: keep last */ }
      }
      renderChrome();
      if (view && view.live) patch(view.live(S.route, S.data));
      tickCountdowns();
    } catch (e) {
      // only a failed request means the server is down; anything else is a page bug, so say what it is
      banner(e instanceof TypeError && /fetch/i.test(e.message) ? 'Can’t reach the Studio server. Start it with: uv run studio web'
             : `Page error: ${e.message}`);
      console.error(e);
    } finally {
      refreshing = null;
      if (again) { again = false; refresh(); }
    }
  })();
  return refreshing;
}

function tickCountdowns() {
  for (const el of $$('[data-deadline]')) {
    const left = Math.round((new Date(el.dataset.deadline) - Date.now()) / 1000);
    const m = Math.floor(Math.abs(left) / 60), s = String(Math.abs(left) % 60).padStart(2, '0');
    el.textContent = left >= 0 ? `${m}:${s} left` : `late by ${m}:${s}`;
    el.style.color = left >= 0 ? (left < 300 ? 'var(--red)' : 'var(--amber)') : 'var(--red)';
  }
}

// ---------- live connection ----------
function connect() {
  const es = new EventSource('/api/stream');
  es.onopen = () => { const was = S.conn; S.conn = 'live'; renderChrome(); if (was === 'reconnecting') refresh(); };   // resync after an outage
  es.onmessage = (e) => {
    if (e.data !== S.version) { const first = S.version == null; S.version = e.data; if (!first) refresh(); }
  };
  es.onerror = () => { S.conn = 'reconnecting'; renderChrome(); };
}

// ---------- interactions ----------
document.addEventListener('click', async (e) => {
  const t = e.target.closest('[data-do],[data-copy],[data-seek],[data-filter],[data-fill],[data-tell-room],[data-sound],[data-watch],[data-toggle],[data-edit-memory],[data-cancel-edit],[data-toggle-skipped],[data-playpause],[data-step],[data-speed],[data-palette],[data-dock-open],[data-dock-close],[data-mic],[data-retry]');
  if (!t) return;
  const d = t.dataset;
  if (d.do !== undefined) {
    e.preventDefault();
    if (d.confirm && !confirm(d.confirm)) return;
    try { await act(JSON.parse(d.do), t); } catch { /* toast already shown */ }
  } else if (d.copy !== undefined) { e.preventDefault(); copy(d.copy, d.copyLabel || 'Copied'); }
  else if (d.seek !== undefined) { if (P.vid) { P.vid.pause(); P.vid.currentTime = Number(d.seek); P.noteT = null; } }
  else if (d.filter) { S.filter = d.filter; patch(V.today.live()); }
  else if (d.fill !== undefined) {
    const ta = $('#talk-text'); openDock();
    if (d.fillRoom) { S.room = d.fillRoom; roomOptions(); if ([...$('#talk-room').options].some((o) => o.value === d.fillRoom)) $('#talk-room').value = d.fillRoom; }
    ta.value = d.fill; ta.focus(); ta.setSelectionRange(ta.value.length, ta.value.length);
  }
  else if (d.tellRoom) { S.room = d.tellRoom; roomOptions(); $('#talk-room').value = d.tellRoom; openDock(); $('#talk-text').focus(); }
  else if (d.sound) playSound(t, d.sound);
  else if (d.watch) watch(d.watch, d.watchTitle);
  else if (d.toggle) { const el = document.getElementById(d.toggle); if (el) { el.hidden = !el.hidden; if (!el.hidden) $('textarea', el)?.focus(); } }
  else if (d.editMemory) openEditor(d.editMemory);
  else if (d.cancelEdit !== undefined) { S.editing = null; const el = $('[data-live="memory"]'); if (el) el._html = null; refresh(); }
  else if (d.toggleSkipped !== undefined) { S.showSkipped = !S.showSkipped; renderChrome(); }
  else if (d.playpause !== undefined) { if (P.vid) P.vid.paused ? P.vid.play() : P.vid.pause(); }
  else if (d.step) { if (P.vid) { P.vid.currentTime = Math.max(0, P.vid.currentTime + Number(d.step)); P.noteT = null; } }
  else if (d.speed !== undefined) { if (P.vid) { P.vid.playbackRate = P.vid.playbackRate === 1 ? 0.5 : 1; t.textContent = P.vid.playbackRate + '×'; } }
  else if (d.palette !== undefined) palette();
  else if (d.dockOpen !== undefined) openDock();
  else if (d.dockClose !== undefined) $('#shell').classList.remove('dock-open');
  else if (d.mic !== undefined) mic(t);
  else if (d.retry !== undefined) { if (S.state) go(); else location.reload(); }
});

function openDock() { if (innerWidth <= 1280) $('#shell').classList.add('dock-open'); }
// tapping outside the sliding Claude panel closes it
document.addEventListener('pointerdown', (e) => {
  const sh = $('#shell');
  if (sh && sh.classList.contains('dock-open') && !e.target.closest('#dock, [data-dock-open], [data-fill], [data-tell-room]')) sh.classList.remove('dock-open');
});

document.addEventListener('submit', async (e) => {
  const f = e.target.closest('form[data-form]');
  if (!f) return;
  e.preventDefault();
  const fd = Object.fromEntries(new FormData(f).entries());
  const btn = $('button[type=submit]', f);
  const route = S.route || {};
  try {
    switch (f.dataset.form) {
      case 'tell':
        if (!fd.text.trim()) { toast('Write something first.', true); $('#talk-text').focus(); return; }
        S.room = fd.room;
        await act({ type: 'tell', room: fd.room, text: fd.text }, btn);
        f.reset(); roomOptions();
        break;
      case 'note': {
        if (!fd.text.trim()) { toast('Type the note first.', true); return; }
        const t = P.noteT ?? (P.vid ? P.vid.currentTime : 0);
        await act({ type: 'note', clip: route.id, version: P.version, t, text: fd.text }, btn);
        f.reset(); P.noteT = null; $('#note-text').blur();
        break;
      }
      case 'approve':
        await act({ type: 'approve', clip: route.id, version: Number(fd.version), slot: fd.slot || null }, btn);
        break;
      case 'changes':
        await act({ type: 'request_changes', clip: route.id, text: fd.text }, btn);
        break;
      case 'posted':
        if (!fd.url.trim()) { toast('Paste the link to the live Short first.', true); return; }
        await act({ type: 'posted', clip: route.id, url: fd.url.trim() }, btn);
        break;
      case 'sched_link':
        await act({ type: 'sched_link', post: f.dataset.post, platform: f.dataset.platform, url: (fd.url || '').trim() }, btn);
        break;
      case 'find':
        if (!fd.url.trim() && !fd.note.trim()) { toast('Paste a link or write a note first.', true); return; }
        await act({ type: 'find_add', url: fd.url.trim(), note: fd.note.trim() }, btn);
        f.reset();
        break;
      case 'memory': {
        const room = S.editing?.room;
        await act({ type: 'memory_save', room, text: fd.text, base: S.editing?.base }, btn);
        S.editing = null;
        const el = $('[data-live="memory"]'); if (el) el._html = null;
        await refresh();
        break;
      }
    }
  } catch { /* toast already shown */ }
});

// flush live updates that were held back while typing
document.addEventListener('focusout', () => { if (S.pending) { S.pending = false; setTimeout(refresh, 50); } });

// sounds
function playSound(btn, url) {
  const was = btn.classList.contains('playing');
  $$('.sound.playing').forEach((b) => { b.classList.remove('playing'); $('.play', b).innerHTML = ICON.play; });
  audio.pause();
  if (was) return;
  audio.src = url; audio.currentTime = 0;
  audio.play().then(() => { btn.classList.add('playing'); $('.play', btn).innerHTML = ICON.pause; }).catch(() => toast('Couldn’t play that sound.', true));
  audio.onended = () => { btn.classList.remove('playing'); $('.play', btn).innerHTML = ICON.play; };
}

// footage viewer
function watch(url, title) {
  const dlg = document.createElement('dialog');
  dlg.innerHTML = `<div class="dlg-head"><span class="mono">${esc(title)}</span><button class="btn ghost" data-close aria-label="Close">${ICON.x}</button></div>
    <div class="dlg-body" style="padding:0"><video src="${esc(url)}" controls autoplay playsinline style="display:block;width:min(88vw,700px);max-height:70vh;background:#000"></video></div>`;
  document.body.append(dlg);
  dlg.addEventListener('close', () => { $('video', dlg).pause(); dlg.remove(); });
  dlg.addEventListener('click', (e) => { if (e.target === dlg || e.target.closest('[data-close]')) dlg.close(); });
  dlg.showModal();
}

// voice input (when the browser supports it)
let rec = null;
function mic(btn) {
  const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
  if (!SR) return;
  if (rec) { rec.stop(); return; }
  const ta = $('#talk-text');
  const base = ta.value ? ta.value.trimEnd() + ' ' : '';
  rec = new SR(); rec.lang = 'en-IN'; rec.interimResults = true; rec.continuous = true;
  rec.onresult = (ev) => { let s = ''; for (const r of ev.results) s += r[0].transcript; ta.value = base + s; };
  rec.onerror = (ev) => { toast(ev.error === 'not-allowed' ? 'Microphone access is blocked for this page.' : 'Voice input stopped: ' + ev.error, true); };
  rec.onend = () => { btn.classList.remove('on'); rec = null; };
  btn.classList.add('on'); rec.start();
}

// ---------- ⌘K palette ----------
function palette() {
  if ($('dialog.palette')) return;
  const st = S.state || { campaigns: [], clips: [] };
  const items = [
    ['Today', '#/', 'page'], ['Rooms and memory', '#/rooms', 'page'], ['Money', '#/money', 'page'], ['Accounts', '#/accounts', 'page'], ['Library', '#/library', 'page'],
    ...st.campaigns.map((c) => [c.name, href.campaign(c.id), 'campaign']),
    ...st.clips.map((c) => [`${c.id}`, href.review(c.id), `clip · ${c.status.replace('_', ' ')}`]),
  ];
  const dlg = document.createElement('dialog');
  dlg.className = 'palette';
  dlg.innerHTML = `<label for="pal-in" class="sr-only">Jump to</label><input id="pal-in" placeholder="Jump to a page, campaign or clip… or type a message for Claude" autocomplete="off"><ul role="listbox"></ul>`;
  document.body.append(dlg);
  const input = $('input', dlg), ul = $('ul', dlg);
  let sel = 0, shown = [];
  const draw = () => {
    const q = input.value.trim().toLowerCase();
    shown = items.filter(([l]) => !q || l.toLowerCase().includes(q)).slice(0, 12);
    if (q) shown.push([`Tell Claude (HQ): “${input.value.trim()}”`, null, 'send']);
    sel = Math.min(sel, Math.max(0, shown.length - 1));
    ul.innerHTML = shown.map(([l, , k], i) => `<li role="option" aria-selected="${i === sel}" class="${i === sel ? 'sel' : ''}" data-i="${i}"><span>${esc(l)}</span><span class="k">${esc(k)}</span></li>`).join('')
      || '<li class="muted">Nothing matches.</li>';
  };
  const choose = async (i) => {
    const it = shown[i]; if (!it) return;
    dlg.close();
    if (it[1]) location.hash = it[1];
    else { try { await act({ type: 'tell', room: 'hq', text: input.value.trim() }); } catch { } }
  };
  input.addEventListener('input', () => { sel = 0; draw(); });
  input.addEventListener('keydown', (e) => {
    if (e.key === 'ArrowDown') { e.preventDefault(); sel = Math.min(shown.length - 1, sel + 1); draw(); }
    else if (e.key === 'ArrowUp') { e.preventDefault(); sel = Math.max(0, sel - 1); draw(); }
    else if (e.key === 'Enter') { e.preventDefault(); choose(sel); }
  });
  ul.addEventListener('click', (e) => { const li = e.target.closest('li[data-i]'); if (li) choose(Number(li.dataset.i)); });
  dlg.addEventListener('click', (e) => { if (e.target === dlg) dlg.close(); });
  dlg.addEventListener('close', () => dlg.remove());
  draw(); dlg.showModal(); input.focus();
}
addEventListener('keydown', (e) => {
  if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === 'k') { e.preventDefault(); palette(); }
});

// ---------- boot ----------
async function boot() {
  shell();
  try {
    S.state = await get('state');
    S.version = S.state.version;
  } catch (e) {
    $('#main').innerHTML = `<div class="page"><h1>The Studio server isn’t answering</h1><p class="muted">Start it with <span class="mono">uv run studio web</span>, then reload.</p><button class="btn" data-retry>Try again</button></div>`;
    return;
  }
  addEventListener('hashchange', go);
  addEventListener('focus', () => refresh());
  setInterval(tickCountdowns, 1000);
  setInterval(() => { if (document.visibilityState === 'visible') refresh(); }, 60000);
  connect();
  await go();
}
boot();
