import fs from "fs";
import path from "path";

/* =========================
   Dataset load
   ========================= */
let PREPPED = null;

export function loadDatasetOnce() {
  if (PREPPED) return PREPPED;
  const p = path.join(process.cwd(), "data", "prepped.json");
  if (!fs.existsSync(p)) throw new Error(`Dataset not found at ${p}`);
  const raw = JSON.parse(fs.readFileSync(p, "utf8"));
  PREPPED = raw;
  console.log(`Loaded ${PREPPED.length} tracks`);
  return PREPPED;
}

/* =========================
   Math helpers
   ========================= */
function zscoreVec(v) {
  const n = v.length || 1;
  let m = 0;
  for (const x of v) m += x;
  m /= n;
  let s2 = 0;
  for (const x of v) {
    const d = x - m;
    s2 += d * d;
  }
  const sd = Math.sqrt(s2 / n) || 1;
  return v.map(x => (x - m) / sd);
}

function cosineSim(a, b) {
  if (!a || !b || a.length !== b.length) return 0;
  let dot = 0, na = 0, nb = 0;
  for (let i = 0; i < a.length; i++) {
    const ai = a[i], bi = b[i];
    dot += ai * bi;
    na += ai * ai;
    nb += bi * bi;
  }
  if (!na || !nb) return 0;
  return dot / (Math.sqrt(na) * Math.sqrt(nb));
}

/* =========================
   Feature construction
   ========================= */
function buildVec(t) {
  const tempoNorm = Math.min(Math.max((t.tempo || 0) / 240, 0), 1);
  const loudNorm = Math.min(Math.max(((t.loudness || 0) + 60) / 60, 0), 1);
  return [
    t.danceability || 0,
    t.energy || 0,
    t.valence || 0,
    t.acousticness || 0,
    t.instrumentalness || 0,
    t.liveness || 0,
    t.speechiness || 0,
    tempoNorm,
    loudNorm,
    t.mode || 0,
  ];
}

function genreOverlap(seedGenres = [], candidateGenres = []) {
  const A = new Set(seedGenres.map(s => s.toLowerCase()));
  const B = new Set(candidateGenres.map(s => s.toLowerCase()));
  if (!A.size || !B.size) return 0;
  
  let inter = 0;
  for (const x of A) if (B.has(x)) inter++;
  
  const uni = A.size + B.size - inter;
  return inter / uni; // Jaccard similarity
}

function eraDistance(seedYear, candidateYear) {
  if (!seedYear || !candidateYear) return 0;
  if (seedYear < 1900 || candidateYear < 1900) return 0;
  return Math.abs(seedYear - candidateYear);
}

function popDistance(seedPop, candidatePop) {
  const s = seedPop || 0;
  const c = candidatePop || 0;
  return Math.abs(s - c);
}

/* =========================
   Core similarity computation
   ========================= */
   function computeAllScores(seed, candidate, params) {
  try {
    // Audio similarity (cosine of z-scored feature vectors)
    const va = zscoreVec(buildVec(seed));
    const vb = zscoreVec(buildVec(candidate));
    const audio_sim = cosineSim(va, vb) || 0;
    
    // Genre similarity (Jaccard index)
    const genre_sim = genreOverlap(seed.genres || [], candidate.genres || []);
    
    // Era distance
    const era_dist = eraDistance(seed.year, candidate.year);
    
    // Popularity distance
    const pop_dist = popDistance(seed.popularity, candidate.popularity);
    
    // Weighted composite score
    const {
      audio_weight = 0.70,
      genre_weight = 0.15,
      era_weight = 0.10,
      pop_weight = 0.05,
      era_decay = 10,
      pop_decay = 30,
      genre_boost = 0.10,
      genre_penalty = -0.10,
    } = params;
    
    // Convert distances to similarities (exponential decay)
    const era_sim = Math.exp(-era_dist / Math.max(1, era_decay));
    const pop_sim = Math.exp(-pop_dist / Math.max(1, pop_decay));
    
    // Apply genre boost/penalty
    let genre_factor = 1.0;
    if (genre_sim > 0) {
      genre_factor = 1.0 + (genre_boost * genre_sim);
    } else if ((seed.genres?.length || 0) > 0 && (candidate.genres?.length || 0) > 0) {
      genre_factor = 1.0 + genre_penalty;
    }
    
    // Weighted sum
    const composite_raw = 
      (audio_weight * audio_sim) +
      (genre_weight * genre_sim) +
      (era_weight * era_sim) +
      (pop_weight * pop_sim);
    
    // Apply genre factor
    const radio_fit = Math.max(0, Math.min(1, composite_raw * genre_factor));
    
    // Validate all outputs are numbers
    const result = {
      audio_sim: Number.isFinite(audio_sim) ? audio_sim : 0,
      genre_sim: Number.isFinite(genre_sim) ? genre_sim : 0,
      era_dist: Number.isFinite(era_dist) ? era_dist : 0,
      era_sim: Number.isFinite(era_sim) ? era_sim : 0,
      pop_dist: Number.isFinite(pop_dist) ? pop_dist : 0,
      pop_sim: Number.isFinite(pop_sim) ? pop_sim : 0,
      genre_factor: Number.isFinite(genre_factor) ? genre_factor : 1,
      composite_raw: Number.isFinite(composite_raw) ? composite_raw : 0,
      radio_fit: Number.isFinite(radio_fit) ? radio_fit : 0,
    };
    
    return result;
  } catch (e) {
    console.error(`Error in computeAllScores for ${candidate.name}:`, e);
    // Return zero scores on any error
    return {
      audio_sim: 0,
      genre_sim: 0,
      era_dist: 0,
      era_sim: 0,
      pop_dist: 0,
      pop_sim: 0,
      genre_factor: 1,
      composite_raw: 0,
      radio_fit: 0,
    };
  }
}
// function computeAllScores(seed, candidate, params) {
//   // Audio similarity (cosine of z-scored feature vectors)
//   const va = zscoreVec(buildVec(seed));
//   const vb = zscoreVec(buildVec(candidate));
//   const audio_sim = cosineSim(va, vb);
  
//   // Genre similarity (Jaccard index)
//   const genre_sim = genreOverlap(seed.genres || [], candidate.genres || []);
  
//   // Era distance
//   const era_dist = eraDistance(seed.year, candidate.year);
  
//   // Popularity distance
//   const pop_dist = popDistance(seed.popularity, candidate.popularity);
  
//   // Weighted composite score (this is what we tune)
//   const {
//     audio_weight = 0.70,
//     genre_weight = 0.15,
//     era_weight = 0.10,
//     pop_weight = 0.05,
    
//     era_decay = 10,        // how many years before similarity drops off
//     pop_decay = 30,        // how many points before similarity drops off
    
//     genre_boost = 0.10,    // bonus for genre overlap
//     genre_penalty = -0.10, // penalty for no genre overlap
//   } = params;
  
//   // Convert distances to similarities (exponential decay)
//   const era_sim = Math.exp(-era_dist / Math.max(1, era_decay));
//   const pop_sim = Math.exp(-pop_dist / Math.max(1, pop_decay));
  
//   // Apply genre boost/penalty
//   let genre_factor = 1.0;
//   if (genre_sim > 0) {
//     genre_factor = 1.0 + (genre_boost * genre_sim);
//   } else if ((seed.genres?.length || 0) > 0 && (candidate.genres?.length || 0) > 0) {
//     // Both have genres but no overlap
//     genre_factor = 1.0 + genre_penalty;
//   }
  
//   // Weighted sum
//   const composite_raw = 
//     (audio_weight * audio_sim) +
//     (genre_weight * genre_sim) +
//     (era_weight * era_sim) +
//     (pop_weight * pop_sim);
  
//   // Apply genre factor
//   const radio_fit = Math.max(0, Math.min(1, composite_raw * genre_factor));
  
//   return {
//     audio_sim,
//     genre_sim,
//     era_dist,
//     era_sim,
//     pop_dist,
//     pop_sim,
//     genre_factor,
//     composite_raw,
//     radio_fit,
//   };
// }

/* =========================
   Main analyzer - returns FLAT LIST
   ========================= */
export async function analyzeTrack(seedInput, params = {}) {
  const data = loadDatasetOnce();
  
  // Find seed
  const seed = data.find(r => 
    String(r.id) === String(seedInput) || 
    String(r.uri) === String(seedInput)
  );
  if (!seed) throw new Error(`Seed not found: ${seedInput}`);
  
  // Parse params with defaults
  const limit = Math.max(0, parseInt(params.limit ?? 2000, 10));
  const include_remasters = String(params.include_remasters ?? "0") === "1";
  const pop_floor = parseInt(params.pop_floor ?? 0, 10);
  
  // Filter candidates
  let candidates = include_remasters 
    ? data 
    : data.filter(r => !(r.is_remaster || r.is_alt));
  
  if (pop_floor > 0) {
    candidates = candidates.filter(r => (r.popularity || 0) >= pop_floor);
  }

  //Filter out audiobooks/spoken word
// candidates = candidates.filter(r => {
const max_speechiness = parseFloat(params.max_speechiness ?? 0.66);
candidates = candidates.filter(r => (r.speechiness || 0) < max_speechiness);
  
// Compute scores for all candidates
const scored = candidates.map(candidate => {
  try {
    const scores = computeAllScores(seed, candidate, params);
    return {
      id: candidate.id,
      uri: candidate.uri,
      name: candidate.name,
      artists: candidate.artists,
      year: candidate.year,
      popularity: candidate.popularity,
      genres: candidate.genres,
      // Audio features
      danceability: candidate.danceability,
      energy: candidate.energy,
      valence: candidate.valence,
      acousticness: candidate.acousticness,
      instrumentalness: candidate.instrumentalness,
      liveness: candidate.liveness,
      speechiness: candidate.speechiness,
      tempo: candidate.tempo,
      loudness: candidate.loudness,
      mode: candidate.mode,
      key: candidate.key,
      time_signature: candidate.time_signature,
      ...scores,
    };
  } catch (e) {
    console.error(`Error scoring track ${candidate.name}:`, e);
    return null;
  }
}).filter(Boolean);  // Remove nulls
  
// Sort by radio_fit descending
scored.sort((a, b) => b.radio_fit - a.radio_fit);

// Filter out tracks with zero or invalid radio_fit
//removed this because it was too aggressive, but it did kinda magic to the right answer
// const validScored = scored.filter(t => {
//   if (!Number.isFinite(t.radio_fit) || t.radio_fit <= 0) {
//     return false;
//   }
//   return true;
// });

const validScored = scored;

console.log(`Filtered: ${scored.length} → ${validScored.length} valid tracks`);

// Apply radio_fit floor if specified
const radio_fit_floor = parseFloat(params.radio_fit_floor ?? 0);
const filtered = radio_fit_floor > 0 
  ? validScored.filter(t => t.radio_fit >= radio_fit_floor)
  : validScored;

// Limit
const ranked = limit > 0 ? filtered.slice(0, limit) : filtered;
  
  // Return everything
  return {
    seed: {
      id: seed.id,
      uri: seed.uri,
      name: seed.name,
      artists: seed.artists,
      year: seed.year,
      popularity: seed.popularity,
      genres: seed.genres || [],
    },
    params: {
      audio_weight: parseFloat(params.audio_weight ?? 0.70),
      genre_weight: parseFloat(params.genre_weight ?? 0.15),
      era_weight: parseFloat(params.era_weight ?? 0.10),
      pop_weight: parseFloat(params.pop_weight ?? 0.05),
      era_decay: parseFloat(params.era_decay ?? 10),
      pop_decay: parseFloat(params.pop_decay ?? 30),
      genre_boost: parseFloat(params.genre_boost ?? 0.10),
      genre_penalty: parseFloat(params.genre_penalty ?? -0.10),
      limit,
      include_remasters,
      pop_floor,
    },
    tracks: ranked,
  };
}
