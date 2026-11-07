export const themes = [
  {id:'ksu',name:'Kennesaw gold & black',description:'KSU gold, a black sidebar, and warm white surfaces.',swatches:['#000000','#ffc629','#faf9f5'],bg:'#faf9f5',text:'#242320',muted:'#64615a',accent:'#805500',fill:'#ffc629',onFill:'#161616'},
  {id:'light',name:'Light',description:'Bright surfaces with a calm teal accent.',swatches:['#ffffff','#087f78','#eaf1f5'],bg:'#f3f6f8',text:'#243445',muted:'#586b7b',accent:'#08756e',fill:'#08756e',onFill:'#ffffff'},
  {id:'dark',name:'Dark',description:'Charcoal panels and soft mint highlights.',swatches:['#191c20','#78d8bf','#30343b'],bg:'#141619',text:'#eef0f3',muted:'#a8b1bc',accent:'#78d8bf',fill:'#78d8bf',onFill:'#10241e'},
  {id:'midnight',name:'Midnight',description:'Deep navy surfaces with a cool blue accent.',swatches:['#080e1b','#94b9ff','#14223c'],bg:'#080e1b',text:'#e7edf9',muted:'#9eacc6',accent:'#94b9ff',fill:'#94b9ff',onFill:'#0b1930'},
] as const;
export type ThemeId=typeof themes[number]['id'];
export const normalizeTheme=(value:unknown):ThemeId=>themes.some(t=>t.id===value)?value as ThemeId:'ksu';
export function savedTheme():ThemeId{try{return normalizeTheme(localStorage.getItem('ccse.theme'))}catch{return 'ksu'}}
export function applyTheme(value:ThemeId){
  const theme=themes.find(t=>t.id===value)!;
  const root=document.documentElement;
  root.dataset.theme=value;
  for(const[key,v]of Object.entries({'--bg':theme.bg,'--text':theme.text,'--muted':theme.muted,'--accent':theme.accent,'--accent-fill':theme.fill,'--on-accent':theme.onFill}))root.style.setProperty(key,v);
  try{localStorage.setItem('ccse.theme',value)}catch{}
  document.querySelector('meta[name="theme-color"]')?.setAttribute('content',theme.swatches[0]);
}
