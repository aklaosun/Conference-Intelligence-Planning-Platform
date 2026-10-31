'use strict';
const input=document.getElementById('server'),status=document.getElementById('status'),button=document.getElementById('connect');
window.ccseConnection.info().then(info=>{input.value=info.server}).catch(()=>{status.textContent='Unable to read the server setting.'});
document.getElementById('connect-form').addEventListener('submit',async event=>{
  event.preventDefault();button.disabled=true;status.textContent='Checking your workspace server…';
  try{const result=await window.ccseConnection.connect(input.value);if(!result.ok)status.textContent=result.error;}
  catch{status.textContent='Unable to connect. Check the server address and your connection.'}
  finally{button.disabled=false}
});
