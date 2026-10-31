'use strict';
const {contextBridge,ipcRenderer}=require('electron');
contextBridge.exposeInMainWorld('ccseConnection',Object.freeze({
  info:()=>ipcRenderer.invoke('workspace:info'),
  connect:value=>ipcRenderer.invoke('workspace:connect',value),
}));
