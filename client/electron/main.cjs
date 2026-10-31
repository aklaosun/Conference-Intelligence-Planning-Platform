'use strict';
const {app,BrowserWindow,Menu,ipcMain,shell,dialog}=require('electron');
const {spawn}=require('node:child_process');
const path=require('node:path');
const fs=require('node:fs');
const {pathToFileURL}=require('node:url');
const {serverUrl}=require('./server-url.cjs');
let win,backend,quitting=false,origin='http://127.0.0.1:8010';
const profile=process.env.CCSE_USER_DATA_DIR||path.join(app.getPath('appData'),'CCSE Conference Workspace');
fs.mkdirSync(profile,{recursive:true});app.setPath('userData',profile);
app.commandLine.appendSwitch('force-renderer-accessibility');
const connectPage=path.join(__dirname,'connect.html');
const localPage=pathToFileURL(connectPage).href;
function settingsPath(){return path.join(app.getPath('userData'),'server.json');}
function openExternal(value){try{const u=new URL(value);if(['https:','http:'].includes(u.protocol))shell.openExternal(u.href);}catch{}}
function localSender(event){if(event.sender!==win.webContents||event.senderFrame?.url!==localPage)throw Error('This action is available only in the connection screen.');}
async function connect(value){
  const base=serverUrl(value);
  const response=await fetch(base+'/health/',{signal:AbortSignal.timeout(10000),redirect:'error'});
  if(!response.ok)throw Error('The server is not ready. Check that the backend is running.');
  const health=await response.json();
  if(health.service!=='ccse-conference-platform'||health.status!=='ok')throw Error('This address is not a ready CCSE workspace server.');
  origin=base;
  fs.mkdirSync(app.getPath('userData'),{recursive:true});
  fs.writeFileSync(settingsPath(),JSON.stringify({server:base}),'utf8');
  await win.loadURL(base+'/app/');
  return {ok:true};
}
function showConnection(){win.loadFile(connectPage);}
async function startLocal(){
  const executable=app.isPackaged?path.join(process.resourcesPath,'backend','ccse-backend.exe'):path.join(__dirname,'../..','desktop-backend/dist/ccse-backend/ccse-backend.exe');
  const seed=app.isPackaged?path.join(process.resourcesPath,'demo-catalog.json'):path.join(__dirname,'../..','data/demo-catalog.json');
  const data=path.join(app.getPath('userData'),'data');
  fs.mkdirSync(data,{recursive:true});
  await win.loadFile(path.join(__dirname,'starting.html'));
  const environment={...process.env,CCSE_DESKTOP_DATA_DIR:data,CCSE_DESKTOP_SEED:seed,PYTHONUTF8:'1',PYTHONIOENCODING:'utf-8'};
  delete environment.GEMINI_API_KEY;
  delete environment.DJANGO_SETTINGS_MODULE;
  backend=spawn(executable,[],{env:environment,windowsHide:true,stdio:['ignore','pipe','pipe']});
  const ready=await new Promise((resolve,reject)=>{
    let buffer='';const timer=setTimeout(()=>reject(Error('The local backend took too long to start.')),60000);
    backend.once('error',error=>{clearTimeout(timer);reject(error)});
    backend.once('exit',code=>{clearTimeout(timer);reject(Error('The local backend stopped during startup (code '+code+').'))});
    backend.stdout.on('data',chunk=>{
      buffer+=chunk.toString('utf8');
      let newline;
      while((newline=buffer.indexOf('\n'))>=0){
        const line=buffer.slice(0,newline).trim();buffer=buffer.slice(newline+1);
        if(line.startsWith('CCSE_READY ')){clearTimeout(timer);try{resolve(JSON.parse(line.slice(11)))}catch(error){reject(error)}}
      }
    });
    backend.stderr.on('data',chunk=>fs.appendFileSync(path.join(data,'backend-start.log'),chunk));
  });
  origin=serverUrl('http://127.0.0.1:'+ready.port);
  fs.writeFileSync(path.join(data,'runtime.json'),JSON.stringify({port:ready.port,pid:backend.pid,started_at:new Date().toISOString()}));
  const response=await fetch(origin+'/api/platform/desktop-bootstrap/',{method:'POST',headers:{'X-Desktop-Bootstrap':ready.token},redirect:'error',signal:AbortSignal.timeout(10000)});
  if(!response.ok)throw Error('Unable to open your local demo account.');
  const sessionCookie=response.headers.getSetCookie().find(cookie=>cookie.startsWith('sessionid='));
  if(!sessionCookie)throw Error('The local backend did not create a session.');
  await win.webContents.session.cookies.set({url:origin,name:'sessionid',value:sessionCookie.split(';')[0].slice(10),httpOnly:true,sameSite:'strict'});
  await win.loadURL(origin+'/app/');
}
if(!app.requestSingleInstanceLock())app.quit();
else app.whenReady().then(async()=>{
  try{const stored=JSON.parse(fs.readFileSync(settingsPath(),'utf8'));origin=serverUrl(stored.server);}catch{}
  if(process.env.CCSE_SERVER_URL){try{origin=serverUrl(process.env.CCSE_SERVER_URL);}catch{}}
  win=new BrowserWindow({width:1460,height:980,minWidth:900,minHeight:650,title:'CCSE Conference Workspace',backgroundColor:'#101e2b',icon:path.join(__dirname,'icon.png'),
    webPreferences:{preload:path.join(__dirname,'preload.cjs'),contextIsolation:true,nodeIntegration:false,sandbox:true,webSecurity:true}});
  win.webContents.session.setPermissionRequestHandler((_contents,_permission,callback)=>callback(false));
  win.webContents.setWindowOpenHandler(({url})=>{openExternal(url);return{action:'deny'}});
  win.webContents.on('will-navigate',(event,url)=>{
    if(url===localPage)return;
    try{if(new URL(url).origin===origin)return;}catch{}
    event.preventDefault();openExternal(url);
  });
  ipcMain.handle('workspace:info',event=>{localSender(event);return{server:origin,version:app.getVersion()}});
  ipcMain.handle('workspace:connect',async(event,value)=>{
    localSender(event);
    try{return await connect(value);}catch(error){return{ok:false,error:error.message||'Unable to connect.'}}
  });
  Menu.setApplicationMenu(Menu.buildFromTemplate([
    {label:'Workspace',submenu:[{label:'Open local data folder',click:()=>shell.openPath(path.join(app.getPath('userData'),'data'))},{label:'Connect to a shared server…',click:showConnection},{type:'separator'},{role:'quit'}]},
    {role:'editMenu'},{role:'viewMenu'},
    {label:'Help',submenu:[{label:'About CCSE Workspace',click:()=>dialog.showMessageBox(win,{type:'info',title:'CCSE Conference Workspace',message:'CCSE Conference Workspace '+app.getVersion(),detail:'Personal local demo with real spreadsheet data. Each computer has an independent database. API keys stay in your private local backend configuration and are never included in installers.'})}]}
  ]));
  if(process.env.CCSE_SERVER_URL){try{await connect(origin);return;}catch{}}
  if(app.isPackaged||process.env.CCSE_LOCAL_DEMO==='1'){
    try{await startLocal();return;}catch(error){if(backend){backend.kill();backend=null}await dialog.showMessageBox(win,{type:'error',title:'Local demo could not start',message:error.message,detail:'Check data/backend-start.log in your local application data folder. Your saved database has not been reset.'});}
  }
  showConnection();
});
app.on('second-instance',()=>{if(win){if(win.isMinimized())win.restore();win.focus()}});
app.on('before-quit',()=>{quitting=true;if(backend){backend.kill();backend=null}});
app.on('window-all-closed',()=>{if(process.platform!=='darwin')app.quit()});
