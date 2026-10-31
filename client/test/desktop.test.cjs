const {test}=require('node:test');
const assert=require('node:assert/strict');
const {serverUrl}=require('../electron/server-url.cjs');
test('local demo uses loopback HTTP',()=>assert.equal(serverUrl('http://127.0.0.1:8010/'),'http://127.0.0.1:8010'));
test('shared backend requires HTTPS',()=>{assert.equal(serverUrl('https://ccse.example.org/'),'https://ccse.example.org');assert.throws(()=>serverUrl('http://ccse.example.org'))});
test('credentials and executable URLs are rejected',()=>{for(const url of ['file:///C:/test','javascript:alert(1)','https://user:password@example.org','https://example.org/path','https://example.org/?token=secret'])assert.throws(()=>serverUrl(url))});
