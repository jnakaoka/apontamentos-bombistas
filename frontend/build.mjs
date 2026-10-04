import {build} from 'esbuild';
import {mkdir,writeFile} from 'node:fs/promises';
await mkdir('dist',{recursive:true});
await build({entryPoints:['src/main.jsx'],bundle:true,outfile:'dist/assets/app.js',minify:true,define:{'process.env.NODE_ENV':'"production"'},loader:{'.css':'css'},logLevel:'info'});
await writeFile('dist/index.html','<!doctype html><html lang="pt"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta name="theme-color" content="#123833"><title>Apontamentos · Bombistas</title><link rel="stylesheet" href="/assets/app.css"></head><body><div id="root"></div><script src="/assets/app.js"></script></body></html>');
