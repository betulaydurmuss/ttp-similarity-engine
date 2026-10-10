async function request(path, { method = 'GET', body, signal } = {}) {
  const response = await fetch(path, {
    method,
    signal,
    headers: body ? { 'Content-Type': 'application/json' } : undefined,
    body: body ? JSON.stringify(body) : undefined
  });
  if (!response.ok) {
    const payload = await response.json().catch(() => ({}));
    const detail = typeof payload.detail === 'string' ? payload.detail : response.statusText;
    throw new Error(detail || `İstek başarısız (${response.status})`);
  }
  return response.json();
}

export const api = {
  station: () => request('/api/station'),
  query: (techniques, topK, signal) =>
    request('/api/query', { method: 'POST', body: { techniques, top_k: topK }, signal }),
  actor: (id) => request(`/api/actors/${encodeURIComponent(id)}`),
  compare: (a, b) => request(`/api/compare?a=${encodeURIComponent(a)}&b=${encodeURIComponent(b)}`),
  noise: (techniques, ratio) => request('/api/noise', { method: 'POST', body: { techniques, ratio } }),
  blind: (fraction, noiseRatio) =>
    request('/api/blind', { method: 'POST', body: { fraction, noise_ratio: noiseRatio } }),
  trust: () => request('/api/trust')
};
