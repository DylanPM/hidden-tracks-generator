

import json
import re
import math
from collections import defaultdict, Counter
from typing import Any, Dict, Tuple, List, Set
from datetime import datetime, timezone
import random
import time
import os
random.seed(42)

# -------- Startup and validation --------
print("=" * 60, flush=True)
print("Starting Genre Constellation Manifest Generator", flush=True)
print("=" * 60, flush=True)

DATA_FILE = 'server/data/prepped.json'
if not os.path.exists(DATA_FILE):
    print(f"❌ ERROR: Input file not found: {DATA_FILE}", flush=True)
    print("Please ensure the data file exists before running this script.", flush=True)
    exit(1)

print(f"✓ Found input file: {DATA_FILE}", flush=True)
file_size_mb = os.path.getsize(DATA_FILE) / (1024 * 1024)
print(f"✓ File size: {file_size_mb:.1f} MB", flush=True)

# -------- Load dataset --------
start_time = time.time()
print(f"\nLoading dataset...", flush=True)
with open(DATA_FILE, 'r', encoding='utf-8') as f:
    tracks = json.load(f)

load_time = time.time() - start_time
print(f"✓ Loaded {len(tracks)} tracks in {load_time:.1f}s\n", flush=True)

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
    "spotify:track:69yfbpvmkIaB10msnKT7Q5",  # Imagine Dragons — Radioactive
    "spotify:track:4VyU9Tg4drTj2mOUZHSK2u",  # Deniece Williams — Let's Hear It for the Boy - From "Footloose" Original Soundtrack
    "spotify:track:6JyEh4kl9DLwmSAoNDRn5b",  # KIDS SEE GHOSTS — 4th Dimension
    "spotify:track:3V1H6liHwCDcWeqdPJabOM",  # Stone Sour — Wicked Game - Acoustic; Live
    "spotify:track:1VzhfMEGIIkn5hFITMJzW1",  # Guru — Loungin
    "spotify:track:7GHKA8GIMcND6c5nN1sFnD",  # Tom Jones — Sexbomb
    
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
        "max_year": 1980
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
        "deny_artist_genres_any": ["dance pop","pop","west coast"]
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
    "soul": {
    "require_artist_genres_any": ["soul", "neo soul", "motown"],
    "deny_artist_genres_any": ["hip hop", "rap", "trap"]
    },
    "motown": {
        "require_artist_genres_any": ["motown", "soul"],
        "deny_artist_genres_any": ["hip hop", "rap"]
    },
    "conscious hip hop": {
        "require_artist_genres_any": ["hip hop", "conscious hip hop", "rap"],
        "deny_artist_genres_any": ["rock", "alternative rock", "pop rock"]
    },
    "west coast rap": {
        "require_artist_genres_any": ["west coast", "g funk", "gangsta rap"],
        "deny_artist_genres_any": ["east coast", "boom bap"]
    }
}

# --- optional patches for special cases ---
GENRE_RULES.setdefault("shoegaze", {}).update({
    "whitelist_artists": ["My Bloody Valentine","Slowdive","Ride","Lush","Chapterhouse","Medicine"],
    "deny_name_contains": ["remix","live","edit"]
})

GENRE_RULES.setdefault("east coast hip hop", {}).update({
    "whitelist_artists": ["Nas","Mobb Deep","Wu-Tang Clan","A Tribe Called Quest","The Notorious B.I.G."],
    "deny_name_contains": ["remix","edit","12\"","dub","re-drum","re drum","re-edit","re edit","instrumental"],
})

GENRE_RULES.setdefault("disco", {}).update({
    "deny_name_contains": ["remix","edit","12\"","dub","re-drum","re drum","re-edit","re edit","instrumental"],
    "min_year": 1974,
    "max_year": 1985
})

GENRE_RULES.setdefault("metal", {}).update({
    "boost_artist_contains": ["Metallica","Megadeth","Anthrax","Slayer","Pantera",
                              "Iron Maiden","Judas Priest","Sepultura","Motörhead",
                              "Motorhead","Dio","Black Sabbath","Opeth","Testament"]
})
GENRE_RULES.setdefault("conscious hip hop", {}).update({
    "boost_artist_contains": ["Common","Mos Def","Blackstar"]
})

# --- targeted tightening / recall patches (paste after GENRE_RULES definition) ---

# METAL FAMILY
GENRE_RULES.setdefault("metal", {}).update({
    # keep core metal, push out generic classic/hard rock bleed
    "deny_artist_genres_any": list(set(
        GENRE_RULES.get("metal", {}).get("deny_artist_genres_any", [])
        + ["classic rock","hard rock"]
    )),
    "boost_artist_contains": list(set(
        GENRE_RULES.get("metal", {}).get("boost_artist_contains", [])
        + ["Metallica","Megadeth","Anthrax","Slayer","Pantera",
           "Iron Maiden","Judas Priest","Sepultura","Motörhead","Motorhead",
           "Dio","Black Sabbath","Opeth","Testament"]
    ))
})
GENRE_RULES.setdefault("thrash metal", {}).update({
    "require_artist_genres_any": list(set(
        GENRE_RULES["thrash metal"].get("require_artist_genres_any", []) + ["crossover thrash"]
    ))
})
GENRE_RULES.setdefault("death metal", {}).update({
    "require_artist_genres_any": list(set(
        GENRE_RULES["death metal"].get("require_artist_genres_any", [])
        + ["melodic death metal","technical death metal"]
    )),
    "deny_artist_genres_any": ["gothic metal","djent","industrial metal"]
})
GENRE_RULES.setdefault("progressive metal", {}).update({
    "deny_artist_genres_any": list(set(
        GENRE_RULES["progressive metal"].get("deny_artist_genres_any", []) + ["power metal"]
    ))
})

# PUNK LANES
GENRE_RULES.setdefault("punk", {}).update({
    "deny_artist_genres_any": list(set(
        GENRE_RULES["punk"].get("deny_artist_genres_any", [])
        + ["ska","ska punk","new wave","classic rock"]
    ))
})
GENRE_RULES.setdefault("post-punk", {}).update({
    "require_artist_genres_any": list(set(
        GENRE_RULES["post-punk"].get("require_artist_genres_any", [])
        + ["gothic rock","coldwave","no wave"]
    )),
    "deny_artist_genres_any": list(set(
        GENRE_RULES["post-punk"].get("deny_artist_genres_any", [])
        + ["punk","pop punk","alternative rock","grunge"]
    ))
})

# SHOEGAZE
GENRE_RULES.setdefault("shoegaze", {}).update({
    "require_artist_genres_any": list(set(
        GENRE_RULES["shoegaze"].get("require_artist_genres_any", [])
        + ["nu gaze","dream pop"]
    )),
    "whitelist_artists": list(set(
        GENRE_RULES["shoegaze"].get("whitelist_artists", [])
        + ["My Bloody Valentine","Slowdive","Ride","Lush","Chapterhouse",
           "Pale Saints","Nothing","Whirr","Medicine"]
    )),
    "deny_name_contains": list(set(
        GENRE_RULES["shoegaze"].get("deny_name_contains", []) + ["remix","live","edit"]
    ))
})

# GRUNGE
GENRE_RULES.setdefault("grunge", {}).update({
    "require_artist_genres_any": ["grunge","post-grunge","seattle sound"],
    "deny_artist_genres_any": ["industrial rock","alternative metal","acoustic"]
})

# POST-ROCK
GENRE_RULES.setdefault("post-rock", {}).update({
    "require_artist_genres_any": ["post-rock","instrumental post-rock"],
    "deny_artist_genres_any": ["idm","ambient","electronica"]
})

# PSYCHEDELIC / HARD ROCK
GENRE_RULES.setdefault("psychedelic rock", {}).update({
    "deny_artist_genres_any": list(set(
        GENRE_RULES["psychedelic rock"].get("deny_artist_genres_any", [])
        + ["classic rock","soft rock","blues rock"]
    ))
})
GENRE_RULES.setdefault("hard rock", {}).update({
    "require_artist_genres_any": ["hard rock","arena rock","glam metal","classic rock"],
    "deny_artist_genres_any": list(set(
        GENRE_RULES["hard rock"].get("deny_artist_genres_any", [])
        + ["industrial metal","psychedelic rock","blues"]
    ))
})

# HOUSE / TECHNO CLUSTER
GENRE_RULES.setdefault("house", {}).update({
    "require_artist_genres_any": ["house","funky house","disco house"],
    "deny_artist_genres_any": ["hip hop","trap","soundtrack"]
})
GENRE_RULES.setdefault("tech house", {}).update({
    "require_artist_genres_any": ["tech house"]  # tighten: drop plain "house"
})
GENRE_RULES.setdefault("progressive house", {}).update({
    "require_artist_genres_any": ["progressive house"],
    "deny_artist_genres_any": ["trance","uplifting trance","eurotrance"]
})
GENRE_RULES.setdefault("acid house", {}).update({
    "require_artist_genres_any": ["acid house"],
    "min_year": min(1987, GENRE_RULES["acid house"].get("min_year", 1987)),
    "max_year": 1993,
    "whitelist_artists": ["Phuture","DJ Pierre","Armando","Adonis","Hardfloor","Josh Wink"]
})
GENRE_RULES.setdefault("techno", {}).update({
    "require_artist_genres_any": ["techno","detroit techno","minimal techno","hard techno","berlin techno"],
    "deny_artist_genres_any": ["deep house","house"]
})
GENRE_RULES.setdefault("breakbeat", {}).update({
    "require_artist_genres_any": ["breakbeat","big beat","breaks","nu skool breaks"]
})
GENRE_RULES.setdefault("dubstep", {}).update({
    "require_artist_genres_any": ["dubstep","brostep","uk dubstep"],
    "deny_artist_genres_any": ["future bass","progressive house","electro house"],
    "whitelist_artists": ["Skream","Benga","Mala","Burial","Rusko"]
})

# HIP HOP GEOGRAPHY / SUBSTYLES
GENRE_RULES.setdefault("east coast hip hop", {}).update({
    "require_artist_genres_any": ["east coast hip hop","boom bap","new york drill"],
    "deny_artist_genres_any": list(set(
        GENRE_RULES["east coast hip hop"].get("deny_artist_genres_any", [])
        + ["west coast rap","g funk","southern hip hop","chicago rap","uk hip hop"]
    )),
    "whitelist_artists": list(set(
        GENRE_RULES["east coast hip hop"].get("whitelist_artists", [])
        + ["Nas","Mobb Deep","Wu-Tang Clan","A Tribe Called Quest","The Notorious B.I.G.",
           "Rakim","Gang Starr","Big L","Mos Def","Black Star","Busta Rhymes","Eric B. & Rakim",
           "Big Daddy Kane","MF DOOM","Joey Bada$$","Boot Camp Clik","De La Soul"]
    ))
})
GENRE_RULES.setdefault("west coast rap", {}).update({
    "require_artist_genres_any": ["west coast rap","g funk","gangsta rap"],
    "deny_artist_genres_any": list(set(
        GENRE_RULES["west coast rap"].get("deny_artist_genres_any", [])
        + ["east coast hip hop","boom bap","southern hip hop"]
    ))
})
GENRE_RULES.setdefault("conscious hip hop", {}).update({
    "require_artist_genres_any": ["conscious hip hop","jazz rap","alternative hip hop"]
})
GENRE_RULES.setdefault("underground hip hop", {}).update({
    "deny_artist_genres_any": list(set(
        GENRE_RULES["underground hip hop"].get("deny_artist_genres_any", [])
        + ["neo soul","r&b","contemporary r&b"]
    ))
})

# R&B / SOUL
GENRE_RULES.setdefault("r&b", {}).update({
    "deny_artist_genres_any": ["rap","hip hop","trap","drill"]
})
GENRE_RULES.setdefault("quiet storm", {}).update({
    "require_artist_genres_any": ["quiet storm"]
})
GENRE_RULES.setdefault("motown", {}).update({
    "require_artist_genres_any": list(set(
        GENRE_RULES["motown"].get("require_artist_genres_any", []) + ["motown"]
    ))
})
GENRE_RULES.setdefault("funk", {}).update({
    "require_artist_genres_any": list(set(
        GENRE_RULES["funk"].get("require_artist_genres_any", []) + ["jazz funk"]
    )),
    "deny_artist_genres_any": list(set(
        GENRE_RULES["funk"].get("deny_artist_genres_any", [])
        + ["americana","roots rock","alt rock","alternative rock"]
    ))
})
GENRE_RULES.setdefault("funk rock", {}).update({
    "deny_artist_genres_any": list(set(
        GENRE_RULES["funk rock"].get("deny_artist_genres_any", [])
        + ["pop rock","post-grunge"]
    ))
})

# JAZZ STACK
GENRE_RULES.setdefault("bebop", {}).update({
    "deny_artist_genres_any": ["swing","cool jazz","vocal jazz"]
})
GENRE_RULES.setdefault("cool jazz", {}).update({
    "require_artist_genres_any": list(set(
        GENRE_RULES["cool jazz"].get("require_artist_genres_any", []) + ["west coast jazz"]
    )),
    "deny_artist_genres_any": ["bebop","hard bop","vocal jazz"]
})
GENRE_RULES.setdefault("hard bop", {}).update({
    "require_artist_genres_any": ["hard bop"],
    "deny_artist_genres_any": ["cool jazz","swing","vocal jazz"]
})
GENRE_RULES.setdefault("jazz fusion", {}).update({
    "require_artist_genres_any": list(set(
        GENRE_RULES["jazz fusion"].get("require_artist_genres_any", []) + ["jazz-rock"]
    )),
    "deny_artist_genres_any": list(set(
        GENRE_RULES["jazz fusion"].get("deny_artist_genres_any", [])
        + ["soundtrack","synthwave","new age"]
    ))
})
GENRE_RULES.setdefault("smooth jazz", {}).update({
    "require_artist_genres_any": ["smooth jazz"],
    "deny_artist_genres_any": ["r&b","contemporary r&b","neo soul"]
})
GENRE_RULES.setdefault("avant-garde jazz", {}).update({
    "require_artist_genres_any": ["avant-garde jazz","free jazz","free improvisation"]
})

# LATIN SET
GENRE_RULES.setdefault("bossa nova", {}).update({
    "require_artist_genres_any": ["bossa nova"],
    "whitelist_artists": ["Antonio Carlos Jobim","João Gilberto","Astrud Gilberto","Marcos Valle","Stan Getz"]
})
GENRE_RULES.setdefault("salsa", {}).update({
    "require_artist_genres_any": ["salsa"],
    "deny_artist_genres_any": ["rap","reggaeton","latin trap"]
})
GENRE_RULES.setdefault("mambo", {}).update({
    "require_artist_genres_any": ["mambo"]
})
GENRE_RULES.setdefault("soca", {}).update({
    "require_artist_genres_any": ["soca"],
    "deny_artist_genres_any": ["dancehall","reggae","lovers rock"]
})

# --- Corrections for misfiring buckets ---

GENRE_RULES.setdefault("east coast hip hop", {}).update({
    "require_artist_genres_any": [
        "east coast hip hop","boom bap","nyc rap","new york drill","queens hip hop","brooklyn drill"
    ],
    "deny_artist_genres_any": [
        "west coast rap","southern hip hop","uk hip hop","alternative hip hop","dance pop","electropop"
    ],
    "deny_name_contains": ["remix","edit","instrumental"]
})

GENRE_RULES.setdefault("west coast rap", {}).update({
    "require_artist_genres_any": [
        "west coast rap","g funk","gangsta rap","la hip hop","bay area hip hop"
    ],
    "deny_artist_genres_any": ["east coast hip hop","southern hip hop","uk hip hop"]
})

GENRE_RULES.setdefault("rap", {}).update({
    "deny_artist_genres_any": ["dance pop","electropop","synthpop","latin pop","pop"],
    "deny_name_contains": ["remix","edit","radio edit","acoustic"]
})

GENRE_RULES.setdefault("funk", {}).update({
    "require_artist_genres_any": ["funk","p funk","pfunk","funk rock","jazz funk","soul funk"],
    "deny_artist_genres_any": ["edm","electro house","dance pop","big room","progressive house"],
    "deny_name_contains": ["remix","edit"],
    "min_year": 1965
})

GENRE_RULES.setdefault("ska", {}).update({
    "require_artist_genres_any": ["ska","ska punk","2 tone","third wave ska","rocksteady"],  # include rocksteady if you want early crossover
    "deny_artist_genres_any": ["roots reggae","reggae","dancehall","dub"],
})

GENRE_RULES.setdefault("afrobeat", {}).update({
    "require_artist_genres_any": ["afrobeat","nigerian afrobeat","afro funk"],
    "deny_artist_genres_any": ["soul","funk","r&b","afropop","dance pop"]
})

GENRE_RULES.setdefault("afropop", {}).update({
    "require_artist_genres_any": ["afropop","afrobeats","naija pop","alté"],
    "deny_artist_genres_any": ["afrobeat"]  # split Fela-style from pop Afrobeats
})

GENRE_RULES.setdefault("bossa nova", {}).update({
    "require_artist_genres_any": ["bossa nova","mpb"],
    "min_year": 1958,
    "deny_artist_genres_any": ["flamenco pop","latin pop","reggaeton"]
})

GENRE_RULES.setdefault("house", {}).update({
    "require_artist_genres_any": ["house","deep house","tech house","progressive house","electro house"],
    "deny_artist_genres_any": ["hip hop","trap","rap","dubstep"],
    "deny_name_contains": ["feat."]  # optional if you want fewer crossover vocals
})

GENRE_RULES.setdefault("progressive house", {}).update({
    "require_artist_genres_any": ["progressive house"],
    "deny_artist_genres_any": ["dance pop","big room","electro house"],
})

GENRE_RULES.setdefault("techno", {}).update({
    "require_artist_genres_any": ["techno","detroit techno","berlin school","minimal techno"],
    "deny_artist_genres_any": ["house","deep house","progressive house","trance"]
})

GENRE_RULES.setdefault("trance", {}).update({
    "require_artist_genres_any": ["trance","uplifting trance","progressive trance","eurotrance"],
    "deny_artist_genres_any": ["dance pop","big room","edm"]
})

GENRE_RULES.setdefault("shoegaze", {}).update({
    "require_artist_genres_any": ["shoegaze","nu gaze","dream pop"],
    "deny_artist_genres_any": ["psychedelic rock","garage rock","alt rock"],  # reduces BJM, etc.
})

GENRE_RULES.setdefault("grunge", {}).update({
    "require_artist_genres_any": ["grunge","post-grunge","seattle sound"],
    "deny_artist_genres_any": ["alternative country","cowpunk","punk blues"]
})

# Jazz splits
GENRE_RULES.setdefault("jazz fusion", {}).update({
    "require_artist_genres_any": ["jazz fusion","fusion","jazz rock","jazz funk"],
    "deny_artist_genres_any": ["hard bop","bebop","cool jazz"]
})
GENRE_RULES.setdefault("cool jazz", {}).update({
    "require_artist_genres_any": ["cool jazz","west coast jazz"],
    "deny_artist_genres_any": ["jazz funk","fusion","modal jazz","hard bop"]
})
GENRE_RULES.setdefault("hard bop", {}).update({
    "require_artist_genres_any": ["hard bop","post bop","bebop"]
})

# tighten trance vs prog house
GENRE_RULES.setdefault("progressive house", {}).update({
    "require_artist_genres_any": ["progressive house"],
    "deny_artist_genres_any": ["trance","uplifting trance","eurotrance"]
})
GENRE_RULES.setdefault("trance", {}).update({
    "require_artist_genres_any": ["trance","uplifting trance","progressive trance","eurotrance"]
})

# acid house must be acid
GENRE_RULES.setdefault("acid house", {}).update({
    "require_artist_genres_any": ["acid house","chicago house"],
    "deny_name_contains": ["radio edit","remix"]
})

# dub must be dub
GENRE_RULES.setdefault("dub", {}).update({
    "require_artist_genres_any": ["dub","dub reggae"],
    "deny_artist_genres_any": ["roots reggae","dancehall","reggae fusion"]
})

# dubstep must be dubstep
GENRE_RULES.setdefault("dubstep", {}).update({
    "require_artist_genres_any": ["dubstep","brostep","post-dubstep"],
    "deny_artist_genres_any": ["electro house","edm","future bass"]
})

# motown must be motown-era or tagged
GENRE_RULES.setdefault("motown", {}).update({
    "require_artist_genres_any": ["motown","northern soul","soul"],
    "max_year": 1985
})

# bossa nova should be bossa/mpb
GENRE_RULES.setdefault("bossa nova", {}).update({
    "require_artist_genres_any": ["bossa nova","mpb"],
    "deny_artist_genres_any": ["latin pop","flamenco pop","reggaeton"]
})

# shoegaze needs shoe/dream tags, but avoid generic psych/alt
GENRE_RULES.setdefault("shoegaze", {}).update({
    "require_artist_genres_any": ["shoegaze","nu gaze","dream pop"],
    "deny_artist_genres_any": ["psychedelic rock","garage rock","alternative rock"]
})

# soca should be clean soca
GENRE_RULES.setdefault("soca", {}).update({
    "require_artist_genres_any": ["soca","power soca","groovy soca"],
    "deny_artist_genres_any": ["dancehall","reggaeton"]
})

# thrash metal stricter
GENRE_RULES.setdefault("thrash metal", {}).update({
    "require_artist_genres_any": ["thrash metal","bay area thrash","crossover thrash"],
    "deny_artist_genres_any": ["classic metal","hard rock"]
})

# --- THRASH METAL (too strict) ---
GENRE_RULES.setdefault("thrash metal", {}).update({
    "require_artist_genres_any": [
        "thrash metal","bay area thrash","crossover thrash","teutonic thrash","speed metal"
    ],
    # keep the spirit of your deny, but don't block heavy metal entirely
    "deny_artist_genres_any": ["glam metal","nu metal","alternative metal","hard rock"],
    "popularity_max": 85
})
GENRE_RULES.setdefault("thrash metal", {}).setdefault("whitelist_artists", []).extend([
    "Metallica","Slayer","Megadeth","Anthrax","Testament","Exodus","Overkill","Kreator","Sodom","Sepultura"
])

# --- SHOEGAZE (dream-pop adjacency was clipped) ---
GENRE_RULES.setdefault("shoegaze", {}).update({
    "require_artist_genres_any": ["shoegaze","nu gaze","dream pop","noise pop","space rock","slowcore"],
    # relax the alt/psych deny (they coexist on lots of legit shoe bands)
    "deny_artist_genres_any": ["adult standards","dance pop","electropop","synthpop"]
})
GENRE_RULES.setdefault("shoegaze", {}).setdefault("whitelist_artists", []).extend([
    "My Bloody Valentine","Slowdive","Ride","Lush","Chapterhouse","Pale Saints",
    "Nothing","DIIV","Whirr","Catherine Wheel","Cocteau Twins","Medicine"
])

# --- POST-ROCK (needs instrumental/adjacent tags) ---
GENRE_RULES.setdefault("post-rock", {}).update({
    "require_artist_genres_any": ["post-rock","instrumental rock","math rock","ambient rock","cinematic post-rock"],
    "deny_artist_genres_any": ["pop","dance pop","electropop","hip hop","rap"]
})
GENRE_RULES.setdefault("post-rock", {}).setdefault("whitelist_artists", []).extend([
    "Explosions in the Sky","Godspeed You! Black Emperor","Mogwai","Sigur Rós",
    "This Will Destroy You","Mono","Do Make Say Think","Russian Circles","Tortoise"
])

# --- ACID HOUSE (rave-era IDs were getting excluded) ---
GENRE_RULES.setdefault("acid house", {}).update({
    "require_artist_genres_any": ["acid house","chicago house","jackin house","acid techno"],
    "deny_name_contains": ["radio edit","edit"],  # keep out radio re-cuts but allow classic mixes
    "min_year": 1986
})
GENRE_RULES.setdefault("acid house", {}).setdefault("whitelist_artists", []).extend([
    "Phuture","DJ Pierre","A Guy Called Gerald","Adonis","Armando","Hardfloor","Josh Wink","808 State"
])

# --- BREAKBEAT (your set only had big-beat outliers) ---
GENRE_RULES.setdefault("breakbeat", {}).update({
    "require_artist_genres_any": ["breakbeat","nu skool breaks","big beat","progressive breaks","breaks"],
    "deny_artist_genres_any": ["trance","eurodance","hardstyle"]
})
GENRE_RULES.setdefault("breakbeat", {}).setdefault("whitelist_artists", []).extend([
    "The Prodigy","The Chemical Brothers","The Crystal Method","Plump DJs",
    "Stanton Warriors","Hybrid","Leftfield","Freestylers","Adam Freeland"
])

# --- DUB (you’re still catching straight reggae vocals) ---
GENRE_RULES.setdefault("dub", {}).update({
    "require_artist_genres_any": ["dub","dub reggae","roots dub","steppers"],
    "deny_artist_genres_any": ["dancehall","reggae fusion","ska","rocksteady"]
})
GENRE_RULES.setdefault("dub", {}).setdefault("whitelist_artists", []).extend([
    "King Tubby","Scientist","Lee Scratch Perry","Augustus Pablo","Mad Professor","Prince Jammy"
])

# --- SOCA (only 1: widen substyles) ---
GENRE_RULES.setdefault("soca", {}).update({
    "require_artist_genres_any": ["soca","power soca","groovy soca","chutney soca"],
    "deny_artist_genres_any": ["dancehall","reggaeton"]
})
GENRE_RULES.setdefault("soca", {}).setdefault("whitelist_artists", []).extend([
    "Machel Montano","Kes","Bunji Garlin","Rupee","Destra","Patrice Roberts","Skinny Fabulous","Alison Hinds"
])
# prefer canonical era cuts when present
GENRE_RULES.setdefault("post-rock", {}).setdefault("boost_name_contains", []).extend([
    "live", "version"  # post-rock live cuts often canonical; keep light touch
])
GENRE_RULES.setdefault("dubstep", {}).update({
    "require_artist_genres_any": ["dubstep","brostep","post-dubstep"]
})
GENRE_RULES.setdefault("dubstep", {}).setdefault("whitelist_artists", []).extend([
    "Skream","Benga","Burial","Rusko","Flux Pavilion","Distance","Mala","Coki","Digital Mystikz","Skrillex"
])






# ============================================================
# Curation predicates
# ============================================================



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

    req = [r.lower() for r in (rules.get("require_artist_genres_any") or [])]
    deny = [d.lower() for d in (rules.get("deny_artist_genres_any") or [])]

    # hard denies first
    if deny and any(any(d in g for d in deny) for g in a_gen):
        return False

    # require at least one strong overlap, and prefer 2+
    if req:
        overlap = sum(1 for r in req for g in a_gen if r in g)
        if overlap < 1:
            return False
        # optional: enforce 2 for tricky buckets
        if target_genre.lower() in {"east coast hip hop","afrobeat","bossa nova","grunge","shoegaze"} and overlap < 2:
            return False

    # name guards
    name = (track.get("name") or "").lower()
    deny_tokens = [t.lower() for t in (rules.get("deny_name_contains") or [])]
    if deny_tokens and any(t in name for t in deny_tokens):
        return False

    # year gates
    y = track.get("release_year")
    y = int(y) if isinstance(y, (int, str)) and str(y).isdigit() else None
    min_year = rules.get("min_year")
    max_year = rules.get("max_year")
    if y is not None:
        if min_year is not None and y < min_year: return False
        if max_year is not None and y > max_year: return False

    # popularity gates
    pop = float(track.get("popularity", 0) or 0)
    pmin = rules.get("popularity_min"); pmax = rules.get("popularity_max")
    if pmin is not None and pop < float(pmin): return False
    if pmax is not None and pop > float(pmax): return False

    return True

def relax_rules_if_sparse(genre: str, candidates: list, target_min: int = 4):
    if len(candidates) >= target_min:
        return candidates  # nothing to do

    rules = GENRE_RULES.get(genre, {})
    relaxed = candidates[:]

    # Step 1: temporarily drop popularity cap if present
    pop_max = rules.get("popularity_max")
    if pop_max is not None and len(relaxed) < target_min:
        relaxed = [t for t in relaxed]  # selection happens upstream; here just mark that cap is ignored
        rules["popularity_max"] = None

    # Step 2: allow adjacent subgenres for this run only
    ADJACENT = {
        "thrash metal": ["speed metal","classic metal","heavy metal"],
        "shoegaze": ["dream pop","noise pop","space rock","slowcore","indie rock"],
        "post-rock": ["instrumental rock","math rock","ambient","experimental rock"],
        "acid house": ["chicago house","acid techno","rave"],
        "breakbeat": ["big beat","nu skool breaks","progressive breaks"],
        "dub": ["dub reggae","roots reggae","rocksteady"],
        "soca": ["power soca","groovy soca","chutney soca"]
    }
    adj = ADJACENT.get(genre, [])
    rules.setdefault("require_artist_genres_any", [])
    rules["require_artist_genres_any"] = list(set(rules["require_artist_genres_any"] + adj))

    # Step 3: loosen name denylists for radio edits if still sparse
    if len(relaxed) < target_min:
        for key in ("deny_name_contains",):
            if key in rules:
                # keep the object intact; just narrow the deny temporarily
                rules[key] = [s for s in rules[key] if s not in ("radio edit","edit")]

    return relaxed


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

print(f"Processing {len(PLAYABLE_GENRES)} genres...", flush=True)
processing_start = time.time()

# Index tracks by genre first
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

processed_count = 0
for genre in PLAYABLE_GENRES:
    processed_count += 1
    if processed_count % 20 == 0 or processed_count == len(PLAYABLE_GENRES):
        elapsed = time.time() - processing_start
        print(f"  Progress: {processed_count}/{len(PLAYABLE_GENRES)} genres ({processed_count/len(PLAYABLE_GENRES)*100:.0f}%) - {elapsed:.1f}s elapsed", flush=True)
    parent = GENRE_TO_PARENT.get(genre, "")
    
    # Get candidate pool from index
    candidates: List[Dict[str, Any]] = []
    genre_lower = genre.lower()
    
    for track in tracks_by_genre.get(genre_lower, []):
        tid = track.get("uri") or track.get("id")
        track_genres = norm_tags(track.get('artist_genres') or track.get('genres'))
        
        if not genre_match(genre, track_genres):
            continue
        if not passes_rules(genre, track):
            continue
        if parent and tid and tid in used_track_ids_by_parent[parent]:
            continue
        candidates.append(track)
        #candidates = genre_specific_filter(genre, candidates)

        # Backoff if this genre is underfilled
        candidates = relax_rules_if_sparse(genre, candidates)


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

processing_time = time.time() - processing_start
print(f"\n✓ Completed genre processing in {processing_time:.1f}s\n", flush=True)

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
print(f"Building genre manifest...", flush=True)
manifest_start = time.time()

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

manifest = {}
for genre_name, genre_node in GENRE_TREE.items():
    if isinstance(genre_node, dict):
        manifest[genre_name] = build_manifest(genre_node)

manifest_build_time = time.time() - manifest_start
print(f"✓ Manifest structure built in {manifest_build_time:.1f}s", flush=True)

# -------- Global stats across the union of all selected seed tracks --------
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
print(f"Saving manifest to file...", flush=True)
with open('genre_constellation_manifest.json', 'w', encoding='utf-8') as f:
    json.dump(manifest, f, indent=2, ensure_ascii=False)

total_time = time.time() - start_time
print("\n" + "=" * 60, flush=True)
print(f"✓ SAVED: genre_constellation_manifest.json", flush=True)
print(f"✓ Total execution time: {total_time:.1f}s", flush=True)
print("=" * 60, flush=True)

# -------- Reporting --------
print("\n" + "=" * 60, flush=True)
print("REPORT:", flush=True)
print("=" * 60, flush=True)
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
for genre in PLAYABLE_GENRES:
    if results.get(genre):
        print(f"\n# {genre.upper()}")
        for track in results[genre]:
            artist = (track.get('artists') or ['Unknown'])[0]
            print(f"{track.get('uri')}  // {artist} — {track.get('name')}")

if low_confidence:
    print("\n" + "=" * 60, flush=True)
    print(f"LOW-CONFIDENCE SEEDS ({len(low_confidence)}) — review these:", flush=True)
    print("=" * 60, flush=True)
    for r in low_confidence[:20]:
        print(f"- [{r['genre']}] {r['artist']} — {r['track']}  ({r['uri']})  conf={r['confidence']} reasons={r['reasons']}")
    if len(low_confidence) > 20:
        print(f"... +{len(low_confidence)-20} more")
    if exclusion_counts:
        print("Top concern reasons:")
        for (g, reason), cnt in exclusion_counts.most_common(10):
            print(f" - {g}: {reason} x{cnt}")
