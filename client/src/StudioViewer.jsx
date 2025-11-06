import React, { useState, useEffect } from 'react';
import './StudioViewer.css';

// Preset configurations
const PRESETS = {
  default: {
    name: "Default Balanced",
    description: "70% audio, 15% genre, 10% era, 5% pop",
    audio_weight: 0.70,
    genre_weight: 0.15,
    era_weight: 0.10,
    pop_weight: 0.05,
    era_decay: 10,
    pop_decay: 30,
    genre_boost: 0.10,
    genre_penalty: -0.10,
    tier_1_pct: 20,
    tier_2_pct: 40,
    tier_3_pct: 60,
    tier_4_pct: 80,
    easy_tiers: '1,4,5',
    medium_tiers: '1,2,3',
    hard_tiers: '1,2',
  },
  audio_heavy: {
    name: "Audio Obsessed",
    description: "90% audio - ignore genre/era, pure sonic similarity",
    audio_weight: 0.90,
    genre_weight: 0.05,
    era_weight: 0.03,
    pop_weight: 0.02,
    era_decay: 20,
    pop_decay: 50,
    genre_boost: 0.05,
    genre_penalty: -0.05,
    tier_1_pct: 20,
    tier_2_pct: 40,
    tier_3_pct: 60,
    tier_4_pct: 80,
    easy_tiers: '1,4,5',
    medium_tiers: '1,2,3',
    hard_tiers: '1,2',
  },
  genre_police: {
    name: "Genre Police",
    description: "35% genre - strict boundaries, big penalty for mismatch",
    audio_weight: 0.50,
    genre_weight: 0.35,
    era_weight: 0.10,
    pop_weight: 0.05,
    era_decay: 10,
    pop_decay: 30,
    genre_boost: 0.25,
    genre_penalty: -0.30,
    tier_1_pct: 20,
    tier_2_pct: 40,
    tier_3_pct: 60,
    tier_4_pct: 80,
    easy_tiers: '1,4,5',
    medium_tiers: '1,2,3',
    hard_tiers: '1,2',
  },
  time_traveler: {
    name: "Time Traveler",
    description: "20% era, decay=5 - era matters a lot",
    audio_weight: 0.60,
    genre_weight: 0.15,
    era_weight: 0.20,
    pop_weight: 0.05,
    era_decay: 5,
    pop_decay: 30,
    genre_boost: 0.10,
    genre_penalty: -0.10,
    tier_1_pct: 20,
    tier_2_pct: 40,
    tier_3_pct: 60,
    tier_4_pct: 80,
    easy_tiers: '1,4,5',
    medium_tiers: '1,2,3',
    hard_tiers: '1,2',
  },
  popularity_contest: {
    name: "Popularity Contest",
    description: "20% pop - hits vs indie matters",
    audio_weight: 0.50,
    genre_weight: 0.20,
    era_weight: 0.10,
    pop_weight: 0.20,
    era_decay: 10,
    pop_decay: 20,
    genre_boost: 0.10,
    genre_penalty: -0.10,
    tier_1_pct: 20,
    tier_2_pct: 40,
    tier_3_pct: 60,
    tier_4_pct: 80,
    easy_tiers: '1,4,5',
    medium_tiers: '1,2,3',
    hard_tiers: '1,2',
  },
  easy_mode: {
    name: "Easy Mode (Obvious Matches)",
    description: "Tier 1 = 30%, includes more obvious wrong answers",
    audio_weight: 0.70,
    genre_weight: 0.15,
    era_weight: 0.10,
    pop_weight: 0.05,
    era_decay: 10,
    pop_decay: 30,
    genre_boost: 0.10,
    genre_penalty: -0.10,
    tier_1_pct: 30,
    tier_2_pct: 50,
    tier_3_pct: 70,
    tier_4_pct: 85,
    easy_tiers: '1,4,5',
    medium_tiers: '1,3,4',
    hard_tiers: '1,2,3',
  },
  hard_mode: {
    name: "Hard Mode (Subtle Distinctions)",
    description: "Tier 1 = 15%, only subtle differences allowed",
    audio_weight: 0.70,
    genre_weight: 0.15,
    era_weight: 0.10,
    pop_weight: 0.05,
    era_decay: 10,
    pop_decay: 30,
    genre_boost: 0.10,
    genre_penalty: -0.10,
    tier_1_pct: 15,
    tier_2_pct: 25,
    tier_3_pct: 40,
    tier_4_pct: 60,
    easy_tiers: '1,3,4,5',
    medium_tiers: '1,2,3',
    hard_tiers: '1,2',
  },
};




export default function StudioViewer() {
  const [seedUri, setSeedUri] = useState('spotify:track:1QvWxgZvTU0w8rlPRE5Zrv');
  const [allTracks, setAllTracks] = useState([]);
  const [seed, setSeed] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
    //for batch export
  const [batchUris, setBatchUris] = useState('');
  const [batchLoading, setBatchLoading] = useState(false);
  const [batchProgress, setBatchProgress] = useState(0);
  const [batchTotal, setBatchTotal] = useState(0);
  const [batchResults, setBatchResults] = useState([]);
  
  // Similarity params (trigger server re-analysis)
  const [params, setParams] = useState(PRESETS.default);
  
  // Bucketing params (instant client-side re-bucket)
  const [pools, setPools] = useState({ easy: [], medium: [], hard: [] });
  
  // UI state
  const [expandedSections, setExpandedSections] = useState({
    weights: true,
    era: false,
    popularity: false,
    genre: false,
    tiers: true,
    pools: true,
    dataset: false,
  });
  
  // Needs re-analysis indicator
  const [needsReanalysis, setNeedsReanalysis] = useState(false);



  // Load preset
  const loadPreset = (presetKey) => {
    setParams(PRESETS[presetKey]);
    setNeedsReanalysis(true);
  };

  // Analyze from server
  const analyze = async () => {
    if (!seedUri) {
      setError('Enter a Spotify track URI');
      return;
    }
    
    setLoading(true);
    setError(null);
    setNeedsReanalysis(false);
    
    try {
      const queryParams = new URLSearchParams({
        seed: seedUri,
        audio_weight: params.audio_weight,
        genre_weight: params.genre_weight,
        era_weight: params.era_weight,
        pop_weight: params.pop_weight,
        era_decay: params.era_decay,
        pop_decay: params.pop_decay,
        genre_boost: params.genre_boost,
        genre_penalty: params.genre_penalty,
        limit: params.limit || 2000,
        include_remasters: params.include_remasters ? '1' : '0',
        pop_floor: params.pop_floor || 0,
      });
      
      const response = await fetch(`http://localhost:8080/analyze?${queryParams}`);
      if (!response.ok) throw new Error(`Server error: ${response.status}`);
      
      const data = await response.json();
      setSeed(data.seed);
      setAllTracks(data.tracks);
      rebucket(data.tracks);
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  };

  // Client-side bucketing (instant)
  const rebucket = (tracks = allTracks) => {
    if (!tracks || tracks.length === 0) return;
    
    const { tier_1_pct, tier_2_pct, tier_3_pct, tier_4_pct } = params;
    
    // Already sorted by radio_fit desc from server
    const n = tracks.length;
    const t1_end = Math.floor(n * tier_1_pct / 100);
    const t2_end = Math.floor(n * tier_2_pct / 100);
    const t3_end = Math.floor(n * tier_3_pct / 100);
    const t4_end = Math.floor(n * tier_4_pct / 100);
    
    // Assign tiers
    const withTiers = tracks.map((t, i) => ({
      ...t,
      tier: i < t1_end ? 1 : i < t2_end ? 2 : i < t3_end ? 3 : i < t4_end ? 4 : 5,
      correct: i < t1_end, // Tier 1 = correct answers
    }));
    
    // Parse pool tier definitions
    const easy_tiers = params.easy_tiers.split(',').map(x => parseInt(x.trim()));
    const medium_tiers = params.medium_tiers.split(',').map(x => parseInt(x.trim()));
    const hard_tiers = params.hard_tiers.split(',').map(x => parseInt(x.trim()));
    
    setPools({
      easy: withTiers.filter(t => easy_tiers.includes(t.tier)),
      medium: withTiers.filter(t => medium_tiers.includes(t.tier)),
      hard: withTiers.filter(t => hard_tiers.includes(t.tier)),
    });
  };

  // Update param (mark if needs re-analysis)
  const updateParam = (key, value) => {
    const newParams = { ...params, [key]: value };
    setParams(newParams);
    
    // Bucketing params can rebucket instantly
    const bucketingParams = ['tier_1_pct', 'tier_2_pct', 'tier_3_pct', 'tier_4_pct', 
                             'easy_tiers', 'medium_tiers', 'hard_tiers'];
    if (bucketingParams.includes(key)) {
      // Re-assign tiers with new params
      rebucket();
    } else {
      setNeedsReanalysis(true);
    }
  };

  // Export profile
  const exportProfile = async () => {
    if (!seed || !pools.easy.length) {
      alert('Analyze a seed first');
      return;
    }
    
    try {
      const payload = {
        seed,
        params,
        pools,
      };
      
      const response = await fetch('http://localhost:8080/export', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });
      
      if (!response.ok) throw new Error(`Export failed: ${response.status}`);
      
      const result = await response.json();
      alert(`✅ Exported: ${result.filename}`);
    } catch (e) {
      alert(`❌ Export failed: ${e.message}`);
    }
  };

  // Toggle section
  const toggleSection = (key) => {
    setExpandedSections(prev => ({ ...prev, [key]: !prev[key] }));
  };

  const batchExport = async () => {
  const uris = batchUris.split('\n').map(u => u.trim()).filter(Boolean);
  if (uris.length === 0) {
    alert('Enter some URIs first');
    return;
  }
  
  setBatchLoading(true);
  setBatchProgress(0);
  setBatchTotal(uris.length);
  setBatchResults([]);
  
  const results = [];
  
  for (let i = 0; i < uris.length; i++) {
    const uri = uris[i];
    setBatchProgress(i + 1);
    
    try {
      // Analyze with default params
      const queryParams = new URLSearchParams({
        seed: uri,
        ...params, // Use current UI params (or hardcode defaults)
      });
      
      const analyzeRes = await fetch(`http://localhost:8080/analyze?${queryParams}`);
      
      if (!analyzeRes.ok) {
        throw new Error(`Analysis failed: ${analyzeRes.status}`);
      }
      
      const data = await analyzeRes.json();
      
      // Check if we got valid results
      if (!data.tracks || data.tracks.length === 0) {
        throw new Error('No valid tracks found');
      }
      
      // Rebucket to get pools
      const tracks = data.tracks;
      const n = tracks.length;
      const { tier_1_pct, tier_2_pct, tier_3_pct, tier_4_pct } = params;
      
      const t1_end = Math.floor(n * tier_1_pct / 100);
      const t2_end = Math.floor(n * tier_2_pct / 100);
      const t3_end = Math.floor(n * tier_3_pct / 100);
      const t4_end = Math.floor(n * tier_4_pct / 100);
      
      const withTiers = tracks.map((t, idx) => ({
        ...t,
        tier: idx < t1_end ? 1 : idx < t2_end ? 2 : idx < t3_end ? 3 : idx < t4_end ? 4 : 5,
        correct: idx < t1_end,
      }));
      
      const easy_tiers = params.easy_tiers.split(',').map(x => parseInt(x.trim()));
      const medium_tiers = params.medium_tiers.split(',').map(x => parseInt(x.trim()));
      const hard_tiers = params.hard_tiers.split(',').map(x => parseInt(x.trim()));
      
      const pools = {
        easy: withTiers.filter(t => easy_tiers.includes(t.tier)),
        medium: withTiers.filter(t => medium_tiers.includes(t.tier)),
        hard: withTiers.filter(t => hard_tiers.includes(t.tier)),
      };
      
      // Export
      const exportRes = await fetch('http://localhost:8080/export', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          seed: data.seed,
          params: data.params,
          pools,
        }),
      });
      
      if (!exportRes.ok) {
        throw new Error(`Export failed: ${exportRes.status}`);
      }
      
      const exportData = await exportRes.json();
      results.push({
        success: true,
        message: `${data.seed.name} by ${data.seed.artists.join(', ')} → ${exportData.filename}`,
      });
      
    } catch (e) {
      results.push({
        success: false,
        message: `${uri}: ${e.message}`,
      });
    }
  }
  
  setBatchResults(results);
  setBatchLoading(false);
};

  return (
    <div className="studio-viewer">
      <header className="studio-header">
        <h1>🎸 Hidden Tracks Profile Studio</h1>
        <p>Tune the algorithm, find the perfect similarity formula</p>
      </header>

      {/* Seed Input */}
      <section className="seed-input">
        <label>Spotify Track URI</label>
        <div className="input-row">
          <input
            type="text"
            value={seedUri}
            onChange={(e) => setSeedUri(e.target.value)}
            placeholder="spotify:track:..."
          />
          <button onClick={analyze} disabled={loading}>
            {loading ? '⏳ Analyzing...' : '🔍 Analyze'}
          </button>
        </div>
        {needsReanalysis && (
          <div className="warning">⚠️ Params changed. Re-analyze to apply.</div>
        )}
        {error && <div className="error">{error}</div>}
      </section>

      {/* Presets */}
        <section className="presets">
          <h3>⚡ Presets</h3>
          <div className="preset-buttons">
            {Object.keys(PRESETS).map(key => (
              <button key={key} onClick={() => loadPreset(key)} className="preset-button">
                <div className="preset-name">{PRESETS[key].name}</div>
                <div className="preset-description">{PRESETS[key].description}</div>
              </button>
            ))}
          </div>
  </section>

{/* Batch Export */}
<section className="batch-export">
  <h3>🚀 Batch Export</h3>
  <p>Paste Spotify URIs (one per line), hit export, go make coffee</p>
  <textarea
    placeholder="spotify:track:1QvWxgZvTU0w8rlPRE5Zrv&#10;spotify:track:2Foc5Q5nqNiosCNqttzHof&#10;spotify:track:5FVd6KXrgO9B3JPmC8OPst"
    rows={8}
    value={batchUris}
    onChange={(e) => setBatchUris(e.target.value)}
  />
  <button onClick={batchExport} disabled={batchLoading}>
    {batchLoading ? `⏳ Exporting... (${batchProgress}/${batchTotal})` : '💾 Batch Export All'}
  </button>
  {batchResults.length > 0 && (
    <div className="batch-results">
      <h4>Results:</h4>
      <ul>
        {batchResults.map((r, i) => (
          <li key={i} className={r.success ? 'success' : 'error'}>
            {r.success ? '✅' : '❌'} {r.message}
          </li>
        ))}
      </ul>
    </div>
  )}
</section>

      {/* Control Panel */}
      <section className="control-panel">
        <h2>🎛️ Control Panel</h2>

        {/* Weights */}
        <CollapsibleSection
          title="Similarity Weights"
          expanded={expandedSections.weights}
          onToggle={() => toggleSection('weights')}
          description="How much each factor matters in the similarity score. Should sum to ~1.0."
        >
          <ParamSlider
            label="Audio Weight"
            value={params.audio_weight}
            onChange={(v) => updateParam('audio_weight', v)}
            min={0}
            max={1}
            step={0.01}
          />
          <ParamSlider
            label="Genre Weight"
            value={params.genre_weight}
            onChange={(v) => updateParam('genre_weight', v)}
            min={0}
            max={1}
            step={0.01}
          />
          <ParamSlider
            label="Era Weight"
            value={params.era_weight}
            onChange={(v) => updateParam('era_weight', v)}
            min={0}
            max={1}
            step={0.01}
          />
          <ParamSlider
            label="Popularity Weight"
            value={params.pop_weight}
            onChange={(v) => updateParam('pop_weight', v)}
            min={0}
            max={1}
            step={0.01}
          />
        </CollapsibleSection>

        {/* Era Effect */}
        <CollapsibleSection
          title="Era Effect"
          expanded={expandedSections.era}
          onToggle={() => toggleSection('era')}
          description="How year distance affects similarity. Lower decay = stricter era matching."
        >
          <ParamSlider
            label="Era Decay (years half-life)"
            value={params.era_decay}
            onChange={(v) => updateParam('era_decay', v)}
            min={1}
            max={50}
            step={1}
          />
        </CollapsibleSection>

        {/* Popularity Effect */}
        <CollapsibleSection
          title="Popularity Effect"
          expanded={expandedSections.popularity}
          onToggle={() => toggleSection('popularity')}
          description="How popularity distance affects similarity. Lower decay = stricter pop matching."
        >
          <ParamSlider
            label="Pop Decay (points half-life)"
            value={params.pop_decay}
            onChange={(v) => updateParam('pop_decay', v)}
            min={1}
            max={100}
            step={1}
          />
        </CollapsibleSection>

        {/* Genre Effect */}
        <CollapsibleSection
          title="Genre Effect"
          expanded={expandedSections.genre}
          onToggle={() => toggleSection('genre')}
          description="Genre overlap bonus/penalty. Boost rewards matches, penalty punishes mismatches."
        >
          <ParamSlider
            label="Genre Boost (when genres overlap)"
            value={params.genre_boost}
            onChange={(v) => updateParam('genre_boost', v)}
            min={0}
            max={0.5}
            step={0.01}
          />
          <ParamSlider
            label="Genre Penalty (no overlap)"
            value={params.genre_penalty}
            onChange={(v) => updateParam('genre_penalty', v)}
            min={-0.5}
            max={0}
            step={0.01}
          />
        </CollapsibleSection>

        {/* Tier Boundaries */}
        <CollapsibleSection
          title="Tier Boundaries (Percentiles)"
          expanded={expandedSections.tiers}
          onToggle={() => toggleSection('tiers')}
          description="Where to cut tiers in the sorted list. Tier 1 = correct answers."
        >
          <ParamSlider
            label="Tier 1 % (correct answers)"
            value={params.tier_1_pct}
            onChange={(v) => updateParam('tier_1_pct', v)}
            min={5}
            max={50}
            step={1}
          />
          <ParamSlider
            label="Tier 2 %"
            value={params.tier_2_pct}
            onChange={(v) => updateParam('tier_2_pct', v)}
            min={10}
            max={70}
            step={1}
          />
          <ParamSlider
            label="Tier 3 %"
            value={params.tier_3_pct}
            onChange={(v) => updateParam('tier_3_pct', v)}
            min={20}
            max={85}
            step={1}
          />
          <ParamSlider
            label="Tier 4 %"
            value={params.tier_4_pct}
            onChange={(v) => updateParam('tier_4_pct', v)}
            min={30}
            max={95}
            step={1}
          />
        </CollapsibleSection>

        {/* Pool Composition */}
        <CollapsibleSection
          title="Pool Composition"
          expanded={expandedSections.pools}
          onToggle={() => toggleSection('pools')}
          description="Which tiers go into each difficulty pool. Comma-separated (e.g., '1,4,5')."
        >
          <ParamText
            label="Easy Tiers"
            value={params.easy_tiers}
            onChange={(v) => updateParam('easy_tiers', v)}
            placeholder="1,4,5"
          />
          <ParamText
            label="Medium Tiers"
            value={params.medium_tiers}
            onChange={(v) => updateParam('medium_tiers', v)}
            placeholder="1,2,3"
          />
          <ParamText
            label="Hard Tiers"
            value={params.hard_tiers}
            onChange={(v) => updateParam('hard_tiers', v)}
            placeholder="1,2"
          />
        </CollapsibleSection>

        {/* Dataset */}
        <CollapsibleSection
          title="Dataset Options"
          expanded={expandedSections.dataset}
          onToggle={() => toggleSection('dataset')}
          description="Filtering and limits for the candidate set."
        >
          <ParamSlider
            label="Limit (max tracks)"
            value={params.limit || 2000}
            onChange={(v) => updateParam('limit', v)}
            min={100}
            max={5000}
            step={100}
          />
          <ParamSlider
            label="Popularity Floor (min)"
            value={params.pop_floor || 0}
            onChange={(v) => updateParam('pop_floor', v)}
            min={0}
            max={80}
            step={5}
          />
          <ParamSlider
            label="Radio Fit Floor (min similarity)"
            value={params.radio_fit_floor || 0}
            onChange={(v) => updateParam('radio_fit_floor', v)}
            min={0}
            max={0.8}
            step={0.05}
          />
          <ParamSlider
              label="Max Speechiness (0.66 = spoken word)"
              value={params.max_speechiness || 0.66}
              onChange={(v) => updateParam('max_speechiness', v)}
              min={0.33}
              max={1.0}
              step={0.01}
            />
          <label>
            <input
              type="checkbox"
              checked={params.include_remasters || false}
              onChange={(e) => updateParam('include_remasters', e.target.checked)}
            />
            Include remasters & alt versions
          </label>
        </CollapsibleSection>
      </section>

      {/* Results */}
      {seed && allTracks.length > 0 && (
        <section className="results">
          <h2>📊 Results</h2>
          
          {/* Seed Info */}
          <div className="seed-info">
            <h3>Seed: {seed.name}</h3>
            <p>
              {seed.artists.join(', ')} ({seed.year}) • Pop: {seed.popularity}
            </p>
            {seed.genres && seed.genres.length > 0 && (
              <p className="genres">{seed.genres.slice(0, 5).join(', ')}</p>
            )}
          </div>

          {/* Pool Stats */}
          <div className="pool-stats">
            <StatCard
              title="Easy Pool"
              total={pools.easy.length}
              correct={pools.easy.filter(t => t.correct).length}
            />
            <StatCard
              title="Medium Pool"
              total={pools.medium.length}
              correct={pools.medium.filter(t => t.correct).length}
            />
            <StatCard
              title="Hard Pool"
              total={pools.hard.length}
              correct={pools.hard.filter(t => t.correct).length}
            />
          </div>

          {/* Tables */}
          <TrackTable title="All Tracks" tracks={allTracks} />
          <TrackTable title="Easy Pool" tracks={pools.easy} />
          <TrackTable title="Medium Pool" tracks={pools.medium} />
          <TrackTable title="Hard Pool" tracks={pools.hard} />
        </section>
      )}

      {/* Export */}
      {seed && pools.easy.length > 0 && (
        <section className="export-section">
          <button className="export-button" onClick={exportProfile}>
            💾 Export Profile
          </button>
        </section>
      )}
    </div>
  );
}

/* =======================
   Sub-components
   ======================= */

function CollapsibleSection({ title, expanded, onToggle, description, children }) {
  return (
    <div className="collapsible-section">
      <div className="section-header" onClick={onToggle}>
        <h3>{expanded ? '▼' : '▶'} {title}</h3>
      </div>
      {expanded && (
        <>
          {description && <p className="section-description">{description}</p>}
          <div className="section-content">{children}</div>
        </>
      )}
    </div>
  );
}

function ParamSlider({ label, value, onChange, min, max, step }) {
  return (
    <div className="param-control">
      <label>{label}</label>
      <div className="slider-input">
        <input
          type="range"
          min={min}
          max={max}
          step={step}
          value={value}
          onChange={(e) => onChange(parseFloat(e.target.value))}
        />
        <input
          type="number"
          min={min}
          max={max}
          step={step}
          value={value}
          onChange={(e) => onChange(parseFloat(e.target.value))}
        />
      </div>
    </div>
  );
}

function ParamText({ label, value, onChange, placeholder }) {
  return (
    <div className="param-control">
      <label>{label}</label>
      <input
        type="text"
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder={placeholder}
      />
    </div>
  );
}

function StatCard({ title, total, correct }) {
  const incorrect = total - correct;
  const correctPct = total > 0 ? ((correct / total) * 100).toFixed(1) : 0;
  
  return (
    <div className="stat-card">
      <h4>{title}</h4>
      <div className="stat-numbers">
        <div>Total: <strong>{total}</strong></div>
        <div className="correct">Correct: <strong>{correct}</strong> ({correctPct}%)</div>
        <div className="incorrect">Wrong: <strong>{incorrect}</strong></div>
      </div>
    </div>
  );
}

function TrackTable({ title, tracks }) {
  return (
    <div className="track-table-container">
      <h3>{title} ({tracks.length} tracks)</h3>
      <div className="table-wrapper">
        <table className="track-table">
          <thead>
            <tr>
              <th>Track</th>
              <th>Artists</th>
              <th>Year</th>
              <th>Pop</th>
              <th>Radio Fit</th>
              <th>Audio Sim</th>
              <th>Genre Sim</th>
              <th>Era Dist</th>
              <th>Tier</th>
              <th>Answer</th>
            </tr>
          </thead>
          <tbody>
            {tracks.map((track, i) => (
              <tr key={i} className={track.correct ? 'correct-row' : 'incorrect-row'}>
                <td className="track-name">{track.name}</td>
                <td className="artists">{track.artists?.join(', ') || '—'}</td>
                <td>{track.year || '—'}</td>
                <td>{track.popularity ?? '—'}</td>
                <td className="score">
                  <span className={getScoreClass(track.radio_fit)}>
                    {track.radio_fit ? track.radio_fit.toFixed(3) : '—'}
                  </span>
                </td>
                <td className="score">{track.audio_sim ? track.audio_sim.toFixed(3) : '—'}</td>
                <td className="score">{track.genre_sim ? track.genre_sim.toFixed(3) : '—'}</td>
                <td>{track.era_dist ?? '—'}</td>
                <td>
                  <span className={`tier-badge tier-${track.tier}`}>
                    T{track.tier}
                  </span>
                </td>
                <td>
                  <span className={track.correct ? 'answer-correct' : 'answer-incorrect'}>
                    {track.correct ? '✓ Correct' : '✗ Wrong'}
                  </span>
                </td>
              </tr>
            ))}
          </tbody>
          {/* <tbody>
            {tracks.map((track, i) => (
              <tr key={i} className={track.correct ? 'correct-row' : 'incorrect-row'}>
                <td className="track-name">{track.name}</td>
                <td className="artists">{track.artists.join(', ')}</td>
                <td>{track.year || '–'}</td>
                <td>{track.popularity}</td>
                <td className="score">
                  <span className={getScoreClass(track.radio_fit)}>
                    {track.radio_fit.toFixed(3)}
                  </span>
                </td>
                <td className="score">{track.audio_sim.toFixed(3)}</td>
                <td className="score">{track.genre_sim.toFixed(3)}</td>
                <td className="score">{track.audio_sim ? track.audio_sim.toFixed(3) : '—'}</td>
                <td className="score">{track.genre_sim ? track.genre_sim.toFixed(3) : '—'}</td>
                <td>{track.era_dist || 0}</td>
                <td>
                  <span className={`tier-badge tier-${track.tier}`}>
                    T{track.tier}
                  </span>
                </td>
                <td>
                  <span className={track.correct ? 'answer-correct' : 'answer-incorrect'}>
                    {track.correct ? '✓ Correct' : '✗ Wrong'}
                  </span>
                </td>
              </tr>
            ))}
          </tbody> */}
        </table>
      </div>
    </div>
  );
}

function getScoreClass(score) {
  if (score >= 0.7) return 'score-high';
  if (score >= 0.5) return 'score-med';
  return 'score-low';
}
