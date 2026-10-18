// Independently implemented from observed LinkedIn response envelopes.
export function mediaReferences(root) {
  const results = [], seen = new Set();
  function add(kind, url, evidence) {
    if (typeof url !== 'string' || !/^https?:\/\//i.test(url)) return;
    const key = kind + url;
    if (!seen.has(key)) { seen.add(key); results.push({kind, url, evidence}); }
  }
  function walk(value, path = '', depth = 0) {
    if (!value || typeof value !== 'object' || depth > 30) return;
    if (typeof value.rootUrl === 'string' && Array.isArray(value.artifacts)) {
      for (const a of value.artifacts) if (a.fileIdentifyingUrlPathSegment)
        add('image', value.rootUrl + a.fileIdentifyingUrlPathSegment, path + '.artifacts');
    }
    for (const [key, child] of Object.entries(value)) {
      const at = path + '.' + key;
      if (typeof child === 'string') {
        if (/transcript|caption/i.test(key)) add('caption', child, at);
        else if (/playableUrl|streamingUrl|contentUrl|downloadUrl|manifestUrl/i.test(key))
          add(/video|stream|playable|manifest/i.test(at) ? 'video' : 'asset', child, at);
        else if (/imageUrl|thumbnailUrl/i.test(key)) add('image', child, at);
      } else walk(child, at, depth + 1);
    }
  }
  walk(root);
  return results;
}
export function parseSavedPage(json, page = 0) {
  const cluster = json?.data?.data?.searchDashClustersByAll;
  if (!Array.isArray(cluster?.elements)) throw Error('LinkedIn response changed: ordered result list missing. Refusing to guess order.');
  const byUrn = new Map((json.included || []).map(e => [e.entityUrn, e]));
  const items = [];
  for (const group of cluster.elements) for (const row of group.items || []) {
    const ref = row.item?.['*entityResult'];
    if (!ref) continue;
    const e = byUrn.get(ref);
    if (!e) throw Error('Ordered post reference could not be resolved. Capture stopped to preserve ordering.');
    const embedded = e.entityEmbeddedObject || {};
    const media = mediaReferences(embedded);
    items.push({id:e.trackingUrn || ref, provider:'linkedin', sourceUrl:e.navigationUrl || '',
      sourcePage:page, author:{name:e.title?.text || '', bio:e.primarySubtitle?.text || ''},
      text:e.summary?.text || '', textCompleteness:'saved-list text; full post not verified',
      savedAt:null, publishedAt:null,
      attachmentPreview:{title:embedded.title?.text || null, subtitle:embedded.primarySubtitle?.text || null,
        playablePreview:embedded.showPlayButton === true, media},
      extraction:{binaryMediaDownloaded:false, transcript:null, ocr:null,
        limitations:['Saved-list images can be link previews. A play button does not prove video content was extracted.']}});
  }
  return {items, cursor:cluster.metadata?.paginationToken || null};
}
export async function collectSaved({limit, fetchPage, onProgress = () => {}, signal}) {
  if (!Number.isSafeInteger(limit) || limit < 1) throw Error('Choose a positive whole number.');
  const items = [], seen = new Set(); let cursor = null, page = 0, reason = 'requested_limit';
  while (items.length < limit) {
    signal?.throwIfAborted();
    const parsed = parseSavedPage(await fetchPage(page, cursor), page);
    if (!parsed.items.length) {reason = 'end_of_results'; break;}
    let added = 0;
    for (const item of parsed.items) {
      if (seen.has(item.id)) continue;
      seen.add(item.id); added++;
      items.push({...item, savedListPosition:items.length + 1});
      if (items.length === limit) break;
    }
    onProgress(items.slice());
    if (!added) {reason = 'repeated_page'; break;}
    cursor = parsed.cursor || cursor; page++;
  }
  return {items, stopReason:reason};
}
