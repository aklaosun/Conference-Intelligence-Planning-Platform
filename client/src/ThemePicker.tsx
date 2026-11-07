import React from 'react';
import {themes,type ThemeId} from './themes';

export function ThemePicker({value,onChange,compact=false,disabled=false}:{value:ThemeId,onChange:(v:ThemeId)=>void,compact?:boolean,disabled?:boolean}){
  if(compact)return <label className="theme-select"><span>Theme</span><select disabled={disabled} aria-label="Color theme" value={value} onChange={e=>onChange(e.target.value as ThemeId)}>{themes.map(t=><option key={t.id} value={t.id}>{t.id==='ksu'?'KSU gold & black':t.name}</option>)}</select></label>;
  return <div className="theme-grid" role="group" aria-label="Choose a color theme">{themes.map(t=><button type="button" disabled={disabled} key={t.id} className={'theme-card '+(value===t.id?'chosen':'')} aria-pressed={value===t.id} onClick={()=>onChange(t.id)}><span className="theme-swatches" aria-hidden="true">{t.swatches.map(c=><i key={c} style={{background:c}}/>)}</span><strong>{t.name}</strong><span>{t.description}</span><small>{value===t.id?'Selected':'Choose theme'}</small></button>)}</div>;
}
