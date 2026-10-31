'use strict';
function serverUrl(value){
  if(typeof value!=='string'||value.length>2048)throw Error('Enter a valid server address.');
  let url;try{url=new URL(value.trim());}catch{throw Error('Use a full server URL, such as https://your-server.example.');}
  if(url.username||url.password||url.search||url.hash||!['http:','https:'].includes(url.protocol))throw Error('Use a server URL without credentials, queries, or fragments.');
  const local=['localhost','127.0.0.1','[::1]'].includes(url.hostname);
  if(url.protocol!=='https:'&&!local)throw Error('Shared servers require HTTPS. HTTP is allowed only for a local demo.');
  if(url.pathname!=='/'&&url.pathname!=='')throw Error('Enter the server origin without an application path.');
  return url.origin;
}
module.exports={serverUrl};
