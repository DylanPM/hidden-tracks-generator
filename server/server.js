import express from "express";
import cors from "cors";
import fs from "fs";
import path from "path";
import bodyParser from "body-parser";
import { analyzeTrack, loadDatasetOnce } from "./analyze_core.js";



const app = express();
app.use(cors());
app.use(bodyParser.json({ limit: "5mb" }));

function ensureDir(p) {
  if (!fs.existsSync(p)) fs.mkdirSync(p, { recursive: true });
}

/* ============== Routes ============== */

app.get("/health", (_req, res) => res.json({ ok: true }));

// Main analyze endpoint - returns flat scored list
app.get("/analyze", async (req, res) => {
  try {
    const seed = req.query.seed;
    if (!seed) return res.status(400).json({ error: "Missing seed parameter" });
    
    const result = await analyzeTrack(seed, req.query);
    res.json(result);
  } catch (e) {
    console.error("Analyze error:", e);
    res.status(500).json({ error: String(e.message || e) });
  }
});

// Peek at raw dataset
app.get("/debug/peek", (req, res) => {
  try {
    const n = Math.min(parseInt(req.query.n ?? "5", 10), 50);
    const data = loadDatasetOnce();
    res.json({ count: data.length, rows: data.slice(0, n) });
  } catch (e) {
    res.status(500).json({ error: String(e.message || e) });
  }
});

// Export profile to disk
app.post("/export", async (req, res) => {
  try {
    const { seed, params, pools } = req.body;
    if (!seed) return res.status(400).json({ error: "Missing seed" });
    if (!pools) return res.status(400).json({ error: "Missing pools" });
    
    // BUILD UNIQUE TRACK LIST WITH POOL TAGS
    const trackMap = new Map();
    
    for (const [poolName, tracks] of Object.entries(pools)) {
      for (const track of tracks) {
        const key = track.id;
        
        if (trackMap.has(key)) {
          // Track already exists, add this pool to its list
          trackMap.get(key).pools.push(poolName);
        } else {
          // New track, create entry with first pool
          trackMap.set(key, {
            ...track,
            pools: [poolName]  // Array of pool names
          });
        }
      }
    }
    
    // Convert map to array
    const tracks = Array.from(trackMap.values());
    
    const profile = {
      seed: {
        id: seed.id,
        name: seed.name,
        artists: seed.artists,
        year: seed.year,
        popularity: seed.popularity,
        genres: seed.genres || [],
      },
      params,
      tracks,  // Single array of unique tracks with pool tags
      exported_at: new Date().toISOString(),
    };
    
    const outDir = path.join(process.cwd(), "exports");
    ensureDir(outDir);
    
    // BETTER NAMING: Use track name instead of ID + timestamp
    const safeName = seed.name
      .toLowerCase()
      .replace(/[^a-z0-9]+/g, '-')  // Replace special chars with dashes
      .replace(/^-+|-+$/g, '');     // Trim dashes from ends
    
    const artist = seed.artists[0]
      .toLowerCase()
      .replace(/[^a-z0-9]+/g, '-')
      .replace(/^-+|-+$/g, '');
    
    const filename = `${artist}_${safeName}.json`;
    let finalFilename = filename;
    
    // If file exists, append a number
    let counter = 1;
    while (fs.existsSync(path.join(outDir, finalFilename))) {
      finalFilename = `${artist}_${safeName}_${counter}.json`;
      counter++;
    }
    
    const filepath = path.join(outDir, finalFilename);
    
    fs.writeFileSync(filepath, JSON.stringify(profile, null, 2), "utf8");
    
    // Update manifest
    const manifestPath = path.join(outDir, "manifest.json");
    let manifest = [];
    if (fs.existsSync(manifestPath)) {
      try {
        manifest = JSON.parse(fs.readFileSync(manifestPath, "utf8"));
      } catch {}
    }
    
    manifest.unshift({
      filename: finalFilename,
      seed: { 
        id: seed.id, 
        name: seed.name, 
        artists: seed.artists 
      },
      exported_at: profile.exported_at,
    });
    
    fs.writeFileSync(
      manifestPath,
      JSON.stringify(manifest.slice(0, 100), null, 2),
      "utf8"
    );
    
    res.json({ success: true, filename: finalFilename });
  } catch (e) {
    console.error("Export error:", e);
    res.status(500).json({ error: String(e.message || e) });
  }
});
// app.post("/export", async (req, res) => {
//   try {
//     const { seed, params, pools } = req.body;
//     if (!seed) return res.status(400).json({ error: "Missing seed" });
//     if (!pools) return res.status(400).json({ error: "Missing pools" });
    
//     const profile = {
//       seed,
//       params,
//       pools,
//       exported_at: new Date().toISOString(),
//     };
    
//     const outDir = path.join(process.cwd(), "exports");
//     ensureDir(outDir);
    
//     // BETTER NAMING: Use track name instead of URI + timestamp
//     const safeName = seed.name
//       .toLowerCase()
//       .replace(/[^a-z0-9]+/g, '-')  // Replace special chars with dashes
//       .replace(/^-+|-+$/g, '');     // Trim dashes from ends
    
//     const artist = seed.artists[0]
//       .toLowerCase()
//       .replace(/[^a-z0-9]+/g, '-')
//       .replace(/^-+|-+$/g, '');
    
//     const filename = `${artist}_${safeName}.json`;
//     const filepath = path.join(outDir, filename);
    
//     // If file exists, append a number
//     let finalFilename = filename;
//     let counter = 1;
//     while (fs.existsSync(path.join(outDir, finalFilename))) {
//       finalFilename = `${artist}_${safeName}_${counter}.json`;
//       counter++;
//     }
    
//     fs.writeFileSync(
//       path.join(outDir, finalFilename),
//       JSON.stringify(profile, null, 2),
//       "utf8"
//     );
    
//     // Update manifest
//     const manifestPath = path.join(outDir, "manifest.json");
//     let manifest = [];
//     if (fs.existsSync(manifestPath)) {
//       try {
//         manifest = JSON.parse(fs.readFileSync(manifestPath, "utf8"));
//       } catch {}
//     }
//     manifest.unshift({
//       filename: finalFilename,
//       seed: { id: seed.id, name: seed.name, artists: seed.artists },
//       exported_at: profile.exported_at,
//     });
//     fs.writeFileSync(
//       manifestPath,
//       JSON.stringify(manifest.slice(0, 100), null, 2),
//       "utf8"
//     );
    
//     res.json({ success: true, filename: finalFilename });
//   } catch (e) {
//     console.error("Export error:", e);
//     res.status(500).json({ error: String(e.message || e) });
//   }
// });

const PORT = process.env.PORT || 8080;
app.listen(PORT, () => {
  console.log(`🎵 Profile Generator Server running on http://localhost:${PORT}`);
  console.log(`📊 Try: http://localhost:${PORT}/analyze?seed=spotify:track:1QvWxgZvTU0w8rlPRE5Zrv`);
});
