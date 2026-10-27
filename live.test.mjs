import { createRequire } from 'node:module';
import fs from 'node:fs';
import path from 'node:path';
import assert from 'node:assert/strict';
import { fileURLToPath } from 'node:url';
const require = createRequire(import.meta.url);
const { JSDOM } = require('jsdom');
const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const assets = path.join(root,'ccse-conference-platform/conferences/static/conferences');
const html = fs.readFileSync(path.join(root,'ccse-conference-platform/conferences/templates/conferences/review.html'),'utf8');
const dom = new JSDOM(html,{runScripts:'outside-only',url:'https://example.org/review/'});
const w = dom.window, $=id=>w.document.getElementById(id);
w.eval(fs.readFileSync(path.join(assets,'review.js'),'utf8'));
globalThis.window=w;globalThis.document=w.document;w.confirm=()=>true;
const fixture=JSON.parse(fs.readFileSync(path.join(root,'examples/synthetic-candidate.json'),'utf8'));
let candidate={id:7,status:'needs_review',created:true,payload:fixture};
let permitted=true,failDetail=false,emptyQueue=false,confirm=true;
w.confirm=()=>confirm;
const calls=[];
globalThis.fetch=async (url,options={})=>{
 calls.push({url,options});
 let data;
 if(url==='/api/ai/session/')data={csrf_token:'csrf-test',permissions:{view_candidates:true,extract:permitted}};
 else if(url.startsWith('/api/ai/candidates/?'))data={count:emptyQueue?0:21,page:1,page_size:20,results:emptyQueue?[]:[{id:7,status:'needs_review',summary:{conference_name:'Test conference'},warning_count:1}]};
 else if(url==='/api/ai/candidates/7/') {
  if(failDetail)return {redirected:false,ok:false,status:403,headers:{get:()=> 'application/json'},json:async()=>({error:'Denied'})};
  data=candidate;
 }else if(url==='/api/ai/extract/')data=candidate;
 else throw new Error('Unexpected route '+url);
 return {redirected:false,ok:true,status:200,headers:{get:()=> 'application/json'},json:async()=>data};
};
await import(path.join(assets,'review-live.mjs'));
const settle=()=>new Promise(r=>setTimeout(r,10));
$('connect').click();await settle();assert.match($('connection').textContent,/Connected/);assert.equal($('extractLive').disabled,false);assert.equal($('nextPage').disabled,false);
$('liveQueue').querySelector('button').click();await settle();assert.equal($('title').textContent,fixture.fields.conference_name.value);assert.equal($('status').textContent,'Record status: needs_review');assert.equal($('export').disabled,false);
$('nextPage').click();await settle();assert(calls.some(c=>c.url.includes('page=2')));
const nameInput=$('field-0');nameInput.value='Unsaved edit';nameInput.dispatchEvent(new w.Event('input',{bubbles:true}));confirm=false;
const before=calls.length;$('liveQueue').querySelector('button').click();await settle();assert.equal(calls.length,before);assert.equal(nameInput.value,'Unsaved edit');confirm=true;
$('conferenceUrl').value='https://example.org/conference';$('extractYear').value='2027';$('extractForm').dispatchEvent(new w.Event('submit',{cancelable:true}));await settle();const post=calls.find(c=>c.url==='/api/ai/extract/');assert.equal(post.options.method,'POST');assert.equal(post.options.credentials,'same-origin');assert.equal(post.options.headers['X-CSRFToken'],'csrf-test');assert.equal(JSON.parse(post.options.body).year,2027);
assert.match($('feedback').textContent,/new extraction/);
candidate={...candidate,status:'approved',created:false};$('extractForm').dispatchEvent(new w.Event('submit',{cancelable:true}));await settle();assert.match($('feedback').textContent,/existing candidate reused/);assert.equal($('export').disabled,true);
failDetail=true;$('liveQueue').querySelector('button').click();await settle();assert.match($('feedback').textContent,/Denied/);assert.equal($('title').textContent,fixture.fields.conference_name.value);assert.equal($('connect').disabled,false);
permitted=false;emptyQueue=true;$('connect').click();await settle();assert.equal($('extractLive').disabled,true);assert.match($('liveQueue').textContent,/No pending/);
// Historical examples have no authoritative current wrapper status: inspect only.
for(const name of ['live-computing-frontiers-candidate.json','live-djangocon-candidate.json']){
 const payload=JSON.parse(fs.readFileSync(path.join(root,'examples',name),'utf8'));
 w.CCSEReview.load({id:8,status:'needs_review',payload});assert.equal($('export').disabled,false);assert.notEqual($('title').textContent,'Conference candidate');
}
assert.equal(calls.some(c=>/approve|reject/.test(c.url)),false);
console.log('PASS: session permissions, same-origin fetch, live queue/detail, pagination, real example import, dirty edit guard, CSRF extraction payload, reused approved state, API error recovery; no approval endpoints called.');
