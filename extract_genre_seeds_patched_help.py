# extract_genre_seeds_patched.py
# Purpose: Build a manifest tree with per-genre seeds and per-genre feature medians,
# plus global feature medians and minimal display hints, with extensive validation
# and optional debug reporting.

from __future__ import annotations

import json
import math
import random
import sys
from collections import defaultdict
from datetime import datetime, timezone
from statistics import median
from typing import Any, Dict, List, Optional, Tuple, Set, Mapping, MutableMapping, Iterable, Union, cast
import os, sys, time, json, math, argparse

# ============================================================
# Types
# ============================================================

Track = Dict[str, Any]
ResultBucket = Dict[str, List[Track]]
ManifestNode = Dict[str, Any]
ManifestTree = Dict[str, ManifestNode]
FeatureDict = Dict[str, Optional[float]]

# ============================================================
# Config
# ============================================================

FEATURE_FIELDS: List[str] = [
    "danceability",
    "energy",
    "speechiness",
    "acousticness",
    "valence",
    "popularity",
    "instrumentalness",
]

TEMPO_MIN = 70.0
TEMPO_MAX = 200.0

SAMPLE_SIZE_PER_GENRE_DEFAULT = 5
SEEDS_PER_GENRE_DEFAULT = 4

# Shoegaze canonical artists to ensure coverage
SHOEGAZE_WHITELIST_ARTISTS: Set[str] = {
    "my bloody valentine", "slowdive", "ride", "lush", "chapterhouse",
    "cocteau twins", "pale saints", "alcest", "mbv", "catherine wheel"
}

# Punk filters
PUNK_NEG_GENRES: Set[str] = {
    "ska", "ska punk", "third wave ska", "2 tone", "skacore", "ska revival"
}
PUNK_POS_GENRES: Set[str] = {
    "punk", "punk rock", "hardcore punk", "77 punk", "post-punk", "anarcho-punk"
}

# East Coast Hip Hop signals
EC_HIPHOP_POS_GENRES: Set[str] = {
    "east coast hip hop", "nyc rap", "boom bap", "queens hip hop",
    "brooklyn drill", "harlem hip hop"
}
EC_HIPHOP_WHITELIST_ARTISTS: Set[str] = {
    "the notorious b.i.g.", "biggie", "nas", "mobb deep", "wu-tang clan",
    "jay-z", "a tribe called quest", "gang starr", "rakim", "eric b. & rakim",
    "onyx", "fat joe", "mos def", "yasiin bey", "talib kweli", "big l",
    "busta rhymes", "cam’ron", "camron", "redman", "method man",
    "ghostface killah", "raekwon", "joey bada$$", "public enemy", "black star"
}

# Disco rules
DISCO_POS_GENRES: Set[str] = {"disco", "classic disco", "philly soul", "hi-nrg", "italo disco"}
DISCO_BLOCKLIST_HINTS: Set[str] = {"footloose", "soundtrack", "ost"}

# Nu Metal cleanup
NU_METAL_BAD_HINTS: Set[str] = {"acoustic", "unplugged", "remix", "radio edit"}

# Metal nudges so pure metal outranks crossover
CANONICAL_METAL_ARTIST_HINTS: Set[str] = {
    "metallica", "slayer", "pantera", "anthrax", "megadeth",
    "judas priest", "iron maiden", "sepultura", "meshuggah", "lamb of god"
}

# Exceptions and swaps reported by you
CURATION_EXCLUDE_URIS: Set[str] = {
    "spotify:track:1OppEieGNdItZbE14gLBEv",  # Supremes not funk
    "spotify:track:0B9x2BRHqj3Qer7biM3pU3",  # Grease not disco
    "spotify:track:3Be7CLdHZpyzsVijme39cW",  # Kygo not disco
    "spotify:track:6JyEh4kl9DLwmSAoNDRn5b",  # 4th Dimension not swing or soul
    "spotify:track:2wSAWEYUHkt92X4SBAPqZE",  # Karma Chameleon not romantic classical
}

# ============================================================
# Utilities
# ============================================================

def norm_name(s: Any) -> str:
    return str(s or "").strip().lower()

def safe_float(v: Any) -> Optional[float]:
    try:
        if v is None:
            return None
        return float(v)
    except Exception:
        return None

def safe_int(v: Any) -> Optional[int]:
    try:
        if v is None:
            return None
        return int(v)
    except Exception:
        return None

def sround(x: Optional[float], nd: int = 2) -> Optional[float]:
    if x is None:
        return None
    try:
        return round(float(x), nd)
    except Exception:
        return None

def median_int(vals: List[int]) -> Optional[int]:
    if not vals:
        return None
    vals_sorted = sorted(vals)
    return int(median(vals_sorted))

def tempo_to_norm(bpm: Optional[float]) -> Optional[float]:
    if bpm is None:
        return None
    x = max(TEMPO_MIN, min(TEMPO_MAX, float(bpm)))
    rng = TEMPO_MAX - TEMPO_MIN
    if rng <= 0:
        return None
    return (x - TEMPO_MIN) / rng

def track_genres(t: Track) -> Set[str]:
    if "genres" in t and isinstance(t["genres"], list):
        return {norm_name(g) for g in t["genres"] if isinstance(g, str)}
    if "artist_genres" in t and isinstance(t["artist_genres"], list):
        return {norm_name(g) for g in t["artist_genres"] if isinstance(g, str)}
    return set()

def track_artist_name(t: Track) -> str:
    if "artist" in t and isinstance(t["artist"], str):
        return t["artist"]
    if "artists" in t and isinstance(t["artists"], list) and t["artists"]:
        return str(t["artists"][0])
    return "Unknown"

def nonempty(vals: Iterable[Any]) -> bool:
    for v in vals:
        if v is not None:
            return True
    return False

# ============================================================
# Validation helpers
# ============================================================

def validate_track_shape(t: Track) -> bool:
    # URI, name, artist, features and year are expected but we accept partial rows
    if not isinstance(t, dict):
        return False
    if not t.get("uri"):
        return False
    if not t.get("name"):
        return False
    return True

def validate_results(results: ResultBucket) -> List[str]:
    problems: List[str] = []
    for pool_name, tracks in results.items():
        if not isinstance(tracks, list):
            problems.append(f"Pool {pool_name} is not a list")
            continue
        for idx, t in enumerate(tracks):
            if not validate_track_shape(t):
                problems.append(f"Pool {pool_name} has invalid track at index {idx}")
    return problems

def validate_manifest_shape(root: ManifestTree) -> List[str]:
    problems: List[str] = []
    if not isinstance(root, dict):
        return ["Manifest root must be an object"]
    for k, node in root.items():
        if not isinstance(node, dict):
            problems.append(f"Node {k} is not an object")
            continue
        # Accept _seeds, _alias, subgenres
        if "subgenres" in node and not isinstance(node["subgenres"], dict):
            problems.append(f"Node {k} has non-object subgenres")
    return problems

# ============================================================
# Curation predicates
# ============================================================

def is_core_punk(t: Track) -> bool:
    if t.get("uri") in CURATION_EXCLUDE_URIS:
        return False
    gs = track_genres(t)
    if gs & PUNK_NEG_GENRES:
        return False
    return bool(gs & PUNK_POS_GENRES)

def is_shoegaze_candidate(t: Track) -> bool:
    if t.get("uri") in CURATION_EXCLUDE_URIS:
        return False
    artist = norm_name(track_artist_name(t))
    gs = track_genres(t)
    return ("shoegaze" in gs) or (artist in SHOEGAZE_WHITELIST_ARTISTS)

def is_east_coast_hiphop(t: Track) -> bool:
    if t.get("uri") in CURATION_EXCLUDE_URIS:
        return False
    artist = norm_name(track_artist_name(t))
    gs = track_genres(t)
    if artist in EC_HIPHOP_WHITELIST_ARTISTS:
        return True
    if gs & EC_HIPHOP_POS_GENRES:
        return True
    if any("west coast" in g for g in gs):
        return False
    hay = " ".join(gs)
    return ("hip hop" in hay) or ("rap" in hay)

def is_disco_track(t: Track) -> bool:
    if t.get("uri") in CURATION_EXCLUDE_URIS:
        return False
    gs = track_genres(t)
    name = norm_name(t.get("name"))
    year = safe_int(t.get("release_year"))
    if any(h in name for h in DISCO_BLOCKLIST_HINTS):
        return False
    if gs & DISCO_POS_GENRES:
        return True
    if year is not None and 1974 <= year <= 1985:
        return "disco" in " ".join(gs)
    return False

def genre_specific_filter(genre_key: str, tracks: List[Track]) -> List[Track]:
    g = norm_name(genre_key)
    if g == "punk":
        filtered = [t for t in tracks if is_core_punk(t)]
        return filtered or tracks
    if g == "shoegaze":
        base = [t for t in tracks if is_shoegaze_candidate(t)]
        return base or tracks
    if g in {"east coast hip hop", "east coast", "east coast rap"}:
        filtered = [t for t in tracks if is_east_coast_hiphop(t)]
        return filtered or tracks
    if g == "disco":
        filtered = [t for t in tracks if is_disco_track(t)]
        return filtered or tracks
    if g == "nu metal":
        out: List[Track] = []
        for t in tracks:
            name = norm_name(t.get("name"))
            gs = track_genres(t)
            if "nu metal" in gs and not any(h in name for h in NU_METAL_BAD_HINTS):
                out.append(t)
        return out or tracks
    if g == "metal":
        def metal_score(t: Track) -> int:
            gs = track_genres(t)
            score = 0
            if "metal" in " ".join(gs):
                score += 2
            artist = norm_name(track_artist_name(t))
            if any(k in artist for k in CANONICAL_METAL_ARTIST_HINTS):
                score += 3
            return score
        return sorted(tracks, key=metal_score, reverse=True)
    return tracks

# ============================================================
# Feature aggregation
# ============================================================

EMPTY_FEATURES: FeatureDict = {
    "danceability": None,
    "energy": None,
    "speechiness": None,
    "acousticness": None,
    "valence": None,
    "tempo_bpm": None,
    "tempo_norm": None,
    "popularity": None,
    "instrumentalness": None,
}

def compute_features_from_tracks(seed_tracks: List[Track]) -> Tuple[FeatureDict, Optional[int]]:
    fvals: Dict[str, List[float]] = defaultdict(list)
    years: List[int] = []
    tempos: List[float] = []

    for t in seed_tracks:
        for f in FEATURE_FIELDS:
            fv = safe_float(t.get(f))
            if fv is not None:
                fvals[f].append(fv)
        bpm = safe_float(t.get("tempo"))
        if bpm is not None:
            tempos.append(bpm)
        y = safe_int(t.get("release_year"))
        if y is not None:
            years.append(y)

    features: FeatureDict = dict(EMPTY_FEATURES)

    for k, vals in fvals.items():
        if vals:
            features[k] = sround(median(vals), 2)

    if tempos:
        med_bpm = median(tempos)
        features["tempo_bpm"] = sround(med_bpm, 2)
        features["tempo_norm"] = sround(tempo_to_norm(med_bpm), 2)

    med_year = median_int(years)
    return features, med_year

def aggregate_features_from_children(children_nodes: Dict[str, Any]) -> Tuple[FeatureDict, Optional[int]]:
    agg_lists: Dict[str, List[float]] = defaultdict(list)
    years: List[int] = []

    for child in children_nodes.values():
        feat = cast(FeatureDict, child.get("features") or {})
        for k, v in feat.items():
            if v is not None:
                agg_lists[k].append(float(v))
        child_year = safe_int(child.get("median_year"))
        if child_year is not None:
            years.append(child_year)

    out_feat: FeatureDict = dict(EMPTY_FEATURES)
    for k, vals in agg_lists.items():
        if vals:
            out_feat[k] = sround(median(vals), 2)

    med_year = median_int(years)
    return out_feat, med_year

# ============================================================
# Seed selection
# ============================================================

def choose_seeds_for_genre(genre_key: str, pool: List[Track], limit: int = SEEDS_PER_GENRE_DEFAULT) -> List[Track]:
    # Remove excluded URIs early
    pool = [t for t in pool if t.get("uri") not in CURATION_EXCLUDE_URIS]

    # Apply genre specific filters
    pool = genre_specific_filter(genre_key, pool)

    # Score function nudges era and popularity
    def score(t: Track) -> float:
        pop = safe_float(t.get("popularity")) or 0.0
        year = safe_int(t.get("release_year")) or 0
        pop_term = -abs(pop - 60) / 60.0
        era_term = 0.0
        g = norm_name(genre_key)
        if g == "disco" and year:
            if 1975 <= year <= 1982:
                era_term += 0.5
            else:
                era_term -= 0.4
        if g == "shoegaze" and year:
            if 1989 <= year <= 1996:
                era_term += 0.35
        return pop_term + era_term

    ranked = sorted(pool, key=score, reverse=True)

    # Dedup by artist and title
    dedup: List[Track] = []
    seen: Set[str] = set()
    for t in ranked:
        key = f"{norm_name(track_artist_name(t))}::{norm_name(t.get('name'))}"
        if key in seen:
            continue
        seen.add(key)
        dedup.append(t)
        if len(dedup) == limit:
            break

    # Ensure shoegaze gets canonical if missing
    g = norm_name(genre_key)
    if g == "shoegaze" and len(dedup) < limit:
        # Backfill from pool by whitelist artist
        cand = [t for t in pool if norm_name(track_artist_name(t)) in SHOEGAZE_WHITELIST_ARTISTS]
        for t in cand:
            key = f"{norm_name(track_artist_name(t))}::{norm_name(t.get('name'))}"
            if key in seen:
                continue
            dedup.append(t)
            seen.add(key)
            if len(dedup) == limit:
                break

    return dedup

# ============================================================
# Manifest building
# ============================================================

def resolve_seed_pool(node: ManifestNode, results: ResultBucket) -> List[Track]:
    seeds_key: Optional[str] = node.get("_seeds") if isinstance(node.get("_seeds"), str) else None
    alias_key: Optional[str] = node.get("_alias") if isinstance(node.get("_alias"), str) else None
    seed_pool: List[Track] = []
    if seeds_key:
        seed_pool = results.get(seeds_key, [])
    if not seed_pool and alias_key:
        seed_pool = results.get(alias_key, [])
    return seed_pool

def build_node(name: str, node: ManifestNode, results: ResultBucket, sample_size_per_genre: int) -> ManifestNode:
    out: ManifestNode = {}

    # Build subgenres first
    sub_out: Dict[str, Any] = {}
    sub = node.get("subgenres")
    if isinstance(sub, dict):
        for child_name, child_node in sub.items():
            if isinstance(child_node, dict):
                sub_out[child_name] = build_node(child_name, child_node, results, sample_size_per_genre)

    # Resolve seed pool for this node
    pool = resolve_seed_pool(node, results)

    # Choose seeds
    seeds_payload: List[Dict[str, Any]] = []
    features: FeatureDict = dict(EMPTY_FEATURES)
    med_year: Optional[int] = None

    if pool:
        chosen = choose_seeds_for_genre(name, pool, limit=SEEDS_PER_GENRE_DEFAULT)
        for t in chosen:
            seeds_payload.append({
                "uri": t.get("uri"),
                "name": t.get("name"),
                "artist": track_artist_name(t),
                "popularity": safe_float(t.get("popularity")),
                "release_year": safe_int(t.get("release_year")),
            })
        features, med_year = compute_features_from_tracks(chosen)

    # If no features yet, aggregate from children
    if all(v is None for v in features.values()) and sub_out:
        agg_feat, agg_year = aggregate_features_from_children(sub_out)
        features = agg_feat
        med_year = agg_year if agg_year is not None else med_year

    # Assign fields
    out["features"] = features
    out["median_year"] = med_year if med_year is not None else None
    if seeds_payload:
        out["seeds"] = seeds_payload
    if sub_out:
        out["subgenres"] = sub_out

    return out

def traverse_collect(node: ManifestNode) -> Iterable[ManifestNode]:
    yield node
    if "subgenres" in node and isinstance(node["subgenres"], dict):
        for child in node["subgenres"].values():
            yield from traverse_collect(child)

def postprocess_backfill_seeds(tree_out: Dict[str, Any], results: ResultBucket) -> None:
    # If a node has no seeds but has a pool, try to pick some
    for name, node in tree_out.items():
        for n in traverse_collect(node):
            if "seeds" in n and n["seeds"]:
                continue
            # Try re-resolving pool
            # There is no direct link here, so we cannot fix without manifest hints
            # This function is kept for future improvements where we persist pool keys
            pass

def buildManifestTree(root: ManifestTree,
                      results: ResultBucket,
                      dataset_id: str = "prepped_v7_2025-11-04",
                      sample_size_per_genre: int = SAMPLE_SIZE_PER_GENRE_DEFAULT) -> Dict[str, Any]:

    # Validate inputs
    man_problems = validate_manifest_shape(root)
    res_problems = validate_results(results)
    if man_problems or res_problems:
        print("Validation warnings:", file=sys.stderr)
        for p in man_problems + res_problems:
            print("  " + p, file=sys.stderr)

    # Build nodes
    tree_out: Dict[str, Any] = {}
    for genre_name, node in root.items():
        if isinstance(node, dict):
            tree_out[genre_name] = build_node(genre_name, node, results, sample_size_per_genre)

    # Collect global feature medians from node features
    global_vals: Dict[str, List[float]] = defaultdict(list)
    global_years: List[int] = []
    track_count = 0

    def collect(node: ManifestNode):
        nonlocal track_count
        feat = cast(FeatureDict, node.get("features") or {})
        for k, v in feat.items():
            if k in FEATURE_FIELDS and v is not None:
                global_vals[k].append(float(v))
        if node.get("median_year") is not None:
            iy = safe_int(node["median_year"])
            if iy is not None:
                global_years.append(iy)
        if "seeds" in node:
            for _ in node["seeds"]:
                track_count += 1
        if "subgenres" in node and isinstance(node["subgenres"], dict):
            for child in node["subgenres"].values():
                collect(child)

    for n in tree_out.values():
        collect(n)

    global_features: FeatureDict = dict(EMPTY_FEATURES)
    for k, vals in global_vals.items():
        if vals:
            global_features[k] = sround(median(vals), 2)

    if global_features.get("tempo_bpm") is not None:
        tbpm = safe_float(global_features["tempo_bpm"])
        global_features["tempo_norm"] = sround(tempo_to_norm(tbpm), 2)
    else:
        global_features["tempo_norm"] = None

    global_median_year = median_int(global_years)

    export: Dict[str, Any] = {
        "global": {
            "features": global_features,
            "median_year": global_median_year,
        },
        "display": {
            "feature_angles": [
                "danceability", "energy", "speechiness", "acousticness",
                "valence", "tempo_norm", "popularity", "instrumentalness"
            ],
            "projection_scale": 180,
            "exaggeration_default": 1.2,
            "speechiness_contrast_gamma": 1.3
        },
        "build": {
            "schema_version": "1",
            "dataset_id": dataset_id,
            "track_count": track_count,
            "sample_size_per_genre": sample_size_per_genre,
            "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "tempo_window": {"min_bpm": TEMPO_MIN, "max_bpm": TEMPO_MAX},
        },
        "genres": tree_out,
    }

    return export

# ============================================================
# Debug QA report
# ============================================================

def count_null_features(feat: FeatureDict) -> int:
    return sum(1 for v in feat.values() if v is None)

def qa_report(export: Dict[str, Any], max_lines: int = 200) -> str:
    lines: List[str] = []
    lines.append("QA report for manifest_with_features.json")
    g = export.get("global", {})
    gf = g.get("features", {})
    lines.append(f"Global median_year: {g.get('median_year')}")
    lines.append("Global features:")
    for k in ["danceability","energy","speechiness","acousticness","valence","tempo_bpm","tempo_norm","popularity","instrumentalness"]:
        lines.append(f"  {k}: {gf.get(k)}")

    def walk(name: str, node: ManifestNode, depth: int = 0):
        indent = "  " * depth
        feat = cast(FeatureDict, node.get("features") or {})
        nulls = count_null_features(feat)
        year = node.get("median_year")
        seeds = node.get("seeds", [])
        lines.append(f"{indent}- {name}: seeds={len(seeds)} null_features={nulls} median_year={year}")
        if depth < 6:
            subs = node.get("subgenres")
            if isinstance(subs, dict):
                for child_name, child in subs.items():
                    walk(child_name, child, depth+1)

    genres = export.get("genres", {})
    for name, node in genres.items():
        walk(name, node, 0)

    return "\n".join(lines[:max_lines])

# ============================================================
# IO helpers
# ============================================================

def _load_json(path: str) -> Any:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

def _save_json(path: str, data: Any) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

# ============================================================
# Main
# ============================================================
def main(argv: List[str]) -> int:
    try:
        print(f"Args: {argv}", file=sys.stderr)
        
        if len(argv) < 4:
            print("Usage:", file=sys.stderr)
            print("  python extract_genre_seeds_patched.py <manifest_input.json> <prepped_results.json> <output.json>", file=sys.stderr)
            return 2

        manifest_path = argv[1]
        results_path = argv[2]
        out_path = argv[3]
        
        print(f"Loading manifest: {manifest_path}", file=sys.stderr)
        manifest_root: ManifestTree = _load_json(manifest_path)
        print(f"Loaded {len(manifest_root)} top-level genres", file=sys.stderr)
        
        print(f"Loading results: {results_path}", file=sys.stderr)
        results: ResultBucket = _load_json(results_path)
        print(f"Loaded {len(results)} result pools", file=sys.stderr)

        print("Building manifest tree...", file=sys.stderr)
        export = buildManifestTree(
            manifest_root,
            results,
            dataset_id="prepped_v7_2025-11-04",
            sample_size_per_genre=SAMPLE_SIZE_PER_GENRE_DEFAULT
        )
        
        print(f"Built tree with {len(export.get('genres', {}))} genres", file=sys.stderr)
        print(f"Writing to: {out_path}", file=sys.stderr)
        _save_json(out_path, export)
        
        print("QA Report:", file=sys.stderr)
        print(qa_report(export, max_lines=50))

        return 0
        
    except Exception as e:
        print(f"ERROR: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        return 1

# def main(argv: List[str]) -> int:
#     # CLI:
#     # python extract_genre_seeds_patched.py manifest_input.json prepped_results.json manifest_with_features.json
#     if len(argv) < 4:
#         print("Usage:", file=sys.stderr)
#         print("  python extract_genre_seeds_patched.py <manifest_input.json> <prepped_results.json> <output.json>", file=sys.stderr)
#         return 2

#     manifest_path = argv[1]
#     results_path = argv[2]
#     out_path = argv[3]

#     manifest_root: ManifestTree = _load_json(manifest_path)
#     results: ResultBucket = _load_json(results_path)

#     export = buildManifestTree(
#         manifest_root,
#         results,
#         dataset_id="prepped_v7_2025-11-04",
#         sample_size_per_genre=SAMPLE_SIZE_PER_GENRE_DEFAULT
#     )

#     _save_json(out_path, export)

#     # Print a short QA summary to stdout
#     print(qa_report(export, max_lines=300))

#     return 0

if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
