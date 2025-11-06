import json
import re
import math
from collections import defaultdict, Counter
from typing import Any, Dict, Tuple, List, Set
from datetime import datetime, timezone
import random
random.seed(42)

# -------- Load dataset --------
with open('server/data/prepped.json', 'r', encoding='utf-8') as f:
    tracks = json.load(f)

print(f"Loaded {len(tracks)} tracks\n")

# -------- Helpers --------
def generate_filename(artist, track_name):
    safe_artist = (artist or 'unknown').lower().replace(' ', '-')
    safe_artist = re.sub(r'[^a-z0-9-]', '', safe_artist)
    safe_artist = re.sub(r'-+', '-', safe_artist).strip('-')
    safe_name = (track_name or 'unknown').lower().replace(' ', '-')
    safe_name = re.sub(r'[^a-z0-9-]', '', safe_name)
    safe_name = re.sub(r'-+', '-', safe_name).strip('-')
    return f"{safe_artist}-{safe_name}.json"

def clamp(x, lo, hi):
    return lo if x < lo else hi if x > hi else x

MIN_BPM = 70.0
MAX_BPM = 200.0
GLOBAL_UNIQUENESS = True
used_track_ids_global: Set[str] = set()
used_artists_global: Set[str] = set()

def tempo_to_norm(bpm: float) -> float:
    return clamp((bpm - MIN_BPM) / (MAX_BPM - MIN_BPM), 0.0, 1.0)

def median_sorted(vals):
    n = len(vals)
    if n == 0:
        raise ValueError("median of empty list")
    mid = n // 2
    if n % 2 == 1:
        return float(vals[mid])
    return float(vals[mid - 1])

def median(vals):
    return median_sorted(sorted(vals))

def linear_quantile(vals, q):
    xs = sorted(vals)
    n = len(xs)
    if n == 0:
        return None
    if n == 1:
        return float(xs[0])
    h = (n - 1) * q
    i = int(math.floor(h))
    frac = h - i
    if i + 1 < n:
        return float(xs[i] * (1.0 - frac) + xs[i + 1] * frac)
    else:
        return float(xs[i])

def mean(vals):
    return float(sum(vals) / len(vals)) if vals else float("nan")

def stddev(vals):
    n = len(vals)
    if n <= 1:
        return 0.0
    m = mean(vals)
    return math.sqrt(sum((x - m) ** 2 for x in vals) / (n - 1))

def sround(x, nd=2):
    try:
        if x is None:
            return None
        return round(float(x), nd)
    except Exception:
        return None

def norm_tags(tags):
    out = []
    for g in tags or []:
        if not g:
            continue
        out.append(g.lower().strip())
    return out

# -------- Explicit denials for the edge cases you flagged --------
TRACK_DENY_URIS = {
    "spotify:track:7CZyCXKG6d5ALeq41sLzbw",  # Post Malone collab
    "spotify:track:4BggEwLhGfrbrl7JBhC8EC",  # Crazy Town - Butterfly
    "spotify:track:5iSEsR6NKjlC9SrIJkyL3k",  # Kid Cudi - Pursuit of Happiness (Nightmare)
}

# -------- Final GENRE_TREE (Drone removed) --------
GENRE_TREE = {
    "rock": {
        "_seeds": "rock",
        "subgenres": {
            "metal": {
                "_seeds": "metal",
                "subgenres": {
                    "thrash metal": {"_seeds": "thrash metal"},
                    "doom & black metal": {"_seeds": "doom & black metal"},
                    "sludge metal": {"_seeds": "sludge metal"},
                    "death metal": {"_seeds": "death metal"},
                    "progressive metal": {"_seeds": "progressive metal"},
                    "nu metal": {"_seeds": "nu metal"}
                }
            },
            "punk": {
                "_seeds": "punk",
                "subgenres": {
                    "hardcore": {"_seeds": "hardcore"},
                    "post-punk": {"_seeds": "post-punk"},
                    "emo": {"_seeds": "emo"}
                }
            },
            "alternative rock": {"_seeds": "alternative rock"},
            "indie rock": {"_seeds": "indie rock"},
            "shoegaze": {"_seeds": "shoegaze"},
            "grunge": {"_seeds": "grunge"},
            "post-rock": {"_seeds": "post-rock"},
            "classic rock": {"_seeds": "classic rock"},
            "garage rock": {"_seeds": "garage rock"},
            "psychedelic rock": {"_seeds": "psychedelic rock"},
            "hard rock": {"_seeds": "hard rock"}
        }
    },

    "electronic": {
        "_seeds": "electronic",
        "subgenres": {
            "house": {
                "_seeds": "house",
                "subgenres": {
                    "deep house": {"_seeds": "deep house"},
                    "tech house": {"_seeds": "tech house"},
                    "progressive house": {"_seeds": "progressive house"},
                    "acid house": {"_seeds": "acid house"}
                }
            },
            "techno": { "_seeds": "techno" },
            "trance": { "_seeds": "trance" },
            "drum and bass": { "_seeds": "drum and bass" },
            "jungle": { "_seeds": "jungle" },
            "breakbeat": { "_seeds": "breakbeat" },
            "uk garage": { "_seeds": "uk garage" },
            "dubstep": { "_seeds": "dubstep" },
            "synthwave": { "_seeds": "synthwave" },
            "ambient": { "_seeds": "ambient" }
        }
    },

    "hip hop": {
        "_seeds": "hip hop",
        "subgenres": {
            "rap": {"_seeds": "rap"},
            "trap": {"_seeds": "trap"},
            "drill": {"_seeds": "drill"},
            "gangsta rap": {"_seeds": "gangsta rap"},
            "boom bap": {"_seeds": "boom bap"},
            "east coast hip hop": {"_seeds": "east coast hip hop"},
            "west coast rap": {"_seeds": "west coast rap"},
            "southern hip hop": {"_seeds": "southern hip hop"},
            "conscious hip hop": {"_seeds": "conscious hip hop"},
            "alternative hip hop": {"_seeds": "alternative hip hop"},
            "underground hip hop": {"_seeds": "underground hip hop"},
            "phonk": {"_seeds": "phonk"},
            "cloud rap": {"_seeds": "cloud rap"}
        }
    },

    "r&b / soul / funk": {
        "_seeds": "r&b / soul / funk",
        "subgenres": {
            "r&b": {
                "_seeds": "r&b",
                "subgenres": {
                    "contemporary r&b": {"_seeds": "contemporary r&b"},
                    "quiet storm": {"_seeds": "quiet storm"}
                }
            },
            "soul": {
                "_seeds": "soul",
                "subgenres": {
                    "motown": {"_seeds": "motown"},
                    "disco": {"_seeds": "disco"},
                    "neo soul": {"_seeds": "neo soul"}
                }
            },
            "funk": {
                "_seeds": "funk",
                "subgenres": {
                    "funk rock": {"_seeds": "funk rock"},
                    "boogie": {"_seeds": "boogie"}
                }
            }
        }
    },

    "jazz": {
        "_seeds": "jazz",
        "subgenres": {
            "bebop": {"_seeds": "bebop"},
            "cool jazz": {"_seeds": "cool jazz"},
            "hard bop": {"_seeds": "hard bop"},
            "swing": {"_seeds": "swing"},
            "jazz fusion": {"_seeds": "jazz fusion"},
            "smooth jazz": {"_seeds": "smooth jazz"},
            "vocal jazz": {"_seeds": "vocal jazz"},
            "nu jazz": {"_seeds": "nu jazz"},
            "avant-garde jazz": {"_seeds": "avant-garde jazz"}
        }
    },

    "country": {
        "_seeds": "country",
        "subgenres": {
            "classic country": {"_seeds": "classic country"},
            "outlaw country": {"_seeds": "outlaw country"},
            "bluegrass": {"_seeds": "bluegrass"},
            "country rock": {"_seeds": "country rock"},
            "southern rock": {"_seeds": "southern rock"},
            "roots rock": {"_seeds": "roots rock"},
            "americana folk": {"_seeds": "americana folk"}
        }
    },

    "latin": {
        "_seeds": "latin",
        "subgenres": {
            "reggaeton": {"_seeds": "reggaeton"},
            "latin pop": {"_seeds": "latin pop"},
            "salsa": {"_seeds": "salsa"},
            "bachata": {"_seeds": "bachata"},
            "cumbia": {"_seeds": "cumbia"},
            "merengue": {"_seeds": "merengue"},
            "tropical": {"_seeds": "tropical"},
            "mambo": {"_seeds": "mambo"},
            "bossa nova": {"_seeds": "bossa nova"}
        }
    },

    "reggae": {
        "_seeds": "reggae",
        "subgenres": {
            "dub": {"_seeds": "dub"},
            "ska": {"_seeds": "ska"},
            "dancehall": {"_seeds": "dancehall"},
            "soca": {"_seeds": "soca"},
            "afrobeat": {"_seeds": "afrobeat"},
            "afropop": {"_seeds": "afropop"},
            "amapiano": {"_seeds": "amapiano"}
        }
    },

    "classical": {
        "_seeds": "classical",
        "subgenres": {
            "baroque": {"_seeds": "baroque"},
            "romantic": {"_seeds": "romantic"},
            "modern classical": {"_seeds": "modern classical"},
            "new age": {"_seeds": "new age"},
            "minimalism": {"_seeds": "minimalism"}
        }
    }
}

# -------- Exclusions and rules (tighteners) --------
EXCLUSIONS = {
    "punk": ["pop punk", "dance", "edm", "electro", "big room"],
    "metal": ["funk metal"],
    "electro": ["electropop", "pop"],
    "rock": ["pop rock", "soft rock"],
    "folk": ["indie folk"],
    "funk": ["funk carioca", "baile funk", "brazilian funk"],
}

GENRE_RULES: Dict[str, Dict[str, Any]] = {
    "metal": {
        "require_artist_genres_any": [
            "metal","heavy metal","hard rock","classic metal","new wave of british heavy metal",
            "speed metal","power metal","glam metal","shock rock"
        ],
        "deny_artist_genres_any": ["hip hop","rap","pop rap","trap","dance pop","electropop","synthpop"]
    },
    "thrash metal": {"require_artist_genres_any": ["thrash metal"]},
    "doom & black metal": {"require_artist_genres_any": ["doom metal", "black metal"]},
    "sludge metal": {"require_artist_genres_any": ["sludge metal"]},
    "death metal": {"require_artist_genres_any": ["death metal"]},
    "progressive metal": {"require_artist_genres_any": ["progressive metal"]},
    "nu metal": {
        "require_artist_genres_any": ["nu metal","rap metal","alternative metal","industrial metal"],
        "deny_artist_genres_any": ["rap rock","pop rock","alternative rock","dance pop","pop","hip hop","pop rap"]
    },
    "indie rock": {
        "require_artist_genres_any": [
            "indie rock","modern rock","garage rock","lo-fi indie","indie garage rock","alternative rock"
        ],
        "deny_artist_genres_any": ["hip hop","rap","pop rap","trap","cloud rap","alternative hip hop"]
    },
    "punk": {
        "require_artist_genres_any": ["punk", "punk rock"],
        "deny_artist_genres_any": ["happy hardcore","hardcore techno","gabber","edm","dance pop","pop","emo","pop punk"],
        "popularity_max": 80
    },
    "hardcore": {
        "require_artist_genres_any": ["hardcore punk","nyhc","post-hardcore","powerviolence","d-beat","youth crew"],
        "deny_artist_genres_any": ["happy hardcore","hardcore techno","gabber","edm","dance","dance pop","pop","pop punk","emo","metalcore","easycore"],
        "popularity_max": 70
    },
    "post-punk": {
        "require_artist_genres_any": ["post-punk","post punk"],
        "deny_artist_genres_any": ["classic rock","soft rock","dance pop","pop"]
    },
    "emo": {
        "require_artist_genres_any": ["emo","screamo","midwest emo","post-hardcore"],
        "deny_artist_genres_any": ["rap","hip hop","trap","dance pop","pop"]
    },
    "alternative rock": {
        "require_artist_genres_any": ["alternative rock","modern rock","post-grunge","alternative metal","grunge"],
        "deny_artist_genres_any": ["dance pop","electropop","synthpop","pop"]
    },
    "shoegaze": {
        "require_artist_genres_any": ["shoegaze","nu gaze","dream pop","space rock"],
        "deny_artist_genres_any": ["soft rock","adult standards","dance pop","pop"]
    },
    "classic rock": {
        "require_artist_genres_any": ["classic rock", "album rock"],
        "deny_artist_genres_any": ["dance pop","electropop","synthpop","pop"],
        "max_year": 1995
    },
    "psychedelic rock": {
        "require_artist_genres_any": ["psychedelic rock","acid rock","psych rock"],
        "deny_artist_genres_any": ["dance pop","pop","adult standards"]
    },
    "hard rock": {
        "require_artist_genres_any": ["hard rock","arena rock","glam metal","classic rock"],
        "deny_artist_genres_any": ["soft rock","adult standards","dance pop","pop"]
    },
    "deep house": {"require_artist_genres_any": ["deep house","house"]},
    "tech house": {"require_artist_genres_any": ["tech house","house"]},
    "progressive house": {"require_artist_genres_any": ["progressive house","house"]},
    "acid house": {
        "require_artist_genres_any": ["acid house","house"],
        "deny_artist_genres_any": ["jazz","soul","r&b","neo soul"],
        "min_year": 1987
    },
    "rap": {
        "require_artist_genres_any": ["rap","hip hop","hip-hop"],
        "deny_artist_genres_any": ["dance pop","pop","electropop","synthpop","latin pop"]
    },
    "underground hip hop": {
        "require_artist_genres_any": ["underground hip hop","boom bap","abstract hip hop","backpack rap"],
        "deny_artist_genres_any": ["dance pop","pop","trap","pop rap","electropop","synthpop"],
        "popularity_max": 65
    },
    "east coast hip hop": {
        "require_artist_genres_any": ["east coast hip hop","new york drill","boom bap"],
        "deny_artist_genres_any": ["dance pop","pop"]
    },
    "trap": {
        "require_artist_genres_any": ["trap","southern hip hop","atl hip hop"],
        "deny_artist_genres_any": ["dance pop","pop"]
    },
    "drill": {
        "require_artist_genres_any": ["drill","uk drill","new york drill"],
        "deny_artist_genres_any": ["dance pop","pop"]
    },
    "funk": {
        "require_artist_genres_any": ["funk","p-funk","pfunk"],
        "deny_artist_genres_any": ["motown","northern soul","soul","disco","new jack swing","hip hop","rap","funk carioca","baile funk","brazilian funk"],
        "popularity_max": 80
    },
    "funk rock": {
        "require_artist_genres_any": ["funk rock","alternative metal","rap rock"],
        "deny_artist_genres_any": ["new jack swing","dance pop","pop"]
    },
    "boogie": {
        "require_artist_genres_any": ["boogie","post-disco"],
        "deny_artist_genres_any": ["soundtrack","broadway","film soundtrack","show tunes"],
        "min_year": 1978, "max_year": 1987
    },
    "jazz fusion": {
        "require_artist_genres_any": ["jazz fusion","fusion","jazz funk"],
        "deny_artist_genres_any": ["bachata","latin pop","reggaeton","dance pop","pop"]
    },
    "bebop": { "require_artist_genres_any": ["bebop", "hard bop"], "max_year": 1965 },
    "cool jazz": { "require_artist_genres_any": ["cool jazz"], "max_year": 1975 },
    "swing": {
        "require_artist_genres_any": ["swing","big band","big band jazz"],
        "deny_artist_genres_any": ["hip hop","rap","trap","drill"],
        "max_year": 1965
    },
    "dancehall": {
        "require_artist_genres_any": ["dancehall"],
        "deny_artist_genres_any": ["reggaeton","latin pop","pop","dance pop"]
    },
}

def genre_match(search_genre: str, track_genres: List[str]) -> bool:
    if search_genre in EXCLUSIONS:
        for exclusion in EXCLUSIONS[search_genre]:
            if any(exclusion.lower() in g.lower() for g in track_genres):
                return False
    sg = search_genre.lower().strip()
    pat = re.compile(rf"\b{re.escape(sg)}\b")
    for tg in track_genres:
        t = tg.lower().strip()
        if t == sg:
            return True
        if pat.search(t):
            return True
    return False

def passes_rules(target_genre: str, track: Dict[str, Any]) -> bool:
    rules = GENRE_RULES.get(target_genre.lower())
    if not rules:
        return True

    a_gen = [g.lower() for g in (track.get("artist_genres") or track.get("genres") or [])]

    req = rules.get("require_artist_genres_any") or []
    if req and not any(any(r in g for g in a_gen) for r in req):
        return False

    deny = rules.get("deny_artist_genres_any") or []
    if deny and any(any(d in g for g in a_gen) for d in deny):
        return False

    y = track.get("release_year")
    try:
        y = int(y) if y is not None else None
    except:
        y = None

    min_year = rules.get("min_year")
    if min_year is not None and y is not None and y < min_year:
        return False

    max_year = rules.get("max_year")
    if max_year is not None and y is not None and y > max_year:
        return False

    pop = float(track.get("popularity", 0))
    popmin = rules.get("popularity_min")
    if popmin is not None and pop < float(popmin):
        return False
    popmax = rules.get("popularity_max")
    if popmax is not None and pop > float(popmax):
        return False

    return True

def seed_confidence(target_genre, track):
    conf = 1.0
    reasons = []
    rules = GENRE_RULES.get(target_genre.lower())
    a_gen = [g.lower() for g in (track.get("artist_genres") or track.get("genres") or [])]
    if rules:
        req = rules.get("require_artist_genres_any") or []
        if req and any(any(r in g for g in a_gen) for r in req):
            conf += 0.15
        elif req:
            conf -= 0.45
            reasons.append(f"missing-required-artist-genre:{req}")
        deny = rules.get("deny_artist_genres_any") or []
        if deny and any(any(d in g for g in a_gen) for d in deny):
            conf -= 0.5
            reasons.append(f"denied-artist-genre:{deny}")
        min_year = rules.get("min_year")
        if min_year is not None and isinstance(min_year, int):
            if track.get("release_year") and int(track["release_year"]) < min_year:
                conf -= 0.25
                reasons.append(f"year<{min_year}")
        max_year = rules.get("max_year")
        if max_year is not None and isinstance(max_year, int):
            if track.get("release_year") and int(track["release_year"]) > max_year:
                conf -= 0.25
                reasons.append(f"year>{max_year}")
    if not a_gen:
        conf -= 0.1
        reasons.append("no-artist-genres")
    return max(0.0, conf), reasons

# -------- Gather playable genres from tree --------
def gather_playable_genres(tree):
    genres = []
    def walk(node):
        if not isinstance(node, dict):
            return
        if "_seeds" in node and isinstance(node["_seeds"], str):
            genres.append(node["_seeds"])
        for v in node.values():
            if isinstance(v, dict):
                walk(v)
            elif isinstance(v, list):
                for it in v:
                    walk(it)
    walk(tree)
    seen = set(); ordered = []
    for g in genres:
        if g not in seen:
            seen.add(g); ordered.append(g)
    return ordered

PLAYABLE_GENRES = gather_playable_genres(GENRE_TREE)

def build_parent_maps(tree: Dict[str, Any]) -> Tuple[Dict[str, str], Dict[str, Set[str]]]:
    genre_to_parent: Dict[str, str] = {}
    parent_to_desc: Dict[str, Set[str]] = {}
    def walk(node: Dict[str, Any], parent_seed: str = ""):
        this_seed = node.get("_seeds") if isinstance(node.get("_seeds"), str) else None
        subs = node.get("subgenres")
        if isinstance(subs, dict):
            parent_label = this_seed or parent_seed
            if parent_label and parent_label not in parent_to_desc:
                parent_to_desc[parent_label] = set()
            for _, child in subs.items():
                if isinstance(child, dict):
                    child_seed = child.get("_seeds") if isinstance(child.get("_seeds"), str) else None
                    if child_seed:
                        genre_to_parent[child_seed] = parent_label or ""
                        if parent_label:
                            parent_to_desc[parent_label].add(child_seed)
                    walk(child, parent_label)
    walk(tree)
    return genre_to_parent, parent_to_desc

GENRE_TO_PARENT, PARENT_TO_DESC = build_parent_maps(GENRE_TREE)

# -------- Seed selection --------
results: Dict[str, List[Dict[str, Any]]] = {}
low_confidence = []
exclusion_counts = Counter()

used_track_ids_by_parent: Dict[str, Set[str]] = defaultdict(set)
used_artists_by_parent: Dict[str, Set[str]] = defaultdict(set)
ARTIST_FAMILY_CAP = 1

def proto_score(target_genre: str, t: Dict[str, Any]) -> float:
    tags = norm_tags(t.get("artist_genres") or t.get("genres"))
    target = target_genre.lower()
    exact = 1.0 if any(g == target for g in tags) else 0.0
    boundary = 1.0 if any(re.search(rf"\b{re.escape(target)}\b", g) for g in tags) else 0.0
    pop = float(t.get("popularity", 0)) / 100.0
    bad_tokens = {"dance pop","pop","electropop","synthpop","soundtrack","broadway","film soundtrack","show tunes"}
    has_bad = any(any(bt in g for bt in bad_tokens) for g in tags)
    pop_penalty = 0.25 if pop >= 0.85 else 0.0
    contam_penalty = 0.30 if has_bad else 0.0
    very_popular_artist = float(t.get("popularity", 0)) >= 90
    artist_penalty = 0.15 if very_popular_artist else 0.0
    jitter = random.random() * 0.03
    return (2.5 * exact) + (1.5 * boundary) + (0.5 * pop) - pop_penalty - contam_penalty - artist_penalty + jitter

for genre in PLAYABLE_GENRES:
    parent = GENRE_TO_PARENT.get(genre, "")

    candidates: List[Dict[str, Any]] = []
    for track in tracks:
        tid = track.get("uri") or track.get("id")
        if tid in TRACK_DENY_URIS:
            continue
        track_genres = norm_tags(track.get('artist_genres') or track.get('genres'))
        if not track_genres:
            continue
        if not genre_match(genre, track_genres):
            continue
        if not passes_rules(genre, track):
            continue
        if parent and tid and tid in used_track_ids_by_parent[parent]:
            continue
        candidates.append(track)

    if not candidates:
        results[genre] = []
        continue

    seen_ids: Set[str] = set()
    seen_artists: Set[str] = set()
    unique_candidates: List[Dict[str, Any]] = []

    for t in candidates:
        tid = t.get("id") or t.get("uri")
        artist = (t.get("artists") or [""])[0]
        if not tid or not artist:
            continue
        if GLOBAL_UNIQUENESS and (tid in used_track_ids_global or artist in used_artists_global):
            continue
        if tid in seen_ids or artist in seen_artists:
            continue
        seen_ids.add(tid)
        seen_artists.add(artist)
        unique_candidates.append(t)

    if not unique_candidates:
        results[genre] = []
        continue

    unique_candidates.sort(key=lambda t_: proto_score(genre, t_), reverse=True)

    top_k: List[Dict[str, Any]] = []
    family_artists = used_artists_by_parent[parent] if parent else set()
    for t in unique_candidates:
        if len(top_k) >= 4:
            break
        artist = (t.get('artists') or [''])[0]
        if parent and (artist in family_artists):
            continue
        top_k.append(t)
        tid = t.get("uri") or t.get("id")
        if parent:
            family_artists.add(artist)
            if tid:
                used_track_ids_by_parent[parent].add(tid)
        if GLOBAL_UNIQUENESS:
            if tid:
                used_track_ids_global.add(tid)
            used_artists_global.add(artist)

    results[genre] = top_k

    for t in top_k:
        conf, reasons = seed_confidence(genre, t)
        if conf < 0.7:
            low_confidence.append({
                "genre": genre,
                "track": t.get("name"),
                "artist": (t.get("artists") or ["Unknown"])[0],
                "uri": t.get("uri"),
                "confidence": sround(conf, 2),
                "reasons": reasons,
                "artist_genres": (t.get("artist_genres") or t.get("genres") or [])[:8],
            })
        for r in reasons:
            exclusion_counts[(genre, r)] += 1

# -------- Feature computation helpers --------
FEATURE_FIELDS = ["danceability","energy","speechiness","acousticness","valence","popularity","instrumentalness"]

def compute_features_from_tracks(seed_tracks: List[Dict[str, Any]]):
    fvals = defaultdict(list)
    years = []
    tempos = []
    for t in seed_tracks:
        for f in FEATURE_FIELDS:
            v = t.get(f)
            if v is not None:
                try: fvals[f].append(float(v))
                except: pass
        bpm = t.get("tempo")
        if bpm is not None:
            try: tempos.append(float(bpm))
            except: pass
        y = t.get("release_year")
        try:
            if y is not None: years.append(int(y))
        except: pass
    feat = {}
    for k, vals in fvals.items():
        if vals: feat[k] = sround(median(vals), 2)
    if tempos:
        med_bpm = median(tempos)
        feat["tempo_bpm"] = sround(med_bpm, 2)
        feat["tempo_norm"] = sround(tempo_to_norm(med_bpm), 2)
    med_year = None
    if years:
        years.sort()
        med_year = int(median_sorted(years))
    return feat, med_year

def aggregate_features_from_children(children_nodes: Dict[str, Any]):
    agg_lists = defaultdict(list)
    years = []
    for child in children_nodes.values():
        feat = child.get("features") or {}
        for k in list(feat.keys()):
            agg_lists[k].append(feat[k])
        if "median_year" in child and child["median_year"] is not None:
            years.append(child["median_year"])
    out_feat = {}
    for k, vals in agg_lists.items():
        num_vals = [v for v in vals if v is not None]
        if num_vals:
            out_feat[k] = sround(median(num_vals), 2)
    med_year = None
    if years:
        years.sort()
        med_year = int(median_sorted(years))
    return out_feat, med_year

# -------- Build manifest with per-genre features everywhere --------
def build_manifest(tree: Dict[str, Any]) -> Dict[str, Any]:
    result: Dict[str, Any] = {}

    # process children first so we can backfill parent from children if needed
    sub = tree.get("subgenres")
    built_sub: Dict[str, Any] = {}
    if isinstance(sub, dict):
        for child_name, child_node in sub.items():
            if isinstance(child_node, dict):
                child_built = build_manifest(child_node)
                built_sub[child_name] = child_built

    # attach seeds for this node
    seeds_key = tree.get("_seeds")
    seeds_payload = []
    node_features = {}
    node_median_year = None

    if isinstance(seeds_key, str):
        genre_name = seeds_key
        seeds = results.get(genre_name, [])
        if seeds:
            for t in seeds:
                artist_name = (t.get("artists") or ["Unknown"])[0]
                seeds_payload.append({
                    "uri": t.get("uri"),
                    "name": t.get("name"),
                    "artist": artist_name,
                    "popularity": t.get("popularity", 0),
                    "filename": generate_filename(artist_name, t.get("name")),
                })
            node_features, node_median_year = compute_features_from_tracks(seeds)

    # if no seeds_features, backfill from children
    if not node_features and built_sub:
        child_feat, child_year = aggregate_features_from_children(built_sub)
        if child_feat:
            node_features = child_feat
        if child_year is not None:
            node_median_year = child_year

    # ensure the features object includes both tempo values, and all fields exist
    if node_features:
        for k in FEATURE_FIELDS:
            node_features.setdefault(k, None)
        node_features.setdefault("tempo_bpm", None)
        node_features.setdefault("tempo_norm", None)

    # write node content
    if seeds_payload:
        result["seeds"] = seeds_payload
    if node_features:
        result["features"] = node_features
    if node_median_year is not None:
        result["median_year"] = node_median_year

    if built_sub:
        result["subgenres"] = built_sub

    return result

manifest: Dict[str, Any] = build_manifest(GENRE_TREE)

# -------- Global stats across the union of all selected seed tracks --------
seed_pool: Dict[str, Dict[str, Any]] = {}
for g, lst in results.items():
    for t in lst:
        key = t.get("uri") or t.get("id")
        if key is not None and key not in seed_pool:
            seed_pool[key] = t

feature_set = ["danceability","energy","speechiness","acousticness","valence","tempo_norm","popularity","instrumentalness"]
accum = {k: [] for k in feature_set}
for t in seed_pool.values():
    tn = None
    if t.get("tempo") is not None:
        try: tn = tempo_to_norm(float(t["tempo"]))
        except: tn = None
    mapping = {
        "danceability": t.get("danceability"),
        "energy": t.get("energy"),
        "speechiness": t.get("speechiness"),
        "acousticness": t.get("acousticness"),
        "valence": t.get("valence"),
        "tempo_norm": tn,
        "popularity": t.get("popularity"),
        "instrumentalness": t.get("instrumentalness"),
    }
    for k, v in mapping.items():
        try:
            if v is not None: accum[k].append(float(v))
        except: pass

means = {}; stddevs = {}; quantiles = {}
for k, vals in accum.items():
    if vals:
        means[k] = sround(mean(vals), 2)
        stddevs[k] = sround(stddev(vals), 2)
        q10 = linear_quantile(vals, 0.10)
        q50 = linear_quantile(vals, 0.50)
        q90 = linear_quantile(vals, 0.90)
        quantiles[k] = {"p10": sround(q10, 2), "p50": sround(q50, 2), "p90": sround(q90, 2)}
    else:
        means[k] = None; stddevs[k] = None
        quantiles[k] = {"p10": None, "p50": None, "p90": None}

manifest["global"] = {
    "feature_set": feature_set,
    "tempo_norm": {"min_bpm": int(MIN_BPM), "max_bpm": int(MAX_BPM)},
    "means": means,
    "stddevs": stddevs,
    "quantiles": quantiles,
    # display defaults for consistent client rendering
    "display": {
        "feature_angles": ["danceability","energy","speechiness","acousticness","valence","tempo_norm","popularity","instrumentalness"],
        "projection_scale": 180,
        "exaggeration_default": 1.2,
        "speechiness_contrast_gamma": 1.3
    }
}

# -------- Build metadata --------
manifest["build"] = {
    "schema_version": "1",
    "dataset_id": "prepped_v7_2025-11-04",
    "track_count": len(tracks),
    "sample_size_per_genre": 4,
    "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
}

# -------- Save manifest --------
with open('genre_constellation_manifest.json', 'w', encoding='utf-8') as f:
    json.dump(manifest, f, indent=2, ensure_ascii=False)

print("=" * 60)
print("SAVED: genre_constellation_manifest.json")
print("=" * 60)

# -------- Reporting --------
print("\n" + "=" * 60)
print("REPORT:")
print("=" * 60)
total_found = 0
issues = []

for genre in PLAYABLE_GENRES:
    count = len(results.get(genre, []))
    total_found += count
    status = "✓" if count == 4 else "⚠️" if count > 0 else "✗"
    if count > 0:
        avg_pop = sum(t.get('popularity', 0) for t in results[genre]) / count
        print(f"{status} {genre:<30} {count}/4 tracks (avg pop: {avg_pop:.0f})")
    if 0 < count < 4:
        issues.append((genre, count))

print(f"\nTotal seed selections: {total_found}")
unique_artists = set()
for lst in results.values():
    for t in lst:
        a = (t.get('artists') or [''])[0]
        if a:
            unique_artists.add(a)
print(f"Total unique artists across all seeds: {len(unique_artists)}")

if issues:
    print(f"\n⚠️  GENRES WITH LOW COVERAGE:")
    for genre, count in issues:
        print(f"   {genre}: only {count} track(s)")

print("\n" + "=" * 60)
print("URIS FOR BATCH EXPORT:")
print("=" * 60)
for genre in PLAYABLE_GENRES:
    if results.get(genre):
        print(f"\n# {genre.upper()}")
        for track in results[genre]:
            artist = (track.get('artists') or ['Unknown'])[0]
            print(f"{track.get('uri')}  // {artist} — {track.get('name')}")

if low_confidence:
    print("\n" + "=" * 60)
    print(f"LOW-CONFIDENCE SEEDS ({len(low_confidence)}) — review these:")
    print("=" * 60)
    for r in low_confidence[:20]:
        print(f"- [{r['genre']}] {r['artist']} — {r['track']}  ({r['uri']})  conf={r['confidence']} reasons={r['reasons']}")
    if len(low_confidence) > 20:
        print(f"... +{len(low_confidence)-20} more")
    if exclusion_counts:
        print("Top concern reasons:")
        for (g, reason), cnt in exclusion_counts.most_common(10):
            print(f" - {g}: {reason} x{cnt}")
