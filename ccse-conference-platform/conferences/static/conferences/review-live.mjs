import { initializeAI, extractConference, listCandidates, getCandidate, submitDecision } from './ai-client.mjs';
const $ = id => document.getElementById(id);
const review = window.CCSEReview;
let permissions = {}, busy = false, page = 1, total = 0;
const pageSize = 20;
function controls() {
  $('connect').disabled = busy;
  $('extractLive').disabled = busy || !permissions.extract;
  $('refreshQueue').disabled = busy || !permissions.view_candidates;
  $('previousPage').disabled = busy || !permissions.view_candidates || page <= 1;
  $('nextPage').disabled = busy || !permissions.view_candidates || page * pageSize >= total;
  for (const button of $('liveQueue').querySelectorAll('button')) button.disabled = busy;
  for (const id of ['sample', 'clear', 'upload', 'original', 'export', 'reject']) {
    if (busy) { const node = $(id); node.dataset.beforeBusy = String(node.disabled); node.disabled = true; }
    else { const node = $(id); if (node.dataset.beforeBusy !== undefined) { node.disabled = node.dataset.beforeBusy === 'true'; delete node.dataset.beforeBusy; } }
  }
}
function showCandidate(candidate) {
  // End the UI lock before load() applies the new candidate's status controls.
  busy = false; controls();
  review.load(candidate);
}
function canReplace() {
  return !review.hasUnsavedEdits() || window.confirm('Replace the current edited candidate? Unsaved review edits will be discarded.');
}
async function operation(task) {
  if (busy) return;
  busy = true; controls();
  try { await task(); }
  catch (error) { review.message('API request failed: ' + error.message + ' If the connection failed after submission, reload the record to confirm its current status.'); }
  finally { busy = false; controls(); }
}
async function queue(targetPage = 1) {
  const data = await listCandidates({status: 'needs_review', page: targetPage, page_size: pageSize});
  if (!Array.isArray(data.results) || !Number.isInteger(data.count)) throw new Error('Unexpected candidate list response.');
  page = targetPage; total = data.count;
  $('queuePage').textContent = `Page ${page} · ${total} pending candidate(s)`;
  $('liveQueue').replaceChildren();
  for (const row of data.results) {
    const button = document.createElement('button'); button.type = 'button';
    button.textContent = `${row.summary?.conference_name || row.requested_url || 'Candidate'} · #${row.id} · ${row.warning_count ?? 0} warning(s)`;
    button.addEventListener('click', () => {
      if (busy || !canReplace()) return;
      operation(async () => {
        const candidate = await getCandidate(row.id);
        showCandidate(candidate);
        review.message(`Loaded candidate #${candidate.id} from the AI API. Current status: ${candidate.status}.`);
      });
    });
    $('liveQueue').append(button);
  }
  if (!data.results.length) $('liveQueue').textContent = 'No pending candidates on this page.';
}
$('connect').addEventListener('click', () => operation(async () => {
  permissions = {};
  $('connection').textContent = 'Connecting…';
  try {
    permissions = await initializeAI();
    $('connection').textContent = `Connected · ${permissions.view_candidates ? 'can view candidates' : 'no candidate-view permission'} · ${permissions.extract ? 'can extract' : 'no extraction permission'}`;
    if (permissions.view_candidates) {
      await queue();
      const wanted = Number(new URL(location.href).searchParams.get("candidate"));
      if (Number.isSafeInteger(wanted) && wanted > 0) showCandidate(await getCandidate(wanted));
    }
  } catch (error) { $('connection').textContent = 'Connection failed — check login and permissions'; throw error; }
}));
$('refreshQueue').addEventListener('click', () => operation(() => queue()));
$('previousPage').addEventListener('click', () => operation(() => queue(page - 1)));
$('nextPage').addEventListener('click', () => operation(() => queue(page + 1)));
$('extractForm').addEventListener('submit', event => {
  event.preventDefault();
  if (busy || !permissions.extract || !$('extractForm').reportValidity() || !canReplace()) return;
  const url = $('conferenceUrl').value.trim(), year = $('extractYear').value ? Number($('extractYear').value) : null;
  if (!/^https?:\/\//i.test(url)) { review.message('Supply an HTTP or HTTPS conference URL.'); return; }
  operation(async () => {
    review.message('Extraction is running. This may take time; no review decision will be saved.');
    const candidate = await extractConference(url, year, {max_pages: Number($('maxPages').value)});
    showCandidate(candidate);
    review.message(`Candidate #${candidate.id}: ${candidate.created ? 'new extraction' : 'unchanged sources; existing candidate reused'}. Current status: ${candidate.status}. No approval or rejection was submitted.`);
    try { await queue(); } catch { /* Retain the successfully loaded extraction. */ }
  });
});

window.addEventListener("ccse-review-decision", event => {
  if (busy) return;
  operation(async () => {
    const result = await submitDecision(event.detail.candidate_id, event.detail);
    showCandidate(result);
    const feedback = document.getElementById("feedback");
    review.message(result.status === "approved"
      ? "Approved and saved to the conference catalog. Reviewer corrections, dates, deadlines and prices are now persisted."
      : "Suggestion rejected. The official conference catalog was not changed.");
    if (result.conference_url) {
      const link = document.createElement("a");
      link.href = result.conference_url;
      link.textContent = "View saved conference →";
      link.className = "saved-conference-link";
      const wrap = document.createElement("p");
      wrap.append(link);
      feedback.append(wrap);
    }
    feedback.scrollIntoView({behavior:"smooth",block:"center"});
    await queue();
  });
});
// Restore the logged-in session and queue as soon as the workbench opens.
document.getElementById("connect").click();

