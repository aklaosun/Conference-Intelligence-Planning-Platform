import {defineConfig} from 'vite';
import react from '@vitejs/plugin-react';
import {resolve} from 'node:path';
export default defineConfig({plugins:[react()],base:'/static/workspace/',build:{
  outDir:resolve(import.meta.dirname,'../ccse-conference-platform/conferences/static/workspace'),
  emptyOutDir:true,manifest:true,rollupOptions:{input:resolve(import.meta.dirname,'src/main.tsx')}
}});
