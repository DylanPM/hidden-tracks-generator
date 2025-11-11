"""
Genre Constellation Manifest Generator

Selects seed tracks for each genre, computes features, and exports a manifest
for the music guessing game level select screen.
"""

import json
import re
import math
from collections import defaultdict, Counter
from typing import Any, Dict, Tuple, List, Set
from datetime import datetime, timezone
import random
import time
import os

# ============================================================================
# CONFIGURATION
# ============================================================================

CONFIG = {
    # File paths
    'data_file': 'server/data/prepped.json',
    'output_file': 'genre_constellation_manifest.json',
    'dataset_id': 'prepped_v7_2025-11-04',

    # Seed selection
    'seeds_per_genre': 5,
    'random_seed': 42,

    # Tempo normalization
    'min_bpm': 70.0,
    'max_bpm': 200.0,

    # Scoring weights
    'score_exact_match': 2.5,
    'score_whitelist_bonus': 1.5,
    'score_boost_bonus': 0.8,
    'score_contamination_penalty': -0.3,
    'score_random_noise': 0.05,

    # Popularity scoring (plateau function)
    'pop_center': 69.0,
    'pop_plateau': 5.0,
    'pop_width': 55.0,
    'pop_weight': 0.5,
}

random.seed(CONFIG['random_seed'])

print("=" * 60, flush=True)
print("Starting Genre Constellation Manifest Generator", flush=True)
print("=" * 60, flush=True)

DATA_FILE = CONFIG['data_file']
if not os.path.exists(DATA_FILE):
    print(f"❌ ERROR: Input file not found: {DATA_FILE}", flush=True)
    exit(1)

print(f"✓ Found input file: {DATA_FILE}", flush=True)
file_size_mb = os.path.getsize(DATA_FILE) / (1024 * 1024)
print(f"✓ File size: {file_size_mb:.1f} MB", flush=True)

start_time = time.time()
print(f"\nLoading dataset...", flush=True)
with open(DATA_FILE, 'r', encoding='utf-8') as f:
    tracks = json.load(f)

    # --- Remove any tracks with 'feat.', 'ft.', 'featuring', or 'with' in the name ---
def strip_features(text: str) -> str:
    """Remove all 'feat.', 'ft.', 'featuring', and similar markers."""
    if not text:
        return ""
    # Removes both parentheses and inline usage
    text = re.sub(r'\s*\(?(?:feat\.?|ft\.?|featuring|with)\s+[^)]+?\)?', '', text, flags=re.IGNORECASE)
    return text.strip()

# --- Clean and filter all tracks BEFORE genre grouping ---
cleaned_tracks = []
for t in tracks:
    name = t.get("name", "") or ""
    # Strict skip: drop any track that includes a feature indicator
    if re.search(r'\b(feat\.?|ft\.?|featuring|with)\b', name, flags=re.IGNORECASE):
        continue

    # Clean up artist and name text
    t["name"] = strip_features(name)
    artists = t.get("artists") or []
    t["artists"] = [strip_features(a) for a in artists]
    cleaned_tracks.append(t)

tracks = cleaned_tracks
    
load_time = time.time() - start_time
print(f"✓ Loaded {len(tracks)} tracks in {load_time:.1f}s\n", flush=True)

# -------- Helpers --------
def generate_filename(artist, track_name):
    artist = strip_features(artist)
    track_name = strip_features(track_name)

    safe_artist = (artist or 'unknown').lower().replace(' ', '-')
    safe_artist = re.sub(r'[^a-z0-9-]', '', safe_artist)
    safe_artist = re.sub(r'-+', '-', safe_artist).strip('-')
    
    safe_name = (track_name or 'unknown').lower().replace(' ', '-')
    safe_name = re.sub(r'[^a-z0-9-]', '', safe_name)
    safe_name = re.sub(r'-+', '-', safe_name).strip('-')
    
    return f"{safe_artist}-{safe_name}.json"

def clamp(x, lo, hi):
    """Clamp value x between lo and hi."""
    return lo if x < lo else hi if x > hi else x

def tempo_to_norm(bpm: float) -> float:
    """Normalize BPM to 0-1 range using configured min/max."""
    min_bpm = CONFIG['min_bpm']
    max_bpm = CONFIG['max_bpm']
    return clamp((bpm - min_bpm) / (max_bpm - min_bpm), 0.0, 1.0)

def median_sorted(vals):
    n = len(vals)
    if n == 0:
        raise ValueError("median of empty list")
    mid = n // 2
    if n % 2 == 1:
        return float(vals[mid])
    return (vals[mid - 1] + vals[mid]) / 2.0

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
def pop_component(pop, center=60.0, plateau=5.0, width=55.0, weight=0.5):
    """
    Piecewise linear popularity term with a flat top around center±plateau,
    then falling linearly to zero at center±width.
    """
    delta = abs(pop - center)
    if delta <= plateau:
        score = 1.0
    elif delta >= width:
        score = 0.0
    else:
        score = 1.0 - (delta - plateau) / (width - plateau)
    return weight * score

# -------- Deny URIs --------
TRACK_DENY_URIS = {
    "spotify:track:7CZyCXKG6d5ALeq41sLzbw",
    #there are more after this
    "spotify:track:4BggEwLhGfrbrl7JBhC8EC",
    "spotify:track:5iSEsR6NKjlC9SrIJkyL3k",
    "spotify:track:69yfbpvmkIaB10msnKT7Q5",
    "spotify:track:4VyU9Tg4drTj2mOUZHSK2u",
    "spotify:track:6JyEh4kl9DLwmSAoNDRn5b",
    "spotify:track:3V1H6liHwCDcWeqdPJabOM",
    "spotify:track:1VzhfMEGIIkn5hFITMJzW1",
    "spotify:track:7GHKA8GIMcND6c5nN1sFnD",
    "spotify:track:4yg2qSpnVAbQLPjCJTWwtY",
    "spotify:track:6qNCLr8GOZOMZJKjfIhxiE",
    "spotify:track:4ncFRft2xEs4kanULQjaOz", #moody man
    "spotify:track:0c6p9QomOhNU9uzujLjtsD", #caught in a mosh
    "spotify:track:2PyDqCtFcXsucZqTF4rE3i", #peter tosh i am that i am
    "spotify:track:05PIJWWaYGCF4cMk5sHQPR ", #live song 
    "spotify:track:73C8vVm2BRLLBQ8FH6N6Qm", #mumfordand songs in the ft.
    "spotify:track:0pPf7GFLcuqp3Eis5Hm5yw", #wasn't smooth guru ni time to play
    "spotify:track:1Xm0HkaGqf0LDouD9Qmo2X", #wasn't hip hop
    "spotify:track:6kZbSmivriyDPLG8wJWRsu", #not ideal for rap
    "spotify:track:3tjnCI2F64MOrRzi3NgXCA", #showiung up for funk
    "spotify:track:5g3rL93FXCoTZwP2zr9RE5", #dJ Osomething nt country
    "spotify:track:2FjvG9IQg242g2LEornfjy", #live freestyle
   "spotify:track:7k3YrlUP1DxGe802jjuT1L",#  // Mulatu Astatke — Yègellé Tezeta
    "spotify:track:61muv9lHtgN18qbm9oK9pH",#  // Quantic — Cumbia Sobre el Mar
    "spotify:track:6SqX9J8tXk7rXaspk7GWX1",#  // Kungs — I Feel So Bad
    "spotify:track:2NF8A7C6tICScdRaZ0BrEe",#  // Ofenbach — Katchi - Ofenbach vs. Nick Waterhouse
    "spotify:track:2Q9F3D53QeclwbsY24cuxO,"  #// M-Beat — Incredible" shwoed up three times
    "spotify:track:4yg2qSpnVAbQLPjCJTWwtY", #jeff buckley live
    "spotify:track:69Yia3qCLw6N9U80WhLwLn", #death metal
    "spotify:track:0P09TBGSKiQwfUsEh1UafT", #hamilton
    "spotify:track:1DrlLvlYd1FIjNavRm6NdX",#not funk rock
    "spotify:track:2r45rookK2awLkiOHOef1o", #Amy Winehouse — Like Smoke
    "spotify:track:1ru5R5iSawvuMELqKXxLjS", #mighty might bosstnes in punk
    "spotify:track:1p50Ir1Hm6Sa1urjaLGi7L", #bring the noise anthrax
    "spotify:track:5YpWUYiyidrtRzYedpXKiU", #bloodhound gang
    "spotify:track:5XTdMVT5i5qcfyTXWxhxVZ",  #Jim Morrison — Ghost Song"
    "spotify:track:0JHREzo9WzIP4vyybhSKPa",  # Five Finger Death Punch — Blue on Black"
    "spotify:track:6mKs2kkBgvf090H566n1pd", #6ix9ine — BEBE"
    "spotify:track:5j3QqRGflS4o5jbsFSwKW1", #DJShawdow
}

# -------- PASTE YOUR GENRE_TREE HERE --------
# REMOVED GENRES (previously commented out, removed for clarity):
# - acid house (electronic > house) - low coverage
# - breakbeat (electronic) - low coverage
# - gangsta rap (hip hop) - redundant with hip hop root
# - bossa nova (latin) - low coverage
# - baroque (classical) - low coverage
# - new age (classical) - low coverage
# - minimalism (classical) - low coverage

GENRE_TREE = {
    "rock": {
        "_seeds": "rock",
        "subgenres": {
            "Heavy": {
                "_seeds": "__synthetic__",
                "subgenres": {
                    "metal": {
                        "_seeds": "metal",
                        "subgenres": {
                            "stoner metal": {"_seeds": "stoner metal"},
                            "death metal": {"_seeds": "death metal"},
                            "nu metal": {"_seeds": "nu metal"},
                        }
                    },
                    "hard rock": {"_seeds": "hard rock"},
                    "punk": {
                        "_seeds": "punk",
                        "subgenres": {
                            "post-punk": {"_seeds": "post-punk"},
                            "emo": {"_seeds": "emo"},
                        }
                    },
                }
            },
            "Modern": {
                "_seeds": "__synthetic__",
                "subgenres": {
                    "alternative rock": {"_seeds": "alternative rock"},
                    "indie rock": {"_seeds": "indie rock"},
                    "shoegaze": {"_seeds": "shoegaze"},
                    "post-rock": {"_seeds": "post-rock"},
                }
            },
            "Retro": {
                "_seeds": "__synthetic__",
                "subgenres": {
                    "classic rock": {"_seeds": "classic rock"},
                    "garage rock": {"_seeds": "garage rock"},
                    "psychedelic rock": {"_seeds": "psychedelic rock"},
                }
            },
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
                }
            },
            "techno": { "_seeds": "techno" },
            "trance": { "_seeds": "trance" },
            "drum and bass": { "_seeds": "drum and bass" },
            "uk garage": { "_seeds": "uk garage" },
            "dubstep": { "_seeds": "dubstep" },
            "synthwave": { "_seeds": "synthwave" },
            "ambient": { "_seeds": "ambient" },
        }
    },

    "pop": {
        "_seeds": "pop",
        "subgenres": {
            "dance pop": {"_seeds": "dance pop"},
            "indie pop": {"_seeds": "indie pop"},
            "electropop": {"_seeds": "electropop"},
            "k-pop": {"_seeds": "k-pop"},
        }
    },

    "hip hop": {
        "_seeds": "hip hop",
        "subgenres": {
            "Regional Hip Hop": {
                "_seeds": "__synthetic__",
                "subgenres": {
                    "east coast hip hop": {"_seeds": "east coast hip hop"},
                    "west coast rap": {"_seeds": "west coast rap"},
                    "southern hip hop": {"_seeds": "southern hip hop"},
                }
            },
            "Trap & Bass": {
                "_seeds": "__synthetic__",
                "subgenres": {
                    "trap": {"_seeds": "trap"},
                    "drill": {"_seeds": "drill"},
                    "phonk": {"_seeds": "phonk"},
                }
            },
            "Alternative Hip Hop": {
                "_seeds": "__synthetic__",
                "subgenres": {
                    "conscious hip hop": {"_seeds": "conscious hip hop"},
                    "underground hip hop": {"_seeds": "underground hip hop"},
                    "cloud rap": {"_seeds": "cloud rap"},
                }
            },
        }
    },

    "r&b / soul / funk": {
        "_seeds": "__synthetic__",
        "subgenres": {
            "r&b": {
                "_seeds": "r&b",
                "subgenres": {
                    "contemporary r&b": {"_seeds": "contemporary r&b"},
                    "quiet storm": {"_seeds": "quiet storm"},
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
            "funk": {"_seeds": "funk"},  # Merged with boogie - no subgenres
            "blues": {"_seeds": "blues"}  # Added - foundation of R&B and soul
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
            "nu jazz": {"_seeds": "nu jazz"},
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
            "indie folk": {"_seeds": "indie folk"}  # Changed from "americana folk" - matches actual Spotify tags
        }
    },

    "latin": {
        "_seeds": "latin",
        "subgenres": {
            "Classic Dance": {
                "_seeds": "__synthetic__",
                "subgenres": {
                    "salsa": {"_seeds": "salsa"},
                    "mambo": {"_seeds": "mambo"},
                    "merengue": {"_seeds": "merengue"},
                    "cumbia": {"_seeds": "cumbia"},
                }
            },
            "Modern Latin": {
                "_seeds": "__synthetic__",
                "subgenres": {
                    "reggaeton": {"_seeds": "reggaeton"},
                    "latin pop": {"_seeds": "latin pop"},
                    "tropical": {"_seeds": "tropical"},
                }
            },
        }
    },

    "Caribbean & African": {
        "_seeds": "__synthetic__",
        "subgenres": {
            "reggae": {"_seeds": "reggae"},
            "dub": {"_seeds": "dub"},
            "ska": {"_seeds": "ska"},
            "dancehall": {"_seeds": "dancehall"},
            "afrobeat": {"_seeds": "afrobeat"},
            "afropop": {"_seeds": "afropop"},
            "amapiano": {"_seeds": "amapiano"}
        }
    },

    "classical": {
        "_seeds": "classical",
        "subgenres": {
            "romantic": {"_seeds": "romantic"},
            "modern classical": {"_seeds": "modern classical"},
        }
    }
}

# -------- GENRE DESCRIPTIONS --------
GENRE_DESCRIPTIONS = {
    # Synthetic parent genres
    "Heavy": "Heavy, distorted rock emphasizing power, aggression, and intensity through metal, hard rock, and punk",
    "Modern": "Contemporary rock exploring atmospheric textures, experimental sounds, and indie aesthetics",
    "Retro": "Classic rock rooted in 60s-80s traditions with raw energy and psychedelic exploration",
    "Regional Hip Hop": "Regional hip hop styles showcasing distinct sounds from East Coast, West Coast, and Southern traditions",
    "Trap & Bass": "Modern bass-heavy hip hop with 808s, trap production, and dark atmospheric sounds",
    "Alternative Hip Hop": "Experimental and underground hip hop pushing creative, lyrical, and production boundaries",
    "Classic Dance": "Traditional Latin dance rhythms including salsa, mambo, merengue, and cumbia",
    "Modern Latin": "Contemporary Latin fusion with reggaeton, pop, and tropical influences",
    "r&b / soul / funk": "Soulful Black American music spanning R&B, soul, funk, and blues traditions",
    "Caribbean & African": "Afro-Caribbean and African rhythms spanning reggae, dancehall, ska, afrobeat, and amapiano",
}

from collections.abc import Mapping

def canon(g: str) -> str:
    if not g: return ""
    g = g.lower().strip()
    g = re.sub(r"[-_/]+", " ", g)
    g = re.sub(r"\s+", " ", g)
    return g

def dump_tree_seeds(tree):
    found = []
    def walk(node, path="root"):
        if isinstance(node, Mapping):
            val = node.get("_seeds", None)
            if isinstance(val, str):
                found.append((path, val))
            elif isinstance(val, (list, tuple)):
                for v in val:
                    if isinstance(v, str):
                        found.append((path, v))
            # only go into explicit subgenres; avoids weird values
            subs = node.get("subgenres")
            if isinstance(subs, Mapping):
                for k, v in subs.items():
                    walk(v, f"{path}/{k}")
    walk(tree)
    return found

assert isinstance(GENRE_TREE, Mapping), "GENRE_TREE is not a dict-like mapping"

_seeds_snapshot = dump_tree_seeds(GENRE_TREE)
print(f"[tree] nodes_with__seeds={len(_seeds_snapshot)} (showing up to 10):", _seeds_snapshot[:10])


# -------- PASTE YOUR EXCLUSIONS HERE --------
EXCLUSIONS = {
    "punk": ["pop punk", "dance", "edm", "electro", "big room"],
    "metal": ["funk metal"],
    "electro": ["electropop", "pop"],
    "rock": ["pop rock", "soft rock"],
    "folk": ["indie folk"],
    "funk": ["funk carioca", "baile funk", "brazilian funk"],
}

# -------- PASTE YOUR GENRE_RULES HERE --------
GENRE_RULES: Dict[str, Dict[str, Any]] = {
  # ----- ROCK OTHER -----
  "alternative rock": {
    "require_artist_genres_any": ["alternative rock", "alternative metal", "post-grunge"],
    "deny_artist_genres_any": ["hardcore punk", "punk", "folk punk", "nu metal", "rap metal", "classic rock", "blues rock"],
    "whitelist_artists": ["Stone Temple Pilots", "Bush", "Live", "Garbage", "Weezer", "Pixies", "Smashing Pumpkins"],
    "boost_artist_contains": ["foo fighters", "collective soul", "everclear", "third eye blind"],
    "min_year": 1985,
    "max_year": 2024,
    "popularity_min": 35,
    "popularity_max": 90
  },
#after this there is a similar format for all gneres
  "indie rock": {
    "require_artist_genres_any": ["indie rock", "modern rock", "garage rock", "lo-fi indie", "indie garage rock", "alternative rock", "garage rock revival"],
    "deny_artist_genres_any": ["hip hop", "rap", "trap", "cloud rap", "alternative hip hop", "dance pop"],
    "whitelist_artists": ["The Strokes", "Interpol", "Arctic Monkeys", "Yeah Yeah Yeahs", "TV On The Radio"],
    "boost_artist_contains": ["parquet courts", "car seat headrest", "alvvays", "vampire weekend"],
    "min_year": 1998,
    "max_year": 2024,
    "popularity_min": 25,
    "popularity_max": 85
  },

  "shoegaze": {
    "require_artist_genres_any": ["shoegaze", "nu gaze", "dream pop", "noise pop", "space rock", "slowcore"],
    "deny_artist_genres_any": ["adult standards", "dance pop", "electropop", "synthpop"],
    "whitelist_artists": [
      "My Bloody Valentine", "Slowdive", "Ride", "Lush", "Chapterhouse",
      "Pale Saints", "Nothing", "Whirr", "Medicine", "Catherine Wheel", "Cocteau Twins", "DIIV"
    ],
    "deny_name_contains": ["remix", "live", "edit"],
    "min_year": 1988,
    "max_year": 2024,
    "popularity_min": 15,
    "popularity_max": 80
  },

  "grunge": {
    "require_artist_genres_any": ["grunge", "post-grunge", "seattle sound"],
    "deny_artist_genres_any": ["classic rock", "pop rock"],
    "whitelist_artists": ["Nirvana", "Soundgarden", "Pearl Jam", "Alice In Chains", "Stone Temple Pilots", "Mudhoney", "Screaming Trees", "Silverchair"],
    "min_year": 1988,
    "max_year": 2002,
    "popularity_min": 30,
    "popularity_max": 90
  },

  "post-rock": {
    "require_artist_genres_any": ["post-rock", "instrumental post-rock", "cinematic post-rock", "math rock", "instrumental rock"],
    "deny_artist_genres_any": ["pop", "dance pop", "electropop", "hip hop", "rap"],
    "whitelist_artists": ["Explosions in the Sky", "Godspeed You! Black Emperor", "Mogwai", "Sigur Rós", "Mono", "This Will Destroy You", "Do Make Say Think", "Tortoise"],
    "min_year": 1994,
    "max_year": 2024,
    "popularity_min": 15,
    "popularity_max": 85
  },

  "classic rock": {
    "require_artist_genres_any": ["classic rock", "album rock"],
    "deny_artist_genres_any": ["dance pop", "electropop", "synthpop", "pop"],
    "max_year": 1985,
    "popularity_min": 30,
    "popularity_max": 85
  },

  "psychedelic rock": {
    "require_artist_genres_any": ["psychedelic rock", "acid rock", "space rock", "neo-psychedelic", "psych pop"],
    "deny_artist_genres_any": ["post-punk", "punk", "proto-punk", "new wave", "garage rock revival", "hip hop", "rap", "edm", "dubstep", "brostep", "electro"],
    "whitelist_artists": ["The 13th Floor Elevators", "Pink Floyd", "The Doors", "Jefferson Airplane", "Cream", "Tame Impala", "Temples", "MGMT"],
    "deny_name_contains": ["remix", "live", "radio edit"],
    "min_year": 1966,
    "max_year": 2024,
    "popularity_min": 25,
    "popularity_max": 90
  },

  "hard rock": {
    "require_artist_genres_any": ["hard rock", "arena rock", "glam metal", "classic rock"],
    "deny_artist_genres_any": ["thrash metal", "speed metal", "death metal", "soft rock", "adult standards", "dance pop", "pop"],
    "whitelist_artists": ["Guns N' Roses", "AC/DC", "Aerosmith", "Def Leppard", "Mötley Crüe", "Poison", "Whitesnake", "Skid Row"],
    "min_year": 1975,
    "max_year": 2024,
    "popularity_min": 30,
    "popularity_max": 85
  },

  # --- COUNTRY -----
  "country": {
    "require_artist_genres_any": ["country", "contemporary country", "country road", "new country"],
    "deny_artist_genres_any": ["europop", "eurodance", "dance pop", "pop", "austropop"],
    "min_year": 1965,
    "max_year": 2024,
    "popularity_min": 40,
    "popularity_max": 90
  },

  # ----- ELECTRONIC -----
  "house": {
    "require_artist_genres_any": ["house", "deep house", "tech house", "progressive house", "electro house", "funky house", "disco house"],
    "deny_artist_genres_any": ["hip hop", "trap", "rap", "dubstep", "soundtrack"],
    "deny_name_contains": ["feat."],
    "min_year": 1985,
    "max_year": 2024,
    "popularity_min": 20,
    "popularity_max": 85
  },

  "deep house": {
    "require_artist_genres_any": ["deep house", "melodic deep house", "vocal deep house"],
    "deny_artist_genres_any": ["dubstep", "trap", "drum and bass"],
    "min_year": 1990,
    "max_year": 2024,
    "popularity_min": 15,
    "popularity_max": 85
  },

  "tech house": {
    "require_artist_genres_any": ["tech house"],
    "deny_artist_genres_any": ["trance", "big room", "edm"],
    "min_year": 1998,
    "max_year": 2024,
    "popularity_min": 15,
    "popularity_max": 85
  },

  "progressive house": {
    "require_artist_genres_any": ["progressive house"],
    "deny_artist_genres_any": ["trance", "uplifting trance", "eurotrance", "dance pop", "big room", "electro house"],
    "min_year": 1992,
    "max_year": 2024,
    "popularity_min": 15,
    "popularity_max": 85
  },

  "acid house": {
    "require_artist_genres_any": ["acid house", "chicago house"],
    "deny_artist_genres_any": ["trance", "progressive house", "vocal house", "deep house", "pop"],
    "whitelist_artists": ["Phuture", "DJ Pierre", "Adonis", "Armando", "Fast Eddie", "Bam Bam", "Hardfloor", "A Guy Called Gerald", "808 State"],
    "deny_name_contains": ["remix", "edit", "mix", "feat.", "featuring", "2008", "2007", "2006"],
    "min_year": 1987,
    "max_year": 1998,
    "popularity_min": 10,
    "popularity_max": 80
  },

  "techno": {
    "require_artist_genres_any": ["techno", "detroit techno", "minimal techno", "hard techno", "berlin techno", "berlin school"],
    "deny_artist_genres_any": ["deep house", "house", "progressive house", "trance", "edm"],
    "whitelist_artists": ["Juan Atkins", "Jeff Mills", "Carl Craig", "Richie Hawtin", "Laurent Garnier", "Surgeon"],
    "min_year": 1988,
    "max_year": 2024,
    "popularity_min": 10,
    "popularity_max": 85
  },

  "trance": {
    "require_artist_genres_any": ["trance", "uplifting trance", "progressive trance", "eurotrance", "psytrance", "goa trance"],
    "deny_artist_genres_any": ["dance pop", "big room", "edm"],
    "min_year": 1994,
    "max_year": 2024,
    "popularity_min": 15,
    "popularity_max": 85
  },

  "breakbeat": {
    "require_artist_genres_any": ["breakbeat","breaks","nu skool breaks","nu breaks","big beat"],
    "deny_artist_genres_any": ["drum and bass", "jungle", "uk garage", "ukg", "dubstep", "garage", "2 step"],
    "whitelist_artists": [
      "The Chemical Brothers", "The Prodigy", "Plump DJs", "Stanton Warriors",
      "Hybrid", "The Freestylers", "Krafty Kuts", "Adam Freeland",
      "Rennie Pilgrem", "Aquasky", "Elite Force", "Deekline & Wizard",
      "Orbital", "Crystal Method", "Fatboy Slim"
    ],
    "boost_artist_contains": ["plump djs", "stanton warriors", "freestylers", "hybrid", "krafty kuts", "adam freeland", "rennie pilgrem", "elite force", "aquasky"],
    "min_year": 1990,
    "max_year": 2012,
    "popularity_min": 15,
    "popularity_max": 85
  },

  "dubstep": {
    "require_artist_genres_any": ["dubstep", "brostep", "uk dubstep", "post-dubstep", "melodic dubstep"],
    "deny_artist_genres_any": ["future bass", "progressive house", "electro house"],
    "whitelist_artists": ["Skream", "Benga", "Mala", "Burial", "Rusko", "Flux Pavilion", "Distance", "Coki", "Digital Mystikz", "Skrillex", "Seven Lions", "NERO"],
    "deny_name_contains": ["remix", "live"],  # Prevent remixes/live versions
    "min_year": 2006,
    "max_year": 2024,
    "popularity_min": 15,
    "popularity_max": 90  # Raised to allow popular Skrillex tracks
  },

  # ----- HIP HOP -----
  "hip hop": {
    "require_artist_genres_any": ["hip hop", "rap", "east coast hip hop", "west coast rap", "southern hip hop"],
    "deny_artist_genres_any": ["rock", "pop", "dance pop"],
    "min_year": 1980,
    "max_year": 2024,
    "popularity_min": 25,
    "popularity_max": 80
  },

  "rap": {
    "require_artist_genres_any": ["rap", "hip hop", "hip-hop"],
    "deny_artist_genres_any": ["dance pop", "electropop", "synthpop", "latin pop", "pop"],
    "deny_name_contains": ["remix", "edit", "radio edit", "acoustic"],
    "min_year": 1980,
    "max_year": 2024,
    "popularity_min": 20,
    "popularity_max": 85
  },

  "underground hip hop": {
    "require_artist_genres_any": ["underground hip hop", "boom bap", "abstract hip hop", "backpack rap"],
    "deny_artist_genres_any": ["dance pop", "pop", "trap", "pop rap", "electropop", "synthpop", "neo soul", "r&b", "contemporary r&b"],
    "whitelist_artists": ["MF DOOM", "Atmosphere", "Company Flow", "Aesop Rock", "Brother Ali", "Pharoahe Monch"],
    "min_year": 1994,
    "max_year": 2024,
    "popularity_min": 10,
    "popularity_max": 70
  },

  "boom bap": {
    "require_artist_genres_any": ["boom bap", "east coast hip hop", "underground hip hop"],
    "deny_artist_genres_any": ["neo soul", "r&b", "jazz", "contemporary r&b", "trap", "drill"],
    "min_year": 1988,
    "max_year": 2010,
    "popularity_min": 10,
    "popularity_max": 80
  },

  "east coast hip hop": {
    "require_artist_genres_any": ["east coast hip hop", "boom bap", "nyc rap", "queens hip hop"],
    "deny_artist_genres_any": ["west coast rap", "southern hip hop", "reggae fusion", "dancehall", "latin pop", "alternative hip hop"],
    "whitelist_artists": [
      "Nas", "Mobb Deep", "Wu-Tang Clan", "A Tribe Called Quest", "The Notorious B.I.G.",
      "Rakim", "Gang Starr", "Big L", "Mos Def", "Black Star", "Busta Rhymes", "Eric B. & Rakim",
      "Big Daddy Kane", "MF DOOM", "Joey Bada$$", "Boot Camp Clik", "De La Soul"
    ],
    "deny_name_contains": ["remix", "edit", "12\"", "dub", "re-drum", "re drum", "re-edit", "re edit", "instrumental"],
    "min_year": 1988,
    "max_year": 2024,
    "popularity_min": 20,
    "popularity_max": 80
  },

  "west coast rap": {
    "require_artist_genres_any": ["west coast rap", "g funk", "gangsta rap", "la hip hop", "bay area hip hop", "west coast"],
    "deny_artist_genres_any": ["east coast hip hop", "boom bap", "southern hip hop", "uk hip hop", "east coast"],
    "min_year": 1989,
    "max_year": 2024,
    "popularity_min": 20,
    "popularity_max": 90
  },

  "trap": {
    "require_artist_genres_any": ["trap", "southern hip hop", "atl hip hop"],
    "deny_artist_genres_any": ["dance pop", "pop"],
    "min_year": 2005,
    "max_year": 2024,
    "popularity_min": 20,
    "popularity_max": 85
  },

  "drill": {
    "require_artist_genres_any": ["drill", "uk drill", "brooklyn drill", "chicago drill"],
    "deny_artist_genres_any": ["jazz rap", "experimental hip hop", "alternative hip hop", "conscious hip hop","dance pop"],
    "whitelist_artists": ["Chief Keef", "Pop Smoke", "Lil Durk", "King Von", "Fivio Foreign", "Headie One", "Digga D", "67", "Loski"],
    "min_year": 2012,
    "max_year": 2024,
    "popularity_min": 20,
    "popularity_max": 85
  },

  "conscious hip hop": {
    "require_artist_genres_any": ["conscious hip hop", "hip hop", "jazz rap", "alternative hip hop", "rap"],
    "deny_artist_genres_any": ["rock", "alternative rock", "pop rock", "trap", "drill", "reggae", "roots reggae", "modern reggae"],  # Added reggae to avoid crossover
    "boost_artist_contains": ["common", "mos def", "blackstar", "black star", "kendrick lamar", "talib kweli", "little simz"],
    "deny_name_contains": ["remix", "live", "radio edit"],
    "min_year": 1990,
    "max_year": 2024,
    "popularity_min": 20,
    "popularity_max": 85
  },

  "southern hip hop": {
    "require_artist_genres_any": ["southern hip hop", "texas rap", "houston rap", "memphis rap", "atlanta hip hop", "dirty south"],
    "deny_artist_genres_any": ["east coast hip hop", "boom bap", "west coast rap"],
    "whitelist_artists": ["UGK", "8Ball & MJG", "Three 6 Mafia", "Scarface", "Geto Boys", "OutKast", "Goodie Mob", "Lil Keke"],
    "boost_artist_contains": ["texas", "houston", "memphis", "atlanta"],
    "min_year": 1992,
    "max_year": 2024,
    "popularity_min": 20,
    "popularity_max": 85
  },

  # ----- R&B / SOUL / FUNK -----
  "r&b": {
    "require_artist_genres_any": ["r&b", "contemporary r&b", "neo soul"],
    "deny_artist_genres_any": ["rap", "hip hop", "trap", "drill"],
    "min_year": 1980,
    "max_year": 2024,
    "popularity_min": 25,
    "popularity_max": 90
  },

  "quiet storm": {
    "require_artist_genres_any": ["quiet storm"],
    "min_year": 1975,
    "max_year": 2005,
    "popularity_min": 15,
    "popularity_max": 85
  },

  "soul": {
    "require_artist_genres_any": ["soul", "neo soul", "motown"],
    "deny_artist_genres_any": ["hip hop", "rap", "trap"],
    "min_year": 1965,
    "max_year": 2024,
    "popularity_min": 20,
    "popularity_max": 90
  },

  "motown": {
    "require_artist_genres_any": ["motown"],
    "deny_artist_genres_any": ["southern soul", "philly soul", "funk", "pop"],
    "max_year": 1972,
    "popularity_min": 15,
    "popularity_max": 85
  },

  "funk": {
    "require_artist_genres_any": ["funk", "p funk", "p-funk", "classic funk", "pfunk", "boogie", "post-disco", "modern funk"],  # Merged with boogie
    "deny_artist_genres_any": ["rap", "contemporary r&b", "quiet storm", "rock", "blues rock", "garage rock", "alternative rock", "indie rock"],
    "whitelist_artists": ["Parliament", "Funkadelic", "George Clinton", "Bootsy Collins", "The Meters", "Ohio Players", "Kool & The Gang", "Zapp", "Cameo", "Con Funk Shun", "DāM-Funk", "Vulfpeck", "Tim Maia", "Marcos Valle"],
    "boost_artist_contains": ["james brown", "sly stone", "graham central", "tower of power"],
    "min_year": 1967,
    "max_year": 1992,  # Extended to cover boogie era (1978-1990)
    "popularity_min": 10,  # Lowered to allow more niche tracks
    "popularity_max": 85
  },

  "blues": {
    "require_artist_genres_any": ["blues", "electric blues", "chicago blues", "delta blues", "blues rock", "modern blues"],
    "deny_artist_genres_any": ["country blues", "bluegrass", "folk"],
    "whitelist_artists": ["B.B. King", "Muddy Waters", "Howlin' Wolf", "Buddy Guy", "Stevie Ray Vaughan", "Gary Clark Jr.", "Joe Bonamassa"],
    "boost_artist_contains": ["robert johnson", "john lee hooker", "albert king", "eric clapton"],
    "deny_name_contains": ["remix", "edit", "radio edit"],
    "min_year": 1950, "max_year": 2024, "popularity_min": 10, "popularity_max": 85
  },

  "neo soul": {
    "require_artist_genres_any": ["neo soul"],
    "deny_artist_genres_any": ["rap", "trap", "drill", "dance pop", "pop"],
    "whitelist_artists": ["Erykah Badu", "D’Angelo", "Jill Scott", "Angie Stone", "Maxwell", "The Internet", "Solange", "H.E.R.", "Cleo Sol", "Ari Lennox"],
    "min_year": 1997,
    "max_year": 2024,
    "popularity_min": 20,
    "popularity_max": 90
  },

  # ----- JAZZ -----
  "jazz fusion": {
    "require_artist_genres_any": ["jazz fusion", "fusion", "jazz funk", "jazz-rock", "jazz rock"],
    "deny_artist_genres_any": ["bachata", "latin pop", "reggaeton", "dance pop", "pop", "soundtrack", "synthwave", "new age", "hard bop", "bebop", "cool jazz"],
    "min_year": 1969,
    "max_year": 2024,
    "popularity_min": 10,
    "popularity_max": 85
  },

  "bebop": {
    "require_artist_genres_any": ["bebop", "hard bop", "bop"],
    "deny_artist_genres_any": ["smooth jazz", "vocal jazz", "easy listening"],
    "max_year": 1970,  # Relaxed slightly
    "popularity_min": 5,
    "popularity_max": 80
  },

  "cool jazz": {
    "require_artist_genres_any": ["cool jazz", "west coast jazz", "modal jazz"],
    "deny_artist_genres_any": ["smooth jazz", "vocal jazz", "easy listening"],
    "max_year": 1980,  # Relaxed
    "popularity_min": 5,
    "popularity_max": 85
  },

  "hard bop": {
    "require_artist_genres_any": ["hard bop", "post bop", "bebop", "modal jazz", "spiritual jazz"],
    "deny_artist_genres_any": ["smooth jazz", "vocal jazz", "easy listening"],
    "min_year": 1955,
    "max_year": 1980,  # Relaxed
    "popularity_min": 5,
    "popularity_max": 85
  },

  "swing": {
    "require_artist_genres_any": ["swing", "big band", "big band jazz"],
    "deny_artist_genres_any": ["hip hop", "rap", "trap", "drill"],
    "max_year": 1965,
    "popularity_min": 5,
    "popularity_max": 85
  },

  "smooth jazz": {
    "require_artist_genres_any": ["smooth jazz"],
    "deny_artist_genres_any": ["r&b", "contemporary r&b", "neo soul", "easy listening", "adult standards"],
    "min_year": 1978,
    "max_year": 2024,
    "popularity_min": 10,
    "popularity_max": 85
  },

  # ----- LATIN / CARIBBEAN & AFRICAN -----
  "bossa nova": {
    "require_artist_genres_any": ["bossa nova"],
    "deny_artist_genres_any": ["samba", "latin pop", "reggaeton"],
    "whitelist_artists": ["Antonio Carlos Jobim", "João Gilberto", "Astrud Gilberto", "Stan Getz", "Nara Leão", "Marcos Valle"],
    "min_year": 1958,
    "max_year": 1995,
    "popularity_min": 10,
    "popularity_max": 85
  },

  "salsa": {
    "require_artist_genres_any": ["salsa", "salsa romantica"],
    "deny_artist_genres_any": ["rap", "reggaeton", "latin trap"],
    "min_year": 1965,
    "max_year": 2024,
    "popularity_min": 15,
    "popularity_max": 85
  },

  "mambo": {
    "require_artist_genres_any": ["mambo"],
    "min_year": 1950,
    "max_year": 1990,
    "popularity_min": 5,
    "popularity_max": 80
  },

  "soca": {
    "require_artist_genres_any": ["soca", "power soca", "groovy soca", "chutney soca", "bashment soca"],
    "deny_artist_genres_any": ["dancehall", "reggaeton", "latin pop"],
    "whitelist_artists": ["Machel Montano", "Kes", "Bunji Garlin", "Patrice Roberts", "Destra", "Nailah Blackman", "Skinny Fabulous", "Alison Hinds"],
    "min_year": 1990,
    "max_year": 2024,
    "popularity_min": 10,
    "popularity_max": 85
  },

  "ska": {
    "require_artist_genres_any": ["ska", "ska punk", "2 tone", "third wave ska", "rocksteady"],
    "deny_artist_genres_any": ["roots reggae", "reggae", "dancehall", "dub"],
    "min_year": 1963,
    "max_year": 2024,
    "popularity_min": 10,
    "popularity_max": 85
  },

  "dancehall": {
    "require_artist_genres_any": ["dancehall"],
    "deny_artist_genres_any": ["reggaeton", "latin pop", "pop", "dance pop"],
    "min_year": 1988,
    "max_year": 2024,
    "popularity_min": 15,
    "popularity_max": 85
  },

  "afrobeat": {
    "require_artist_genres_any": ["afrobeat", "nigerian afrobeat", "afro funk"],
    "deny_artist_genres_any": ["soul", "funk", "r&b", "afropop", "dance pop"],
    "min_year": 1970,
    "max_year": 2024,
    "popularity_min": 10,
    "popularity_max": 85
  },

  "afropop": {
    "require_artist_genres_any": ["afropop", "afrobeats", "naija pop", "alté", "amapiano"],
    "deny_artist_genres_any": ["afrobeat"],
    "min_year": 2010,
    "max_year": 2024,
    "popularity_min": 20,
    "popularity_max": 90
  },

  "dub": {
    "require_artist_genres_any": ["dub", "dub reggae", "roots dub", "steppers"],
    "deny_artist_genres_any": ["dancehall", "reggae fusion", "ska", "rocksteady"],
    "whitelist_artists": ["King Tubby", "Scientist", "Lee Scratch Perry", "Augustus Pablo", "Mad Professor", "Prince Jammy"],
    "min_year": 1972,
    "max_year": 2015,
    "popularity_min": 5,
    "popularity_max": 85
  },
        # ----- METAL FAMILY -----
    "metal": {
        "require_artist_genres_any": ["metal", "heavy metal", "hard rock", "nwobhm", "classic metal"],
        "deny_artist_genres_any": [
            "power metal", "symphonic metal", "melodic metal",
            "progressive metal", "nu metal", "alternative metal"
        ],
        "whitelist_artists": ["Judas Priest", "Iron Maiden", "Motörhead", "Dio", "Black Sabbath", "Ozzy Osbourne", "Saxon", "Accept"],
        "boost_artist_contains": [
            "metallica","megadeth","anthrax","slayer","pantera",
            "iron maiden","judas priest","sepultura","motorhead",
            "dio","black sabbath","opeth","testament"
        ],
        "deny_name_contains": ["remaster", "remastered", "live", "edit", "demo"],
        "min_year": 1975,
        "max_year": 2005,
        "popularity_min": 10,
        "popularity_max": 80
    },

    "thrash metal": {
        "require_artist_genres_any": ["thrash metal", "thrash"],
        "deny_artist_genres_any": ["death metal", "melodic death metal", "power metal", "progressive metal", "metalcore"],
        "whitelist_artists": ["Metallica", "Slayer", "Megadeth", "Anthrax", "Testament", "Exodus", "Kreator", "Sodom", "Overkill"],
        "deny_name_contains": ["remaster", "remastered", "live", "edit"],
        "min_year": 1983,
        "max_year": 2004,
        "popularity_min": 10,
        "popularity_max": 85
    },

    "stoner metal": {
        "require_artist_genres_any": ["stoner metal", "stoner rock", "uk doom metal", "doom metal", "sludge metal"],
        "deny_artist_genres_any": ["symphonic metal", "gothic metal", "power metal", "metalcore"],
        "deny_name_contains": ["live", "edit", "remix"],
        "min_year": 1988,
        "max_year": 2020,
        "popularity_min": 5,
        "popularity_max": 85
    },

    "death metal": {
        "require_artist_genres_any": ["death metal", "brutal death metal", "technical death metal", "melodic death metal", "old school death metal", "swedish death metal", "florida death metal"],
        "deny_artist_genres_any": ["symphonic metal", "gothic metal", "black metal", "thrash metal", "metalcore"],
        "whitelist_artists": ["Death", "Cannibal Corpse", "Morbid Angel", "Obituary", "Deicide", "Suffocation", "Carcass", "Entombed"],
        "deny_name_contains": ["remaster", "remastered", "live", "edit"],
        "min_year": 1987,
        "max_year": 2012,
        "popularity_min": 5,
        "popularity_max": 80
    },

    "nu metal": {
        "require_artist_genres_any": ["nu metal"],
        "deny_artist_genres_any": ["death metal", "drum and bass", "electronic", "industrial rock"],
        "whitelist_artists": ["Korn", "Limp Bizkit", "Linkin Park", "Deftones", "Disturbed", "System of a Down", "Papa Roach", "P.O.D."],
        "deny_name_contains": ["remix", "radio edit", "edit", "live"],
        "min_year": 1996,
        "max_year": 2010,
        "popularity_min": 20,
        "popularity_max": 85
    },

    # ----- PUNK LANES -----
    "punk": {
        "require_artist_genres_any": ["punk", "punk rock"],
        "deny_artist_genres_any": ["pop", "dance pop", "electropop", "alternative rock", "comedy rock", "novelty", "garage rock", "pop punk","ska"],
        "deny_name_contains": ["remix", "edit", "radio edit", "live"],
        "min_year": 1976,
        "max_year": 2024,
        "popularity_min": 10,
        "popularity_max": 85
    },

    "ska": {
        "require_artist_genres_any": ["ska", "ska punk", "2 tone", "third wave ska", "rocksteady"],
        "deny_artist_genres_any": ["punk rock", "hardcore punk", "new wave"],
        "whitelist_artists": ["The Specials", "The Selecter", "The Beat", "Toots & The Maytals", "The Skatalites", "The Mighty Mighty Bosstones", "Rancid"],
        "deny_name_contains": ["remix", "edit", "radio edit", "live"],
        "min_year": 1963,
        "max_year": 2024,
        "popularity_min": 10,
        "popularity_max": 85
    },

    "hardcore": {
        "require_artist_genres_any": ["hardcore punk", "nyhc", "post-hardcore", "powerviolence", "d-beat", "youth crew"],
        "deny_artist_genres_any": ["happy hardcore", "hardcore techno", "gabber", "edm", "dance", "dance pop", "pop", "pop punk", "emo", "metalcore", "easycore"],
        "deny_name_contains": ["remix", "edit", "radio edit", "live"],
        "min_year": 1981,
        "max_year": 2010,
        "popularity_min": 5,
        "popularity_max": 70
    },

    "post-punk": {
        "require_artist_genres_any": ["post-punk", "post punk", "gothic rock", "coldwave", "no wave"],
        "deny_artist_genres_any": ["classic rock", "soft rock", "dance pop", "pop punk", "grunge", "hardcore punk"],
        "deny_name_contains": ["remix", "edit", "radio edit", "live"],
        "min_year": 1978,
        "max_year": 1995,  # Relaxed slightly
        "popularity_min": 5,
        "popularity_max": 85
    },

    "emo": {
        "require_artist_genres_any": ["emo", "midwest emo", "emo punk", "emo pop", "screamo", "emocore", "post-hardcore"],
        "deny_artist_genres_any": ["emo rap", "trap", "southern hip hop", "drill", "phonk"],
        "whitelist_artists": [
            "Sunny Day Real Estate","Mineral","American Football","Braid","The Get Up Kids","Texas Is the Reason",
            "Jawbreaker","Rites of Spring","Embrace","Cap'n Jazz","Jimmy Eat World","Thursday",
            "Taking Back Sunday","Brand New","Saves the Day","The Promise Ring","Quicksand"
        ],
        "boost_artist_contains": [
            "mcr","my chemical romance","dashboard confessional","fall out boy","paramore","hawthorne heights"
        ],
        "deny_name_contains": ["remix", "edit", "radio edit", "live", "acoustic"],
        "min_year": 1985,
        "max_year": 2010,
        "popularity_min": 10,
        "popularity_max": 85
    },

        # ===== ROCK MISSING =====
    "garage rock": {
        "require_artist_genres_any": ["garage rock", "garage rock revival", "proto-punk", "punk blues"],
        "deny_artist_genres_any": ["dance pop", "electropop", "pop", "indie pop"],
        "whitelist_artists": ["The Sonics", "The Stooges", "The Cramps", "The Hives", "The Kills", "The White Stripes"],
        "deny_name_contains": ["remix", "edit", "live", "remaster", "remastered"],
        "min_year": 1965, "max_year": 2012, "popularity_min": 5, "popularity_max": 85
    },

    # ===== ELECTRONIC MISSING =====
    "drum and bass": {
        "require_artist_genres_any": ["drum and bass", "dnb", "liquid funk", "neurofunk", "jump up"],
        "deny_artist_genres_any": ["dubstep", "breakbeat", "uk garage"],
        "whitelist_artists": ["High Contrast", "LTJ Bukem", "Goldie", "Noisia", "Calibre", "Logistics", "Pendulum"],
        "deny_name_contains": ["radio edit", "remix", "vip", "edit", "live"],
        "min_year": 1995, "max_year": 2020, "popularity_min": 10, "popularity_max": 85
    },
    "uk garage": {
        "require_artist_genres_any": ["uk garage", "ukg", "2-step", "speed garage"],
        "deny_artist_genres_any": ["grime", "dubstep", "drum and bass"],
        "whitelist_artists": ["Artful Dodger", "MJ Cole", "Todd Edwards", "So Solid Crew", "DJ Luck & MC Neat", "Sunship"],
        "deny_name_contains": ["radio edit", "remix", "edit", "dub"],
        "min_year": 1996, "max_year": 2005, "popularity_min": 10, "popularity_max": 85
    },
    "synthwave": {
        "require_artist_genres_any": ["synthwave", "darksynth", "retro electro", "outrun"],
        "deny_artist_genres_any": ["edm", "big room", "dance pop"],
        "whitelist_artists": ["Carpenter Brut", "Perturbator", "Kavinsky", "Gunship", "M|O|O|N", "Magic Sword"],
        "deny_name_contains": ["remix", "edit", "radio edit", "live"],
        "min_year": 2008, "max_year": 2024, "popularity_min": 5, "popularity_max": 85
    },
    "ambient": {
        "require_artist_genres_any": ["ambient", "drone", "modern classical", "electronic ambient"],
        "deny_artist_genres_any": ["edm", "techno", "house", "trance"],
        "whitelist_artists": ["Brian Eno", "Stars of the Lid", "William Basinski", "Harold Budd", "Marconi Union", "Aphex Twin"],
        "deny_name_contains": ["remix", "edit", "radio edit"],
        "min_year": 1975, "max_year": 2024, "popularity_min": 5, "popularity_max": 80
    },

    # ===== POP =====
    "pop": {
        "require_artist_genres_any": ["pop", "art pop", "baroque pop", "chamber pop"],
        "deny_artist_genres_any": ["dance pop", "indie pop", "electropop", "k-pop", "pop rap", "trap", "hip hop", "r&b", "country pop", "latin pop", "reggaeton"],
        "whitelist_artists": ["Taylor Swift", "Adele", "Ed Sheeran", "Sam Smith", "Coldplay"],
        "deny_name_contains": ["remix", "edit", "radio edit", "live"],  # Added live
        "min_year": 2000, "max_year": 2024, "popularity_min": 50, "popularity_max": 100
    },

    "dance pop": {
        "require_artist_genres_any": ["dance pop", "pop dance", "eurodance", "post-teen pop"],
        "deny_artist_genres_any": ["indie pop", "art pop", "chamber pop", "k-pop", "j-pop", "hip hop", "trap", "edm", "art rock", "rock"],  # Added art rock and rock
        "whitelist_artists": ["Dua Lipa", "The Weeknd", "Ariana Grande", "Britney Spears", "Lady Gaga", "Kylie Minogue"],
        "deny_name_contains": ["remix", "edit", "radio edit", "live"],  # Added live
        "min_year": 1995, "max_year": 2024, "popularity_min": 55, "popularity_max": 100
    },

    "indie pop": {
        "require_artist_genres_any": ["indie pop", "bedroom pop", "indie poptimism", "alt z"],
        "deny_artist_genres_any": ["dance pop", "k-pop", "electropop", "hip hop", "trap", "indie rock", "indie folk"],
        "whitelist_artists": ["Clairo", "Rex Orange County", "Carly Rae Jepsen", "Lorde", "Vampire Weekend", "MGMT"],
        "deny_name_contains": ["remix", "edit", "radio edit"],
        "min_year": 2005, "max_year": 2024, "popularity_min": 40, "popularity_max": 95
    },

    "electropop": {
        "require_artist_genres_any": ["electropop", "synthpop", "new wave pop", "indietronica"],
        "deny_artist_genres_any": ["dance pop", "indie pop", "k-pop", "edm", "house", "techno"],
        "whitelist_artists": ["CHVRCHES", "Robyn", "Grimes", "Charli XCX", "Passion Pit", "M83"],
        "deny_name_contains": ["remix", "edit", "radio edit"],
        "min_year": 2005, "max_year": 2024, "popularity_min": 40, "popularity_max": 90
    },

    "k-pop": {
        "require_artist_genres_any": ["k-pop"],
        "deny_artist_genres_any": ["j-pop", "dance pop", "indie pop", "mandopop"],
        "whitelist_artists": ["BTS", "BLACKPINK", "EXO", "TWICE", "Red Velvet", "Stray Kids", "ITZY", "aespa"],
        "deny_artist_contains": ["irene", "seulgi", "jennie", "rosé", " - "],  # Deny sub-units and solo artists
        "deny_name_contains": ["remix", "instrumental", "live"],
        "min_year": 2010, "max_year": 2024, "popularity_min": 50, "popularity_max": 100
    },

    # ===== HIP HOP MISSING =====
    "gangsta rap": {
        "require_artist_genres_any": ["gangsta rap", "g funk", "west coast rap"],
        "deny_artist_genres_any": ["boom bap", "east coast hip hop", "conscious hip hop"],
        "whitelist_artists": ["N.W.A", "Ice Cube", "Dr. Dre", "Snoop Dogg", "DJ Quik", "The Game"],
        "deny_name_contains": ["remix", "edit", "radio edit", "live"],
        "min_year": 1988, "max_year": 2010, "popularity_min": 15, "popularity_max": 85
    },
    "phonk": {
        "require_artist_genres_any": ["phonk", "memphis phonk", "drift phonk"],
        "deny_artist_genres_any": ["trap metal", "hardstyle"],
        "whitelist_artists": ["DJ Smokey", "Soudiere", "Kordhell", "Ghostemane", "Inteus", "Ryan Celsius"],
        "deny_name_contains": ["remix", "edit", "slowed", "reverb"],
        "min_year": 2012, "max_year": 2024, "popularity_min": 5, "popularity_max": 85
    },
    "cloud rap": {
        "require_artist_genres_any": ["cloud rap", "underground hip hop", "alternative hip hop"],
        "deny_artist_genres_any": ["boom bap", "trap metal"],
        "whitelist_artists": ["Yung Lean", "A$AP Rocky", "Clams Casino", "Bladee", "Lil B"],
        "deny_name_contains": ["remix", "edit", "radio edit"],
        "min_year": 2011, "max_year": 2024, "popularity_min": 10, "popularity_max": 85
    },

    # ===== R&B / SOUL / FUNK MISSING =====
    "contemporary r&b": {
        "require_artist_genres_any": ["contemporary r&b", "r&b", "neo soul"],
        "deny_artist_genres_any": ["rap", "trap", "drill"],
        "whitelist_artists": ["Usher", "Mary J. Blige", "Aaliyah", "TLC", "Tinashe", "H.E.R.", "SZA"],
        "deny_name_contains": ["remix", "edit", "radio edit"],
        "min_year": 1994, "max_year": 2024, "popularity_min": 20, "popularity_max": 90
    },
    "disco": {
        "require_artist_genres_any": ["disco", "post-disco", "philly soul"],
        "deny_artist_genres_any": ["house", "edm", "dance pop"],
        "whitelist_artists": ["Chic", "Donna Summer", "Bee Gees", "Diana Ross", "The Trammps", "Sylvester"],
        "deny_name_contains": ["remix", "edit", "radio edit", "12\" mix"],
        "min_year": 1975, "max_year": 1982, "popularity_min": 20, "popularity_max": 90
    },

    # ===== JAZZ MISSING =====
    "vocal jazz": {
        "require_artist_genres_any": ["vocal jazz", "jazz vocal", "torch song", "standards"],
        "deny_artist_genres_any": ["swing", "bebop", "cool jazz"],
        "whitelist_artists": ["Ella Fitzgerald", "Billie Holiday", "Sarah Vaughan", "Chet Baker", "Diana Krall", "Nat King Cole"],
        "deny_name_contains": ["remix", "edit", "radio edit", "live"],
        "min_year": 1947, "max_year": 2005, "popularity_min": 10, "popularity_max": 85
    },
    "nu jazz": {
        "require_artist_genres_any": ["nu jazz", "acid jazz", "jazztronica", "future jazz"],
        "deny_artist_genres_any": ["smooth jazz", "dance pop"],
        "whitelist_artists": ["St Germain", "The Cinematic Orchestra", "Jazzanova", "Koop", "Bugge Wesseltoft"],
        "deny_name_contains": ["remix", "edit", "radio edit"],
        "min_year": 1996, "max_year": 2012, "popularity_min": 10, "popularity_max": 85
    },

    # ===== COUNTRY MISSING =====
    "classic country": {
        "require_artist_genres_any": ["classic country", "country", "nashville sound", "classic country pop"],
        "deny_artist_genres_any": ["bro country", "country road", "jazz", "vocal jazz", "contemporary vocal jazz", "ccm", "neo mellow"],  # Added jazz and ccm to avoid crossover
        "whitelist_artists": ["Johnny Cash", "Merle Haggard", "Patsy Cline", "George Jones", "Loretta Lynn", "Conway Twitty"],  # Removed modern artists
        "deny_name_contains": ["remix", "edit", "radio edit", "live"],
        "max_year": 1990, "popularity_min": 10, "popularity_max": 85
    },
    "indie folk": {
        "require_artist_genres_any": ["indie folk", "folk-pop", "chamber folk", "folk", "stomp and holler"],
        "deny_artist_genres_any": ["dance pop", "electropop", "indie pop", "bedroom pop", "indie soul", "uk alternative pop", "electronic", "electronica"],  # Added electronic genres
        "whitelist_artists": ["Fleet Foxes", "Bon Iver", "Iron & Wine", "The Lumineers", "Mumford & Sons", "Of Monsters and Men"],
        "deny_name_contains": ["remix", "edit", "radio edit", "live"],
        "min_year": 2005, "max_year": 2024, "popularity_min": 10, "popularity_max": 85
    },

    # ===== LATIN MISSING =====
    "latin pop": {
        "require_artist_genres_any": ["latin pop", "pop latino"],
        "deny_artist_genres_any": ["reggaeton", "latin trap"],
        "whitelist_artists": ["Shakira", "Ricky Martin", "Enrique Iglesias", "Thalía", "Luis Fonsi", "Juanes"],
        "deny_name_contains": ["remix", "edit", "radio edit"],
        "min_year": 1995, "max_year": 2024, "popularity_min": 25, "popularity_max": 90
    },
    "tropical": {
        "require_artist_genres_any": ["tropical", "tropical house", "latin","tropical pop"],
        "deny_artist_genres_any": ["reggaeton", "latin trap"],
        "deny_name_contains": ["remix", "edit", "radio edit"],
        "popularity_min": 10, "popularity_max": 85
    },

    # ===== REGGAE FAMILY MISSING =====
    "reggae": {
        "require_artist_genres_any": ["reggae", "roots reggae", "lovers rock", "rocksteady"],
        "deny_artist_genres_any": ["dancehall", "reggaeton"],
        "whitelist_artists": ["Bob Marley & The Wailers", "Toots & The Maytals", "Burning Spear", "Peter Tosh", "Third World", "Gregory Isaacs"],
        "deny_name_contains": ["remix", "edit", "radio edit", "dub"],
        "min_year": 1968, "max_year": 1990, "popularity_min": 10, "popularity_max": 85
    },
    "amapiano": {
        "require_artist_genres_any": ["amapiano", "afro house", "south african house"],
        "deny_artist_genres_any": ["gqom", "dance pop"],
        "whitelist_artists": ["Kabza De Small", "DJ Maphorisa", "Musa Keys", "Focalistic", "DBN Gogo", "Major League Djz"],
        "deny_name_contains": ["remix", "edit", "radio edit"],
        "min_year": 2018, "max_year": 2024, "popularity_min": 5, "popularity_max": 85
    },

    # ===== CLASSICAL MISSING =====
    "baroque": {
        "require_artist_genres_any": ["baroque", "classical"],
        "deny_artist_genres_any": ["romantic", "modern classical", "contemporary classical"],
        "whitelist_artists": ["J. S. Bach", "George Frideric Handel", "Antonio Vivaldi", "Domenico Scarlatti"],
        "deny_name_contains": ["remix", "edit", "rework"],
        "popularity_min": 5, "popularity_max": 100
    },
    "romantic": {
        "require_artist_genres_any": ["romantic", "classical"],
        "deny_artist_genres_any": ["baroque", "minimalism"],
        "whitelist_artists": ["Chopin", "Tchaikovsky", "Brahms", "Liszt", "Mahler", "Dvořák"],
        "deny_name_contains": ["remix", "edit", "rework"],
        "min_year": 1800, "max_year": 1915, "popularity_min": 5, "popularity_max": 85
    },
    "modern classical": {
        "require_artist_genres_any": ["modern classical", "contemporary classical", "neoclassical"],
        "deny_artist_genres_any": ["baroque", "romantic"],
        "whitelist_artists": ["Philip Glass", "Max Richter", "Michael Nyman", "Arvo Pärt", "Steve Reich", "Ólafur Arnalds"],
        "deny_name_contains": ["remix", "edit", "rework"],
        "min_year": 1965, "max_year": 2024, "popularity_min": 5, "popularity_max": 85
    },
}

# -------- Matching logic --------
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
    artist = (track.get("artists") or [""])[0].lower()
    name = (track.get("name") or "").lower()

    # Hard denies (with word boundary matching to avoid false positives)
    deny = rules.get("deny_artist_genres_any") or []
    if deny:
        for d in deny:
            # Use word boundaries so "punk" doesn't match "post-punk"
            deny_pattern = re.compile(rf'\b{re.escape(d.lower())}\b')
            if any(deny_pattern.search(g) for g in a_gen):
                return False

    # Require at least one (with word boundary matching for consistency)
    req = rules.get("require_artist_genres_any") or []
    if req:
        found = False
        for r in req:
            # Use word boundaries for more precise matching
            req_pattern = re.compile(rf'\b{re.escape(r.lower())}\b')
            if any(req_pattern.search(g) for g in a_gen):
                found = True
                break
        if not found:
            return False

    # Name denies (check BEFORE whitelist so even whitelisted artists can be filtered for live/remix)
    deny_tokens = rules.get("deny_name_contains") or []
    if deny_tokens:
        for t in deny_tokens:
            if t.lower() in name:
                return False

    # Artist name denies
    deny_artist_tokens = rules.get("deny_artist_contains") or []
    if deny_artist_tokens:
        for t in deny_artist_tokens:
            if t.lower() in artist:
                return False

    # Whitelist bypass
    whitelist = rules.get("whitelist_artists") or []
    if whitelist:
        if any(w.lower() in artist for w in whitelist):
            return True

    # Year gates
    y = track.get("release_year")
    try:
        y = int(y) if y else None
    except:
        y = None
    
    if y:
        min_year = rules.get("min_year")
        max_year = rules.get("max_year")
        if min_year and y < min_year:
            return False
        if max_year and y > max_year:
            return False

    # Popularity gates
    pop = float(track.get("popularity", 0) or 0)
    pmin = rules.get("popularity_min")
    pmax = rules.get("popularity_max")
    if pmin and pop < float(pmin):
        return False
    if pmax and pop > float(pmax):
        return False

    return True

def gather_playable_genres(tree):
    genres = []
    def walk(node):
        if not isinstance(node, dict): return
        seed = node.get("_seeds")
        if isinstance(seed, str) and seed != "__synthetic__":
            genres.append(seed)  # keep original string
        subs = node.get("subgenres")
        if isinstance(subs, dict):
            for v in subs.values():
                walk(v)

    # Actually walk the tree!
    for root_node in tree.values():
        walk(root_node)

    # unique preserve order
    seen, ordered = set(), []
    for g in genres:
        if g not in seen:
            seen.add(g)
            ordered.append(g)
    return ordered


def build_parent_maps(tree: Dict[str, Any]) -> Tuple[Dict[str, str], Dict[str, Set[str]]]:
    genre_to_parent: Dict[str, str] = {}
    parent_to_desc: Dict[str, Set[str]] = {}

    def walk(node: Dict[str, Any], parent_seed: str = ""):
        seed_raw = node.get("_seeds")
        this_seed = seed_raw if isinstance(seed_raw, str) and seed_raw.strip() else None

        subs = node.get("subgenres")
        if isinstance(subs, dict):
            parent_label = this_seed or parent_seed
            if parent_label and parent_label not in parent_to_desc:
                parent_to_desc[parent_label] = set()

            for child in subs.values():
                if not isinstance(child, dict):
                    continue
                child_raw = child.get("_seeds")
                child_seed = child_raw if isinstance(child_raw, str) and child_raw.strip() else None
                if child_seed:
                    genre_to_parent[child_seed] = parent_label or ""
                    if parent_label:
                        parent_to_desc[parent_label].add(child_seed)
                walk(child, parent_label)

    walk(tree)
    return genre_to_parent, parent_to_desc

PLAYABLE_GENRES = gather_playable_genres(GENRE_TREE)
print(f"[sanity] gathered {len(PLAYABLE_GENRES)} playable genres")  # must be > 0
print("[sanity] first 10:", PLAYABLE_GENRES[:10])
if not PLAYABLE_GENRES:
    raise RuntimeError("No playable genres. GENRE_TREE or gather_playable_genres is wrong.")

GENRE_TO_PARENT, PARENT_TO_DESC = build_parent_maps(GENRE_TREE)

# -------- Seed selection --------
results: Dict[str, List[Dict[str, Any]]] = {}
used_track_ids_by_parent: Dict[str, Set[str]] = defaultdict(set)
used_artists_by_parent: Dict[str, Set[str]] = defaultdict(set)

def proto_score(target_genre: str, t: Dict[str, Any]) -> float:
    """
    Score a track's fitness for a target genre.

    Combines exact genre matches, artist whitelists, popularity plateau,
    and contamination penalties to rank candidates.
    """
    tags = norm_tags(t.get("artist_genres") or t.get("genres"))
    target = target_genre.lower()
    artists = [a.lower() for a in (t.get("artists") or [])]

    # Exact genre match bonus
    exact = CONFIG['score_exact_match'] if any(g == target for g in tags) else 0.0

    # Check genre-specific rules
    rules = GENRE_RULES.get(target, {})
    whitelist = [w.lower() for w in rules.get("whitelist_artists", [])]
    boost = [b.lower() for b in rules.get("boost_artist_contains", [])]

    whitelist_bonus = CONFIG['score_whitelist_bonus'] if any(w in a for a in artists for w in whitelist) else 0.0
    boost_bonus = CONFIG['score_boost_bonus'] if any(b in a for a in artists for b in boost) else 0.0

    # Popularity scoring with plateau function
    pop = float(t.get("popularity", 0))
    pop_score = pop_component(
        pop,
        center=CONFIG['pop_center'],
        plateau=CONFIG['pop_plateau'],
        width=CONFIG['pop_width'],
        weight=CONFIG['pop_weight']
    )

    # Contamination from undesirable genres
    bad_tokens = {"dance pop", "pop", "electropop", "soundtrack"}
    contam = CONFIG['score_contamination_penalty'] if any(any(bt in g for g in tags) for bt in bad_tokens) else 0.0

    # Depth bonus: reward multiple matching tags
    allow = [a.lower() for a in rules.get("allow_artist_genres_any", [])]
    deny = [d.lower() for d in rules.get("deny_artist_genres_any", [])]
    match_bonus = min(1.2, 0.4 * sum(g in tags for g in allow))
    deny_penalty = -0.5 if any(d in tags for d in deny) else 0.0

    # Small random noise for tiebreaking
    noise = random.random() * CONFIG['score_random_noise']

    return exact + whitelist_bonus + boost_bonus + pop_score + contam + match_bonus + deny_penalty + noise

print(f"Processing {len(PLAYABLE_GENRES)} genres...", flush=True)
processing_start = time.time()

print("Indexing tracks by genre...", flush=True)
tracks_by_genre: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
for track in tracks:
    tid = track.get("uri") or track.get("id")
    if tid in TRACK_DENY_URIS:
        continue
    track_genres = norm_tags(track.get('artist_genres') or track.get('genres'))
    if not track_genres:
        continue
    for tg in track_genres:
        tracks_by_genre[tg].append(track)

print(f"Indexed {len(tracks_by_genre)} genre buckets", flush=True)
print("Selecting seeds...", flush=True)

# Define globals once, outside the loop but inside main runtime scope
global_seen_ids: Set[str] = set()
global_seen_artists: Set[str] = set()

results: Dict[str, List[Dict[str, Any]]] = {}



for idx, genre in enumerate(PLAYABLE_GENRES, 1):
    if idx % 20 == 0:
        print(f"  {idx}/{len(PLAYABLE_GENRES)}...", flush=True)

    genre_lower = genre.lower()

    # gather candidates from all matching genre index keys
    # e.g., "dubstep" should match "melodic dubstep", "gaming dubstep", etc.
    candidates = []
    genre_pattern = re.compile(rf"\b{re.escape(genre_lower)}\b")
    for index_key in tracks_by_genre.keys():
        if genre_pattern.search(index_key):
            for track in tracks_by_genre[index_key]:
                tid = track.get("uri") or track.get("id")
                track_genres = norm_tags(track.get('artist_genres') or track.get('genres'))
                if not tid:
                    continue
                if not genre_match(genre, track_genres):
                    continue
                if not passes_rules(genre, track):
                    continue
                candidates.append(track)

    if not candidates:
        results[genre] = []
        continue

    # per-genre local de-dupe for cleanliness
    seen_ids = set()
    seen_artists = set()
    unique = []
    for t in candidates:
        tid = t.get("uri") or t.get("id")
        artist = ((t.get("artists") or [""])[0] or "").strip()
        artist_l = artist.lower()
        if not tid or not artist:
            continue
        if tid in seen_ids or artist_l in seen_artists:
            continue
        seen_ids.add(tid)
        seen_artists.add(artist_l)
        unique.append(t)

    if not unique:
        results[genre] = []
        continue

    unique.sort(key=lambda t: proto_score(genre, t), reverse=True)

    # final pick with global de-dupe only
    top_k = []
    for t in unique:
        if len(top_k) >= CONFIG['seeds_per_genre']:
            break
        tid = t.get("uri") or t.get("id")
        artist = ((t.get("artists") or [""])[0] or "").strip().lower()
        if tid in global_seen_ids or artist in global_seen_artists:
            continue
        top_k.append(t)
        global_seen_ids.add(tid)
        global_seen_artists.add(artist)

    results[genre] = top_k


processing_time = time.time() - processing_start
print(f"\n✓ Completed in {processing_time:.1f}s\n", flush=True)

# Define feature fields for both regular and synthetic genres
FEATURE_FIELDS = ["danceability","energy","speechiness","acousticness","valence","popularity","instrumentalness"]

# -------- Synthetic genre seed selection --------
# Selects 5 UNIQUE seeds for synthetic parent genres using:
# - Aggregate audio features from all child seeds
# - Candidate tracks matching ANY child genre tag
# - Global deduplication (no track/artist overlap with any other genre)
# - Representative diversity (at least 1 from each child if possible)
#
print("Selecting seeds for synthetic parent genres...", flush=True)

def gather_synthetic_genres(tree, path=""):
    """Find all nodes with _seeds: '__synthetic__' and their direct children."""
    synthetic = []
    def walk(node, node_path, node_name):
        if not isinstance(node, dict):
            return
        seed = node.get("_seeds")
        if seed == "__synthetic__":
            # Find direct children with real seeds
            children_seeds = []
            subs = node.get("subgenres", {})
            if isinstance(subs, dict):
                for child_name, child_node in subs.items():
                    if isinstance(child_node, dict):
                        child_seed = child_node.get("_seeds")
                        if isinstance(child_seed, str) and child_seed != "__synthetic__":
                            children_seeds.append(child_seed)
            if children_seeds:
                synthetic.append((node_path, node_name, children_seeds))

        # Continue walking
        subs = node.get("subgenres", {})
        if isinstance(subs, dict):
            for child_name, child_node in subs.items():
                child_path = child_name if not node_path else f"{node_path}/{child_name}"
                walk(child_node, child_path, child_name)

    for root_name, root_node in tree.items():
        walk(root_node, root_name, root_name)

    return synthetic

def compute_aggregate_features(child_genres):
    """Compute aggregate audio features from all child genre seeds."""
    all_tracks = []
    for child in child_genres:
        all_tracks.extend(results.get(child, []))

    if not all_tracks:
        return None

    # Compute mean of all audio features
    feature_sums = defaultdict(float)
    feature_counts = defaultdict(int)

    for track in all_tracks:
        for feat in FEATURE_FIELDS:
            val = track.get(feat)
            if val is not None:
                try:
                    feature_sums[feat] += float(val)
                    feature_counts[feat] += 1
                except:
                    pass
        # Include tempo
        tempo = track.get("tempo")
        if tempo is not None:
            try:
                feature_sums["tempo_norm"] += tempo_to_norm(float(tempo))
                feature_counts["tempo_norm"] += 1
            except:
                pass

    aggregate = {}
    for feat, total in feature_sums.items():
        if feature_counts[feat] > 0:
            aggregate[feat] = total / feature_counts[feat]

    return aggregate

def feature_distance(track, target_features):
    """Compute Euclidean distance between track and target features."""
    distance = 0.0
    count = 0

    for feat in FEATURE_FIELDS:
        target_val = target_features.get(feat)
        track_val = track.get(feat)
        if target_val is not None and track_val is not None:
            try:
                distance += (float(track_val) - float(target_val)) ** 2
                count += 1
            except:
                pass

    # Include tempo
    if "tempo_norm" in target_features:
        tempo = track.get("tempo")
        if tempo is not None:
            try:
                tempo_norm = tempo_to_norm(float(tempo))
                distance += (tempo_norm - target_features["tempo_norm"]) ** 2
                count += 1
            except:
                pass

    return math.sqrt(distance / count) if count > 0 else float('inf')

# Create mapping of path -> display name for build_manifest lookup
synthetic_path_to_name = {}
synthetic_genres = gather_synthetic_genres(GENRE_TREE)
print(f"Found {len(synthetic_genres)} synthetic parent genres", flush=True)

for full_path, display_name, child_seeds in synthetic_genres:
    synthetic_path_to_name[full_path] = display_name

    # Compute aggregate features from all children
    aggregate_features = compute_aggregate_features(child_seeds)
    if not aggregate_features:
        results[display_name] = []
        continue

    # Gather candidate tracks matching ANY child genre
    candidates = []
    for child_genre in child_seeds:
        child_genre_lower = child_genre.lower()
        genre_pattern = re.compile(rf"\b{re.escape(child_genre_lower)}\b")

        for index_key in tracks_by_genre.keys():
            if genre_pattern.search(index_key):
                for track in tracks_by_genre[index_key]:
                    tid = track.get("uri") or track.get("id")
                    if not tid or tid in global_seen_ids:
                        continue

                    track_genres = norm_tags(track.get('artist_genres') or track.get('genres'))
                    if not genre_match(child_genre, track_genres):
                        continue
                    if not passes_rules(child_genre, track):
                        continue

                    # Add track with metadata for selection
                    candidates.append({
                        "track": track,
                        "child_genre": child_genre,
                        "distance": feature_distance(track, aggregate_features)
                    })

    # Remove duplicates within candidates
    seen_candidate_ids = set()
    unique_candidates = []
    for c in candidates:
        tid = c["track"].get("uri") or c["track"].get("id")
        if tid not in seen_candidate_ids:
            seen_candidate_ids.add(tid)
            unique_candidates.append(c)

    # Sort by distance to aggregate
    unique_candidates.sort(key=lambda c: c["distance"])

    # Select 5 seeds ensuring diversity (at least 1 per child if possible)
    selected = []
    child_representation = {child: 0 for child in child_seeds}

    # First pass: ensure at least 1 from each child
    for child in child_seeds:
        if len(selected) >= 5:
            break
        for c in unique_candidates:
            if c["child_genre"] == child:
                track = c["track"]
                tid = track.get("uri") or track.get("id")
                artist = ((track.get("artists") or [""])[0] or "").strip().lower()

                if tid not in global_seen_ids and artist not in global_seen_artists:
                    selected.append(track)
                    global_seen_ids.add(tid)
                    global_seen_artists.add(artist)
                    child_representation[child] += 1
                    unique_candidates.remove(c)
                    break

    # Second pass: fill remaining slots with closest matches
    for c in unique_candidates:
        if len(selected) >= 5:
            break
        track = c["track"]
        tid = track.get("uri") or track.get("id")
        artist = ((track.get("artists") or [""])[0] or "").strip().lower()

        if tid not in global_seen_ids and artist not in global_seen_artists:
            selected.append(track)
            global_seen_ids.add(tid)
            global_seen_artists.add(artist)

    results[display_name] = selected
    print(f"  ✓ {display_name}: {len(selected)}/5 seeds selected", flush=True)

print(f"✓ Synthetic genre selection complete\n", flush=True)

# -------- Feature computation --------
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

print(f"Building genre manifest...", flush=True)
manifest_start = time.time()

def build_manifest(tree: Dict[str, Any], genre_path: str = "") -> Dict[str, Any]:
    result: Dict[str, Any] = {}
    sub = tree.get("subgenres")
    built_sub: Dict[str, Any] = {}
    if isinstance(sub, dict):
        for child_name, child_node in sub.items():
            if isinstance(child_node, dict):
                child_path = child_name if not genre_path else f"{genre_path}/{child_name}"
                child_built = build_manifest(child_node, child_path)
                built_sub[child_name] = child_built

    seeds_key = tree.get("_seeds")
    seeds_payload = []
    node_features = {}
    node_median_year = None

    if isinstance(seeds_key, str):
        # For synthetic genres, look up the display name from the path mapping
        if seeds_key == "__synthetic__":
            lookup_key = synthetic_path_to_name.get(genre_path, genre_path)
        else:
            lookup_key = seeds_key
        seeds = results.get(lookup_key, [])
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

    if not node_features and built_sub:
        child_feat, child_year = aggregate_features_from_children(built_sub)
        if child_feat:
            node_features = child_feat
        if child_year is not None:
            node_median_year = child_year

    if node_features:
        for k in FEATURE_FIELDS:
            node_features.setdefault(k, None)
        node_features.setdefault("tempo_bpm", None)
        node_features.setdefault("tempo_norm", None)

    if seeds_payload:
        result["seeds"] = seeds_payload
    if node_features:
        result["features"] = node_features
    if node_median_year is not None:
        result["median_year"] = node_median_year
    if built_sub:
        result["subgenres"] = built_sub

    return result

manifest = {}
for genre_name, genre_node in GENRE_TREE.items():
    if isinstance(genre_node, dict):
        manifest[genre_name] = build_manifest(genre_node, genre_name)

manifest_build_time = time.time() - manifest_start
print(f"✓ Manifest structure built in {manifest_build_time:.1f}s", flush=True)

print(f"Computing global statistics...", flush=True)
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
    "tempo_norm": {"min_bpm": int(CONFIG['min_bpm']), "max_bpm": int(CONFIG['max_bpm'])},
    "means": means,
    "stddevs": stddevs,
    "quantiles": quantiles,
    "display": {
        "feature_angles": ["danceability","energy","speechiness","acousticness","valence","tempo_norm","popularity","instrumentalness"],
        "projection_scale": 180,
        "exaggeration_default": 1.2,
        "speechiness_contrast_gamma": 1.3
    }
}

manifest["build"] = {
    "schema_version": "1",
    "dataset_id": CONFIG['dataset_id'],
    "track_count": len(tracks),
    "sample_size_per_genre": CONFIG['seeds_per_genre'],
    "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
}

print(f"Saving manifest to file...", flush=True)
with open(CONFIG['output_file'], 'w', encoding='utf-8') as f:
    json.dump(manifest, f, indent=2, ensure_ascii=False)

total_time = time.time() - start_time
print("\n" + "=" * 60, flush=True)
print(f"✓ SAVED: {CONFIG['output_file']}", flush=True)
print(f"✓ Total execution time: {total_time:.1f}s", flush=True)
print("=" * 60, flush=True)

print("\n" + "=" * 60, flush=True)
print("REPORT:", flush=True)
print("=" * 60, flush=True)
total_found = 0
issues = []

target_count = CONFIG['seeds_per_genre']
for genre in PLAYABLE_GENRES:
    count = len(results.get(genre, []))
    total_found += count
    status = "✓" if count == target_count else "⚠️" if count > 0 else "✗"
    if count > 0:
        avg_pop = sum(t.get('popularity', 0) for t in results[genre]) / count
        print(f"{status} {genre:<30} {count}/{target_count} tracks (avg pop: {avg_pop:.0f})")
    if 0 < count < target_count:
        issues.append((genre, count))

# Report synthetic genres
print(f"\nSYNTHETIC PARENT GENRES:")
for full_path, display_name, child_seeds in synthetic_genres:
    count = len(results.get(display_name, []))
    if count > 0:
        total_found += count
        avg_pop = sum(t.get('popularity', 0) for t in results[display_name]) / count
        print(f"✓ {display_name:<30} {count} tracks (avg pop: {avg_pop:.0f})")

print(f"\nTotal seed selections: {total_found}", flush=True)
unique_artists = set()
for lst in results.values():
    for t in lst:
        a = (t.get('artists') or [''])[0]
        if a:
            unique_artists.add(a)
print(f"Total unique artists across all seeds: {len(unique_artists)}", flush=True)

if issues:
    print(f"\n⚠️  GENRES WITH LOW COVERAGE:")
    for genre, count in issues:
        print(f"   {genre}: only {count} track(s)")

print("\n" + "=" * 60, flush=True)
print("URIS FOR BATCH EXPORT:", flush=True)
print("=" * 60, flush=True)

# Export both regular and synthetic genres
all_genres_to_export = list(PLAYABLE_GENRES) + [display_name for _, display_name, _ in synthetic_genres]
for genre in all_genres_to_export:
    if results.get(genre):
        print(f"\n# {genre.upper()}")
        for track in results[genre]:
            artist = (track.get('artists') or ['Unknown'])[0]
            print(f"{track.get('uri')}  // {artist} — {track.get('name')}")

# Write clean URI list for bulk import
uris_file = "seed_uris.txt"
with open(uris_file, 'w', encoding='utf-8') as f:
    for genre in all_genres_to_export:
        if results.get(genre):
            for track in results[genre]:
                f.write(f"{track.get('uri')}\n")

print(f"\n✓ Clean URI list saved to: {uris_file}", flush=True)
print(f"  Total URIs: {sum(len(results.get(g, [])) for g in all_genres_to_export)}", flush=True)
