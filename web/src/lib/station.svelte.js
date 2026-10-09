import { api } from './api.js';
import { parseTechniques } from './parse.js';

export const TOP_K = 10;

class Station {
  data = $state(null);
  error = $state(null);
  mode = $state('observe');
  arrived = $state(false);

  selected = $state([]);
  noise = $state([]);
  rejected = $state([]);
  result = $state(null);
  previousRanks = $state({});
  busy = $state(false);

  dossierId = $state(null);
  dossier = $state(null);
  dossierError = $state(null);
  comparison = $state(null);
  blind = $state(null);
  hover = $state(null);
  constellationFocus = $state(null);
  matrixOpen = $state(false);
  toast = $state(null);
  trust = $state(null);
  cameraRequest = $state(0);

  techniques = $derived(new Map((this.data?.techniques ?? []).map((t) => [t.id, t])));
  actors = $derived(new Map((this.data?.actors ?? []).map((a) => [a.id, a])));
  constellations = $derived(new Map((this.data?.constellations ?? []).map((c) => [c.id, c])));
  vocabulary = $derived(new Set(this.techniques.keys()));
  query = $derived([...this.selected, ...this.noise]);
  candidateIds = $derived(new Set((this.result?.candidates ?? []).map((c) => c.id)));

  async load() {
    try {
      this.data = await api.station();
    } catch (error) {
      this.error = error.message;
    }
  }

  add(ids) {
    const fresh = ids.filter((id) => this.vocabulary.has(id) && !this.selected.includes(id));
    if (fresh.length) {
      this.selected = [...this.selected, ...fresh];
      this.noise = this.noise.filter((id) => !fresh.includes(id));
    }
    return fresh.length;
  }

  addText(text) {
    const { known, unknown } = parseTechniques(text, this.vocabulary);
    const added = this.add(known);
    if (unknown.length) {
      this.rejected = [...new Set([...this.rejected, ...unknown])].slice(-12);
    }
    return { added, unknown };
  }

  remove(id) {
    this.selected = this.selected.filter((t) => t !== id);
    this.noise = this.noise.filter((t) => t !== id);
  }

  toggle(id) {
    if (this.selected.includes(id) || this.noise.includes(id)) this.remove(id);
    else this.add([id]);
  }

  clear() {
    this.selected = [];
    this.noise = [];
    this.rejected = [];
    this.blind = null;
    this.result = null;
    this.previousRanks = {};
  }

  async injectNoise(ratio = 0.3) {
    if (!this.selected.length) return;
    const { noise } = await api.noise(this.selected, ratio);
    this.noise = [...new Set([...this.noise, ...noise])].filter((id) => !this.selected.includes(id));
  }

  async startBlind(noiseRatio = 0) {
    const blind = await api.blind(0.4, noiseRatio);
    this.clear();
    this.mode = 'observe';
    this.closeDossier();
    this.blind = { answer: blind.answer, revealed: false, noisy: noiseRatio > 0 };
    this.selected = blind.techniques;
    this.noise = blind.noise;
  }

  revealBlind() {
    if (this.blind) this.blind = { ...this.blind, revealed: true };
  }

  setResult(result) {
    const ranks = {};
    for (const c of this.result?.candidates ?? []) ranks[c.id] = c.rank;
    this.previousRanks = ranks;
    this.result = result;
  }

  async openDossier(id) {
    if (!id) return;
    this.dossierId = id;
    this.dossierError = null;
    if (this.dossier?.id !== id) this.dossier = null;
    try {
      const dossier = await api.actor(id);
      if (this.dossierId === id) this.dossier = dossier;
    } catch (error) {
      if (this.dossierId === id) this.dossierError = error.message;
    }
  }

  closeDossier() {
    this.dossierId = null;
    this.dossier = null;
    this.dossierError = null;
  }

  async openComparison(a, b) {
    this.comparison = { a, b, data: null };
    try {
      const data = await api.compare(a, b);
      if (this.comparison?.a === a && this.comparison?.b === b) this.comparison = { a, b, data };
    } catch (error) {
      this.notify(error.message);
      this.comparison = null;
    }
  }

  async loadTrust() {
    if (this.trust) return;
    try {
      this.trust = await api.trust();
    } catch (error) {
      this.trust = { available: false, error: error.message };
    }
  }

  recenter() {
    this.cameraRequest += 1;
  }

  notify(message) {
    const stamp = Date.now();
    this.toast = { message, stamp };
    setTimeout(() => {
      if (this.toast?.stamp === stamp) this.toast = null;
    }, 2600);
  }
}

export const station = new Station();
