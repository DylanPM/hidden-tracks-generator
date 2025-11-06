import json
import re
from collections import defaultdict

with open('server/data/prepped.json', 'r', encoding='utf-8') as f:
    tracks = json.load(f)

print(f"Loaded {len(tracks)} tracks\n")

def generate_filename(artist, track_name):
    """Generate expected filename for exported profile"""
    safe_artist = artist.lower().replace(' ', '-')
    safe_artist = re.sub(r'[^a-z0-9-]', '', safe_artist)
    safe_artist = re.sub(r'-+', '-', safe_artist).strip('-')
    
    safe_name = track_name.lower().replace(' ', '-')
    safe_name = re.sub(r'[^a-z0-9-]', '', safe_name)
    safe_name = re.sub(r'-+', '-', safe_name).strip('-')
    
    return f"{safe_artist}_{safe_name}.json"

# ALL genres - removed detroit techno and idm
ALL_GENRES = [
    # Most specific (leaves) - Metal
    "thrash metal", "doom metal", "sludge metal", "black metal", 
    "death metal", "progressive metal", "nu metal",
    
    # House subgenres
    "deep house", "tech house", "progressive house", "acid house",
    
    # Techno subgenres
    "minimal techno",  # removed detroit techno
    
    # Trance subgenres
    "progressive trance", "psytrance",
    
    # Bass music subgenres
    "drum and bass", "jungle",
    "dubstep", "brostep", "melodic dubstep",
    
    # Hip-hop subgenres
    "trap", "drill", "gangsta rap", "boom bap", "east coast hip hop",
    "west coast rap", "southern hip hop", "conscious hip hop", 
    "alternative hip hop", "underground hip hop", "phonk", "cloud rap",
    
    # R&B subgenres
    "contemporary r&b", "neo soul", "quiet storm",
    
    # Jazz subgenres
    "bebop", "cool jazz", "hard bop", "swing", "jazz fusion",
    "smooth jazz", "vocal jazz", "nu jazz", "avant-garde jazz",
    
    # Country subgenres
    "classic country", "outlaw country", "bluegrass",
    "country rock", "southern rock", "roots rock",
    
    # Latin subgenres
    "reggaeton", "latin pop", "salsa", "bachata", "cumbia",
    "merengue", "tropical", "mambo", "bossa nova",
    
    # Afro-Caribbean subgenres
    "afrobeat", "afropop", "amapiano", "dancehall",
    "dub", "ska", "soca",
    
    # Classical subgenres
    "baroque", "romantic", "modern classical",
    "soundtrack", "new age", "minimalism", "drone",
    
    # Experimental subgenres
    "avant-garde", "noise", "glitch", "lo-fi",
    
    # Rock subgenres (leaves)
    "alternative rock", "indie rock", "garage rock", "classic rock",
    "psychedelic rock", "hard rock", "punk", "post-punk", "emo",
    "shoegaze", "grunge", "post-rock",
    
    # Electronic subgenres (leaves) - removed idm
    "edm", "electro", "synthwave", "ambient",
    
    # MID-LEVEL GENRES
    "metal", "house", "techno", "trance",
    "hip hop", "rap", "r&b", "soul", "funk", "disco", "motown", "boogie", "funk rock",
    "jazz", "country", "americana", "folk",
    "latin", "reggae", "experimental",
    
    # TOP-LEVEL GENRES
    "rock", "electronic", "classical",
]

# Genres that need relaxed matching
RELAXED_GENRES = ["doom metal", "black metal"]

# Exclusions
EXCLUSIONS = {
    "punk": ["pop punk", "pop"],
    "metal": ["funk metal", "nu metal", "rap metal"],
    "electro": ["electropop", "pop"],
    "rock": ["pop rock", "soft rock"],
    "folk": ["indie folk"],
}

def genre_match(search_genre, track_genres):
    if search_genre in EXCLUSIONS:
        for exclusion in EXCLUSIONS[search_genre]:
            if any(exclusion.lower() in g.lower() for g in track_genres):
                return False
    
    pattern = r'\b' + re.escape(search_genre.lower()) + r'\b'
    return any(re.search(pattern, g.lower()) for g in track_genres)

used_track_ids = set()
used_artists = set()
results = {}

for genre in ALL_GENRES:
    candidates = []
    for track in tracks:
        if track['id'] in used_track_ids:
            continue
        
        primary_artist = track['artists'][0] if track.get('artists') else None
        if primary_artist and primary_artist in used_artists:
            continue
        
        track_genres = track.get('genres', [])
        if not track_genres:
            continue
        
        if genre_match(genre, track_genres):
            candidates.append(track)
    
    if not candidates:
        results[genre] = []
        continue
    
    # GROUP BY PURITY TIERS, THEN PICK MOST POPULAR WITHIN EACH TIER
    purity_tiers = defaultdict(list)
    for track in candidates:
        num_genres = len(track.get('genres', []))
        if num_genres <= 2:
            tier = 'pure'
        elif num_genres <= 4:
            tier = 'medium'
        else:
            tier = 'broad'
        purity_tiers[tier].append(track)
    
    # Sort each tier by popularity (descending)
    for tier in purity_tiers:
        purity_tiers[tier].sort(key=lambda t: -t.get('popularity', 0))
    
    # Collect top 4 (changed from 3), prioritizing pure → medium → broad
    top_4 = []
    genre_artists = set()
    
    for tier in ['pure', 'medium', 'broad']:
        if len(top_4) >= 4:  # Changed from 3
            break
        
        for track in purity_tiers.get(tier, []):
            artist = track['artists'][0] if track.get('artists') else None
            if artist and artist in genre_artists:
                continue
            
            top_4.append(track)
            if artist:
                genre_artists.add(artist)
            
            if len(top_4) >= 4:  # Changed from 3
                break
    
    results[genre] = top_4
    
    for t in top_4:
        used_track_ids.add(t['id'])
        if t.get('artists'):
            used_artists.add(t['artists'][0])

# Build hierarchical manifest (same as before)
GENRE_TREE = {
    "rock": {
        "_seeds": "rock",
        "subgenres": {
            "metal": {
                "_seeds": "metal",
                "subgenres": {
                    "thrash metal": {"_seeds": "thrash metal"},
                    "doom metal": {"_seeds": "doom metal"},
                    "sludge metal": {"_seeds": "sludge metal"},
                    "black metal": {"_seeds": "black metal"},
                    "death metal": {"_seeds": "death metal"},
                    "progressive metal": {"_seeds": "progressive metal"},
                    "nu metal": {"_seeds": "nu metal"}
                }
            },
            "punk": {
                "_seeds": "punk",
                "subgenres": {
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
            "techno": {
                "_seeds": "techno",
                "subgenres": {
                    "minimal techno": {"_seeds": "minimal techno"}
                }
            },
            "trance": {
                "_seeds": "trance",
                "subgenres": {
                    "progressive trance": {"_seeds": "progressive trance"},
                    "psytrance": {"_seeds": "psytrance"}
                }
            },
            "drum and bass": {"_seeds": "drum and bass"},
            "jungle": {"_seeds": "jungle"},
            "dubstep": {
                "_seeds": "dubstep",
                "subgenres": {
                    "brostep": {"_seeds": "brostep"},
                    "melodic dubstep": {"_seeds": "melodic dubstep"}
                }
            },
            "edm": {"_seeds": "edm"},
            "electro": {"_seeds": "electro"},
            "synthwave": {"_seeds": "synthwave"},
            "ambient": {"_seeds": "ambient"}
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
    "r&b": {
        "_seeds": "r&b",
        "subgenres": {
            "contemporary r&b": {"_seeds": "contemporary r&b"},
            "neo soul": {"_seeds": "neo soul"},
            "quiet storm": {"_seeds": "quiet storm"}
        }
    },
    "soul": {
        "_seeds": "soul",
        "subgenres": {
            "motown": {"_seeds": "motown"},
            "disco": {"_seeds": "disco"}
        }
    },
    "funk": {
        "_seeds": "funk",
        "subgenres": {
            "funk rock": {"_seeds": "funk rock"},
            "boogie": {"_seeds": "boogie"}
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
            "roots rock": {"_seeds": "roots rock"}
        }
    },
    "folk": {
        "_seeds": "folk",
        "subgenres": {
            "americana": {"_seeds": "americana"}
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
            "dancehall": {"_seeds": "dancehall"}
        }
    },
    "afrobeat": {
        "_seeds": "afrobeat",
        "subgenres": {
            "afropop": {"_seeds": "afropop"},
            "amapiano": {"_seeds": "amapiano"},
            "soca": {"_seeds": "soca"}
        }
    },
    "classical": {
        "_seeds": "classical",
        "subgenres": {
            "baroque": {"_seeds": "baroque"},
            "romantic": {"_seeds": "romantic"},
            "modern classical": {"_seeds": "modern classical"},
            "soundtrack": {"_seeds": "soundtrack"},
            "new age": {"_seeds": "new age"},
            "minimalism": {"_seeds": "minimalism"},
            "drone": {"_seeds": "drone"}
        }
    },
    "experimental": {
        "_seeds": "experimental",
        "subgenres": {
            "avant-garde": {"_seeds": "avant-garde"},
            "noise": {"_seeds": "noise"},
            "glitch": {"_seeds": "glitch"},
            "lo-fi": {"_seeds": "lo-fi"}
        }
    }
}
def build_manifest(tree):
    if isinstance(tree, dict):
        result = {}
        for key, value in tree.items():
            if key == "_seeds":
                # This level is playable - add its seeds
                genre_name = value
                if results.get(genre_name):
                    result["seeds"] = [
                        {
                            "uri": t['uri'],
                            "name": t['name'],
                            "artist": t['artists'][0] if t.get('artists') else 'Unknown',
                            "popularity": t.get('popularity', 0),
                            "filename": generate_filename(
                                t['artists'][0] if t.get('artists') else 'unknown',
                                t['name']
                            )
                        }
                        for t in results[genre_name]
                    ]
            else:
                # Recurse into subgenres
                result[key] = build_manifest(value)
        return result
    else:
        return {}

manifest = build_manifest(GENRE_TREE)

with open('genre_constellation_manifest.json', 'w', encoding='utf-8') as f:
    json.dump(manifest, f, indent=2, ensure_ascii=False)

# Output URIs
print("=" * 60)
print("URIS FOR BATCH EXPORT:")
print("=" * 60)
for genre in ALL_GENRES:
    if results[genre]:
        print(f"\n# {genre.upper()}")
        for track in results[genre]:
            artist = track['artists'][0] if track.get('artists') else 'Unknown'
            pop = track.get('popularity', 0)
            num_genres = len(track.get('genres', []))
            print(f"{track['uri']}  # {artist} - {track['name']} (pop:{pop}, tags:{num_genres})")

print("\n" + "=" * 60)
print("SAVED: genre_constellation_manifest.json")
print("=" * 60)

# Report
print("\n" + "=" * 60)
print("REPORT:")
print("=" * 60)
total_found = 0
issues = []

for genre in ALL_GENRES:
    count = len(results[genre])
    total_found += count
    
    status = "✓" if count == 4 else "⚠️" if count > 0 else "✗"  # Changed from 3
    
    if count > 0:
        avg_pop = sum(t.get('popularity', 0) for t in results[genre]) / count
        print(f"{status} {genre:<30} {count}/4 tracks (avg pop: {avg_pop:.0f})")  # Changed from /3
    
    if count < 4 and count > 0:  # Changed from 3
        issues.append((genre, count))

print(f"\nTotal unique tracks: {total_found}")
print(f"\nTotal unique artists: {len(used_artists)}")
print(f"Genres with 4 tracks: {len([g for g in ALL_GENRES if len(results[g]) == 4])}")  # Changed from 3

if issues:
    print(f"\n⚠️  GENRES WITH LOW COVERAGE:")
    for genre, count in issues:
        print(f"   {genre}: only {count} track(s)")

# Clean URI list for copy-paste
print("\n" + "=" * 60)
print("CLEAN URI LIST (copy-paste into batch exporter):")
print("=" * 60)
for genre in ALL_GENRES:
    for track in results[genre]:
        print(track['uri'])