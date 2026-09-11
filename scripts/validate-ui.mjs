import { readFile } from 'node:fs/promises';

const html = await readFile('index.html', 'utf8');
const errors = [];

const scriptMatches = [...html.matchAll(/<script>([\s\S]*?)<\/script>/g)];
if (scriptMatches.length !== 1) {
  errors.push(`インラインスクリプトは1つである必要があります（現在: ${scriptMatches.length}）`);
} else {
  try {
    new Function(scriptMatches[0][1]);
  } catch (error) {
    errors.push(`画面スクリプトの構文エラー: ${error.message}`);
  }
}

const requiredIds = [
  'inputOut',
  'inputIn',
  'moveDate',
  'suggOut',
  'suggIn',
  'generateBtn',
  'shareChecklist',
  'copyChecklist',
  'printChecklist',
  'moreAttrsToggle',
  'resetProgress',
  'resultsWrap',
  'outBlock',
  'inBlock',
  'legal',
];

for (const id of requiredIds) {
  if (!html.includes(`id="${id}"`)) errors.push(`必要な画面要素がありません: #${id}`);
}

const requiredBehaviors = [
  'commitTypedCity',
  "inputEl.addEventListener('input'",
  "inputEl.addEventListener('keydown'",
  "inputEl.addEventListener('blur'",
  "document.getElementById('generateBtn').addEventListener('click', generate)",
  "document.getElementById('shareChecklist').addEventListener('click', shareChecklist)",
  "document.getElementById('copyChecklist').addEventListener('click', copyChecklist)",
  "box.onclick = () =>",
  'let cityDataReady = false;',
  "fetchJson('./data/cities.json')",
  "fetchJson('./data/city_data.json')",
  'function movePlanAlerts(start, end)',
  '年末年始の注意',
  '年度末・年度初めの注意',
  '転入届と同じ施設でできること',
  "direction === 'out' ? '転出届' : '転入届'",
  'https://note.com/meyonze',
  'https://x.com/meyonze34',
  'https://static.cloudflareinsights.com/beacon.min.js',
  'data-cf-beacon=',
];

for (const behavior of requiredBehaviors) {
  if (!html.includes(behavior)) errors.push(`必要な画面操作が見つかりません: ${behavior}`);
}

if (errors.length) {
  console.error(`画面検証に失敗しました（${errors.length}件）`);
  errors.forEach(error => console.error(`- ${error}`));
  process.exitCode = 1;
} else {
  console.log('画面検証: OK（構文・主要操作・必須要素）');
}
