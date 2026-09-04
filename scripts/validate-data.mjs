import { readFile } from 'node:fs/promises';

const [cities, cityData, reviewData] = await Promise.all([
  readJson('data/cities.json'),
  readJson('data/city_data.json'),
  readJson('data/city_data_review.json'),
]);

const errors = [];
const warnings = new Map();
const cityIds = new Set();

for (const city of cities) {
  if (!city.id || !city.name || !city.yomi || !city.pref) {
    errors.push(`自治体一覧に必須項目がありません: ${JSON.stringify(city)}`);
  }
  if (cityIds.has(city.id)) errors.push(`自治体IDが重複しています: ${city.id}`);
  cityIds.add(city.id);
}

validateRecords(cityData, '本データ');
validateRecords(reviewData, 'レビュー用データ', { allowIncomplete: true });

const reviewIds = new Set(Object.keys(reviewData));
const overlap = Object.keys(cityData).filter(id => reviewIds.has(id));
const highVsLowConflicts = overlap.filter(
  id => cityData[id].confidence === 'high' && reviewData[id].confidence === 'low',
);
const highVsUnclassifiedReviews = overlap.filter(
  id => cityData[id].confidence === 'high' && !reviewData[id].confidence,
);
const otherOverlaps = overlap.filter(
  id => !highVsLowConflicts.includes(id) && !highVsUnclassifiedReviews.includes(id),
);
if (highVsLowConflicts.length) {
  warn('本データの high とレビュー用データの low が競合', highVsLowConflicts);
}
if (highVsUnclassifiedReviews.length) {
  warn('本データの high と信頼度未設定のレビュー用データが重複', highVsUnclassifiedReviews);
}
if (otherOverlaps.length) warn('本データとレビュー用データが重複', otherOverlaps);

if (errors.length) {
  console.error(`データ検証に失敗しました（${errors.length}件）`);
  errors.forEach(error => console.error(`- ${error}`));
  process.exitCode = 1;
} else {
  console.log(`データ構造: OK（自治体 ${cities.length}件、本データ ${Object.keys(cityData).length}件、レビュー ${Object.keys(reviewData).length}件）`);
}

if (warnings.size) {
  console.warn(`要確認: ${warnings.size}種類`);
  for (const [label, ids] of warnings) {
    const sample = ids.slice(0, 3).join(', ');
    console.warn(`- ${label}: ${ids.length}件${sample ? `（例: ${sample}）` : ''}`);
  }
}

async function readJson(path) {
  return JSON.parse(await readFile(path, 'utf8'));
}

function validateRecords(records, label, { allowIncomplete = false } = {}) {
  for (const [id, record] of Object.entries(records)) {
    if (!cityIds.has(id)) errors.push(`${label}に自治体一覧にないIDがあります: ${id}`);
    if (record?.hasData !== true) reportIncomplete(`${label}: hasData が true ではありません`, id);
    if (typeof record?.office !== 'string' || !record.office.trim()) reportIncomplete(`${label}: 窓口情報がありません`, id);
    if (!record?.links || typeof record.links !== 'object') {
      reportIncomplete(`${label}: links がありません`, id);
      continue;
    }
    for (const [kind, url] of Object.entries(record.links)) {
      if (url != null && (typeof url !== 'string' || !isHttpUrl(url))) {
        errors.push(`${label}/${id}: ${kind} のURLが不正です`);
      }
    }
    if (!record.links.out || !record.links.in) warn(`${label}: 転出・転入のどちらかの公式URLが未収録`, [id]);
    if (record.confidence && !['high', 'low'].includes(record.confidence)) {
      errors.push(`${label}/${id}: confidence の値が不正です`);
    }
    if (!record.confidence) warn(`${label}: confidence が未設定`, [id]);
  }

  function reportIncomplete(message, id) {
    if (allowIncomplete) warn(message, [id]);
    else errors.push(`${label}/${id}: ${message.replace(`${label}: `, '')}`);
  }
}

function warn(label, ids) {
  const existing = warnings.get(label) ?? [];
  warnings.set(label, existing.concat(ids));
}

function isHttpUrl(value) {
  try {
    const url = new URL(value);
    return url.protocol === 'https:' || url.protocol === 'http:';
  } catch {
    return false;
  }
}
