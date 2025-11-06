# seed_selector.py
# Safe filter + scorer + selector for seed tracks per genre.
# Applies EXCLUSIONS per-genre and uses set logic with early returns.

from __future__ import annotations
from typing import Dict, List, Any, Set, Tuple, Iterable
from collections import defaultdict
import math
import re

# ---------- Utility: normalization ----------

_WS = re.compile(r"\s+")
def norm_text(s: str) -> str:
    if not s:
        return ""
    return _WS.sub(" ", s).strip().lower()

def norm_tags(tags: Iterable[str] | None) -> Set[str]:
    if not tags:
        return set()
    return {norm_text(t) for t in tags if t}

def first_artist(track: Dict[str, Any]) -> str:
    artists = track.get("artists") or []
    return artists[0] if artists else ""

def year_of(track: Dict[str, Any]) -> int | None:
    y = track.get("release_year")
    try:
        return int(y) if y is not None else None
    except Exception:
        return None

def title_of(track: Dict[str, Any]) -> str:
    return track.get("name") or ""

def tid_of(track: Dict[str, Any]) -> str | None:
    return track.get("uri") or track.get("id")

def popularity_of(track: Dict[str, Any]) -> float | None:
    pop = track.get("popularity")
    try:
        return float(pop) if pop is not None else None
    except Exception:
        return None

# ---------- Exclusions and rules (merged, deduped) ----------
EXCLUSIONS: Dict[str, List[str]] = {
    "punk": ["pop punk", "dance", "edm", "electro", "big room"],
    "metal": ["funk metal"],
    "electro": ["electropop", "pop"],
    "rock": ["pop rock", "soft rock"],
    "folk": ["indie folk"],
    "funk": ["funk carioca", "baile funk", "brazilian funk"],
}

# Paste your full GENRE_RULES here. The example below is just a stub
# so the file runs if imported alone. Keep your large dict intact.
GENRE_RULES: Dict[str, Dict[str, Any]] = {
    # ----- METAL FAMILY -----
    "metal": {
        "require_artist_genres_any": [
            "metal","heavy metal","hard rock","classic metal","new wave of british heavy metal",
            "speed metal","power metal","glam metal","shock rock"
        ],
        "deny_artist_genres_any": [
            "hip hop","rap","pop rap","trap","dance pop","electropop","synthpop","classic rock","hard rock"
        ],
        "boost_artist_contains": [
            "Metallica","Megadeth","Anthrax","Slayer","Pantera","Iron Maiden","Judas Priest",
            "Sepultura","Motörhead","Motorhead","Dio","Black Sabbath","Opeth","Testament"
        ],
    },
    "thrash metal": {
        "require_artist_genres_any": [
            "thrash metal","bay area thrash","crossover thrash","teutonic thrash","speed metal"
        ],
        "deny_artist_genres_any": ["glam metal","nu metal","alternative metal","hard rock","classic metal"],
        "popularity_max": 85,
        "whitelist_artists": [
            "Metallica","Slayer","Megadeth","Anthrax","Testament","Exodus","Overkill","Kreator","Sodom","Sepultura"
        ],
    },
    "doom & black metal": { "require_artist_genres_any": ["doom metal","black metal"] },
    "sludge metal": { "require_artist_genres_any": ["sludge metal"] },
    "death metal": {
        "require_artist_genres_any": ["death metal","melodic death metal","technical death metal"],
        "deny_artist_genres_any": ["gothic metal","djent","industrial metal"]
    },
    "progressive metal": {
        "require_artist_genres_any": ["progressive metal"],
        "deny_artist_genres_any": ["power metal"]
    },
    "nu metal": {
        "require_artist_genres_any": ["nu metal","rap metal","alternative metal","industrial metal"],
        "deny_artist_genres_any": ["rap rock","pop rock","alternative rock","dance pop","pop","hip hop","pop rap"]
    },

    # ----- PUNK LANES -----
    "punk": {
        "require_artist_genres_any": ["punk","punk rock"],
        "deny_artist_genres_any": ["pop","dance pop","electropop","alternative rock","comedy rock","novelty","garage rock"],
        "popularity_max": 85
    },
    "ska": {
        "require_artist_genres_any": ["ska","ska punk","2 tone","third wave ska","rocksteady"],
        "deny_artist_genres_any": ["punk rock","hardcore punk","new wave"],
        "whitelist_artists": ["The Specials","The Selecter","The Beat","Toots & The Maytals","The Skatalites","The Mighty Mighty Bosstones","Rancid"]
    },
    "hardcore": {
        "require_artist_genres_any": ["hardcore punk","nyhc","post-hardcore","powerviolence","d-beat","youth crew"],
        "deny_artist_genres_any": [
            "happy hardcore","hardcore techno","gabber","edm","dance","dance pop","pop","pop punk","emo","metalcore","easycore"
        ],
        "popularity_max": 70
    },
    "post-punk": {
        "require_artist_genres_any": ["post-punk","post punk","gothic rock","coldwave","no wave"],
        "deny_artist_genres_any": ["classic rock","soft rock","dance pop","pop","punk","pop punk","alternative rock","grunge"]
    },
    "emo": {
        "require_artist_genres_any": ["emo","screamo","midwest emo","post-hardcore"],
        "deny_artist_genres_any": ["rap","hip hop","trap","dance pop","pop"]
    },

    # ----- ROCK OTHER -----
    "alternative rock": {
        "require_artist_genres_any": ["alternative rock","modern rock","post-grunge","alternative metal","grunge"],
        "deny_artist_genres_any": ["dance pop","electropop","synthpop","pop"]
    },
    "indie rock": {
        "require_artist_genres_any": ["indie rock","modern rock","garage rock","lo-fi indie","indie garage rock","alternative rock"],
        "deny_artist_genres_any": ["hip hop","rap","pop rap","trap","cloud rap","alternative hip hop"]
    },
    "shoegaze": {
        "require_artist_genres_any": ["shoegaze","nu gaze","dream pop","noise pop","space rock","slowcore"],
        "deny_artist_genres_any": ["adult standards","dance pop","electropop","synthpop"],
        "whitelist_artists": [
            "My Bloody Valentine","Slowdive","Ride","Lush","Chapterhouse",
            "Pale Saints","Nothing","Whirr","Medicine","Catherine Wheel","Cocteau Twins","DIIV"
        ],
        "deny_name_contains": ["remix","live","edit"]
    },
    "grunge": {
        "require_artist_genres_any": ["grunge","post-grunge","seattle sound"],
        "deny_artist_genres_any": ["alternative rock","pop rock","classic rock"],
        "min_year": 1989,
        "max_year": 1997,
        "whitelist_artists": ["Nirvana","Soundgarden","Pearl Jam","Alice In Chains","Stone Temple Pilots","Mudhoney","Screaming Trees"]
    },
    "post-rock": {
        "require_artist_genres_any": ["post-rock","instrumental post-rock","cinematic post-rock","math rock","instrumental rock"],
        "deny_artist_genres_any": ["pop","dance pop","electropop","hip hop","rap"],
        "whitelist_artists": ["Explosions in the Sky","Godspeed You! Black Emperor","Mogwai","Sigur Rós","Mono","This Will Destroy You","Do Make Say Think","Tortoise"]
    },
    "classic rock": {
        "require_artist_genres_any": ["classic rock","album rock"],
        "deny_artist_genres_any": ["dance pop","electropop","synthpop","pop"],
        "max_year": 1980
    },
    "psychedelic rock": {
        "require_artist_genres_any": ["psychedelic rock","acid rock","psych rock"],
        "deny_artist_genres_any": ["dance pop","pop","adult standards","classic rock","soft rock","blues rock"]
    },
    "hard rock": {
        "require_artist_genres_any": ["hard rock","arena rock","glam metal","classic rock"],
        "deny_artist_genres_any": ["soft rock","adult standards","dance pop","pop","industrial metal","psychedelic rock","blues"]
    },

    # ----- ELECTRONIC -----
    "house": {
        "require_artist_genres_any": ["house","deep house","tech house","progressive house","electro house","funky house","disco house"],
        "deny_artist_genres_any": ["hip hop","trap","rap","dubstep","soundtrack"],
        "deny_name_contains": ["feat."]
    },
    "deep house": { "require_artist_genres_any": ["deep house","house"] },
    "tech house": { "require_artist_genres_any": ["tech house"] },
    "progressive house": {
        "require_artist_genres_any": ["progressive house"],
        "deny_artist_genres_any": ["trance","uplifting trance","eurotrance","dance pop","big room","electro house"]
    },
    "acid house": {
        "require_artist_genres_any": ["acid house","jackin house","acid techno"],
        "deny_name_contains": ["radio edit","edit"],
        "min_year": 1986, "max_year": 1993,
        "whitelist_artists": ["Phuture","DJ Pierre","Adonis","Armando","Hardfloor","A Guy Called Gerald","Josh Wink","808 State"]
    },
    "techno": {
        "require_artist_genres_any": ["techno","detroit techno","minimal techno","hard techno","berlin techno","berlin school"],
        "deny_artist_genres_any": ["deep house","house","progressive house","trance"]
    },
    "trance": {
        "require_artist_genres_any": ["trance","uplifting trance","progressive trance","eurotrance"],
        "deny_artist_genres_any": ["dance pop","big room","edm"]
    },
    "breakbeat": {
        "require_artist_genres_any": ["breakbeat","big beat","nu skool breaks","progressive breaks"],
        "deny_artist_genres_any": ["trance","eurodance","hardstyle"],
        "whitelist_artists": ["The Prodigy","The Chemical Brothers","The Crystal Method","Plump DJs","Stanton Warriors","Hybrid","Leftfield","Freestylers","Adam Freeland"]
    },
    "dubstep": {
        "require_artist_genres_any": ["dubstep","brostep","uk dubstep","post-dubstep"],
        "deny_artist_genres_any": ["future bass","progressive house","electro house","edm"],
        "whitelist_artists": ["Skream","Benga","Mala","Burial","Rusko","Flux Pavilion","Distance","Coki","Digital Mystikz","Skrillex"]
    },

    # ----- HIP HOP -----
    "rap": {
        "require_artist_genres_any": ["rap","hip hop","hip-hop"],
        "deny_artist_genres_any": ["dance pop","electropop","synthpop","latin pop","pop"],
        "deny_name_contains": ["remix","edit","radio edit","acoustic"]
    },
    "underground hip hop": {
        "require_artist_genres_any": ["underground hip hop","boom bap","abstract hip hop","backpack rap"],
        "deny_artist_genres_any": ["dance pop","pop","trap","pop rap","electropop","synthpop","neo soul","r&b","contemporary r&b"],
        "popularity_max": 65
    },
    "boom bap": {
        "require_artist_genres_any": ["boom bap","east coast hip hop","underground hip hop"],
        "deny_artist_genres_any": ["neo soul","r&b","jazz","contemporary r&b"]
    },
    "east coast hip hop": {
        "require_artist_genres_any": ["east coast hip hop","boom bap","nyc rap","queens hip hop","brooklyn drill"],
        "deny_artist_genres_any": ["west coast rap","southern hip hop","reggae fusion","dancehall","latin pop","alternative hip hop"],
        "whitelist_artists": [
            "Nas","Mobb Deep","Wu-Tang Clan","A Tribe Called Quest","The Notorious B.I.G.",
            "Rakim","Gang Starr","Big L","Mos Def","Black Star","Busta Rhymes","Eric B. & Rakim",
            "Big Daddy Kane","MF DOOM","Joey Bada$$","Boot Camp Clik","De La Soul"
        ],
        "deny_name_contains": ["remix","edit","12\"","dub","re-drum","re drum","re-edit","re edit","instrumental"]
    },
    "west coast rap": {
        "require_artist_genres_any": ["west coast rap","g funk","gangsta rap","la hip hop","bay area hip hop","west coast"],
        "deny_artist_genres_any": ["east coast hip hop","boom bap","southern hip hop","uk hip hop","east coast"]
    },
    
    "trap": {
        "require_artist_genres_any": ["trap","southern hip hop","atl hip hop"],
        "deny_artist_genres_any": ["dance pop","pop"]
    },
    "drill": {
        "require_artist_genres_any": ["drill","uk drill","new york drill"],
        "deny_artist_genres_any": ["dance pop","pop"]
    },
    "conscious hip hop": {
        "require_artist_genres_any": ["conscious hip hop","hip hop","jazz rap","alternative hip hop","rap"],
        "deny_artist_genres_any": ["rock","alternative rock","pop rock"],
        "boost_artist_contains": ["Common","Mos Def","Blackstar","Black Star"]
    },

    # ----- R&B / SOUL / FUNK -----
    "r&b": {
        "deny_artist_genres_any": ["rap","hip hop","trap","drill"]
    },
    "quiet storm": { "require_artist_genres_any": ["quiet storm"] },
    "soul": {
        "require_artist_genres_any": ["soul","neo soul","motown"],
        "deny_artist_genres_any": ["hip hop","rap","trap"]
    },
    "motown": {
        "require_artist_genres_any": ["motown"],
        "deny_artist_genres_any": ["southern soul","philly soul","funk","pop"],
        "max_year": 1972
    },
    "funk": {
        "require_artist_genres_any": ["funk","p funk","pfunk","funk rock","jazz funk","soul funk"],
        "deny_artist_genres_any": ["soul ballad","adult standards","pop","soft rock", "edm","electro house","dance pop","big room","progressive house","americana","roots rock","alt rock","alternative rock","hip hop","rap","funk carioca","baile funk","brazilian funk"],
        "deny_name_contains": ["remix","edit"],
        "min_year": 1965
    },
    "funk rock": {
        "require_artist_genres_any": ["funk rock","alternative metal","rap rock"],
        "deny_artist_genres_any": ["new jack swing","dance pop","pop","pop rock","post-grunge"]
    },
    "boogie": {
        "require_artist_genres_any": ["boogie","post-disco"],
        "deny_artist_genres_any": ["soundtrack","broadway","film soundtrack","show tunes"],
        "min_year": 1978,
        "max_year": 1987
    },
    "neo soul": {
        "require_artist_genres_any": ["neo soul"],
        "deny_artist_genres_any": ["rap","trap","drill","dance pop","pop"],
        "whitelist_artists": ["Erykah Badu","D’Angelo","Jill Scott","Angie Stone","Maxwell","The Internet","Solange"]
    },

    # ----- JAZZ -----
    "jazz fusion": {
        "require_artist_genres_any": ["jazz fusion","fusion","jazz funk","jazz-rock","jazz rock"],
        "deny_artist_genres_any": ["bachata","latin pop","reggaeton","dance pop","pop","soundtrack","synthwave","new age","hard bop","bebop","cool jazz"]
    },
    "bebop": {
        "require_artist_genres_any": ["bebop","hard bop"],
        "deny_artist_genres_any": ["swing","cool jazz","vocal jazz"],
        "max_year": 1965
    },
    "cool jazz": {
        "require_artist_genres_any": ["cool jazz","west coast jazz"],
        "deny_artist_genres_any": ["bebop","hard bop","vocal jazz","jazz funk","fusion","modal jazz"],
        "max_year": 1975
    },
    "hard bop": {
        "require_artist_genres_any": ["hard bop","post bop","bebop"],
        "deny_artist_genres_any": ["cool jazz","swing","vocal jazz"]
    },
    "swing": {
        "require_artist_genres_any": ["swing","big band","big band jazz"],
        "deny_artist_genres_any": ["hip hop","rap","trap","drill"],
        "max_year": 1965
    },
    "smooth jazz": {
        "require_artist_genres_any": ["smooth jazz"],
        "deny_artist_genres_any": ["r&b","contemporary r&b","neo soul"]
    },
    "avant-garde jazz": {
        "require_artist_genres_any": ["avant-garde jazz","free jazz","free improvisation"]
    },

    # ----- LATIN / REGGAE -----
    "bossa nova": {
        "require_artist_genres_any": ["bossa nova"],
        "deny_artist_genres_any": ["samba","mpb","latin pop","reggaeton"],
        "whitelist_artists": ["Antonio Carlos Jobim","João Gilberto","Astrud Gilberto","Stan Getz","Nara Leão","Marcos Valle"]
    },
    "salsa": {
        "require_artist_genres_any": ["salsa"],
        "deny_artist_genres_any": ["rap","reggaeton","latin trap"]
    },
    "mambo": {
        "require_artist_genres_any": ["mambo"]
    },
    "soca": {
        "require_artist_genres_any": ["soca","power soca","groovy soca","chutney soca"],
        "deny_artist_genres_any": ["dancehall","reggaeton","latin pop"],
        "whitelist_artists": ["Machel Montano","Kes","Bunji Garlin","Patrice Roberts","Destra","Nailah Blackman","Skinny Fabulous","Alison Hinds"]
    },
    "ska": {
        "require_artist_genres_any": ["ska","ska punk","2 tone","third wave ska","rocksteady"],
        "deny_artist_genres_any": ["roots reggae","reggae","dancehall","dub"]
    },
    "dancehall": {
        "require_artist_genres_any": ["dancehall"],
        "deny_artist_genres_any": ["reggaeton","latin pop","pop","dance pop"]
    },
    "afrobeat": {
        "require_artist_genres_any": ["afrobeat","nigerian afrobeat","afro funk"],
        "deny_artist_genres_any": ["soul","funk","r&b","afropop","dance pop"]
    },
    "afropop": {
        "require_artist_genres_any": ["afropop","afrobeats","naija pop","alté"],
        "deny_artist_genres_any": ["afrobeat"]
    },
    "dub": {
        "require_artist_genres_any": ["dub","dub reggae","roots dub","steppers"],
        "deny_artist_genres_any": ["dancehall","reggae fusion","ska","rocksteady"],
        "whitelist_artists": ["King Tubby","Scientist","Lee Scratch Perry","Augustus Pablo","Mad Professor","Prince Jammy"]
    },
}

# ---------- Core helpers ----------

def _contains_any(text: str, needles: Iterable[str]) -> bool:
    lt = norm_text(text)
    for n in needles:
        if n and n.lower() in lt:
            return True
    return False

def _artist_in_whitelist(artist: str, wl: Iterable[str]) -> bool:
    a = artist.strip().lower()
    return any(a == w.strip().lower() for w in wl)

def _set_intersects(a: Set[str], b_list: Iterable[str]) -> bool:
    b = {norm_text(x) for x in b_list if x}
    return not a.isdisjoint(b)

def _set_contains_all(a: Set[str], b_list: Iterable[str]) -> bool:
    b = {norm_text(x) for x in b_list if x}
    return b.issubset(a)

def _merged_deny_genres(genre_key: str, rules: Dict[str, Any]) -> Set[str]:
    # Merge deny list from rules with EXCLUSIONS[genre_key]
    rule_denies = set(norm_tags(rules.get("deny_artist_genres_any") or []))
    extra = set(norm_tags(EXCLUSIONS.get(genre_key, [])))
    return rule_denies.union(extra)

# ---------- Rule evaluation ----------

def passes_rules(genre_key: str, track: Dict[str, Any], rules: Dict[str, Any]) -> bool:
    a_genres = norm_tags(track.get("artist_genres") or track.get("genres"))
    if not a_genres:
        if rules.get("require_artist_genres_any") or rules.get("require_artist_genres_all"):
            return False

    # Require any
    req_any = rules.get("require_artist_genres_any") or []
    if req_any and not _set_intersects(a_genres, req_any):
        return False

    # Require all
    req_all = rules.get("require_artist_genres_all") or []
    if req_all and not _set_contains_all(a_genres, req_all):
        return False

    # Deny any (merged with EXCLUSIONS)
    deny_any_merged = _merged_deny_genres(genre_key, rules)
    if deny_any_merged and not a_genres.isdisjoint(deny_any_merged):
        return False

    # Title filters
    title = title_of(track)
    deny_name = rules.get("deny_name_contains") or []
    if deny_name and _contains_any(title, deny_name):
        return False

    # Year window
    y = year_of(track)
    min_year = rules.get("min_year")
    if min_year is not None and (y is None or y < int(min_year)):
        return False
    max_year = rules.get("max_year")
    if max_year is not None and (y is None or y > int(max_year)):
        return False

    # Popularity window
    pop = popularity_of(track)
    pop_min = rules.get("popularity_min")
    if pop_min is not None and (pop is None or pop < float(pop_min)):
        return False
    pop_max = rules.get("popularity_max")
    if pop_max is not None and (pop is None or pop > float(pop_max)):
        return False

    # Optional whitelist strictness
    if rules.get("whitelist_only"):
        artist = first_artist(track)
        wl = rules.get("whitelist_artists") or []
        if wl and not _artist_in_whitelist(artist, wl):
            return False

    return True

def genre_match(genre_key: str, track: Dict[str, Any], rules_for_genre: Dict[str, Any]) -> bool:
    return passes_rules(genre_key, track, rules_for_genre)

# ---------- Scoring ----------

def score_track(track: Dict[str, Any], rules: Dict[str, Any], seed_year_hint: int | None = None) -> float:
    s = 0.0
    artist = first_artist(track)
    title = title_of(track)
    pop = popularity_of(track)
    y = year_of(track)

    # Popularity center
    if pop is not None:
        center = float(rules.get("popularity_center", 60))
        s -= abs(pop - center) * 0.05

    # Year proximity
    if seed_year_hint is not None and y is not None:
        s -= abs(y - seed_year_hint) * 0.02

    # Name penalties already filtered, small nudge anyway
    if _contains_any(title, rules.get("deny_name_contains") or []):
        s -= 1.0

    wl = rules.get("whitelist_artists") or []
    if wl and _artist_in_whitelist(artist, wl):
        s += 2.0

    boosts = rules.get("boost_artist_contains") or []
    if boosts and _contains_any(artist, boosts):
        s += 1.0

    return s

# ---------- Selection pipeline ----------

def select_seeds_for_genre(
    genre: str,
    tracks_by_genre: Dict[str, List[Dict[str, Any]]],
    rules: Dict[str, Any],
    parent: str | None,
    used_track_ids_by_parent: Dict[str, Set[str]],
    used_artists_by_parent: Dict[str, Set[str]],
    used_track_ids_global: Set[str],
    used_artists_global: Set[str],
    GLOBAL_UNIQUENESS: bool = True,
    K: int = 4,
) -> List[Dict[str, Any]]:
    family_tids = used_track_ids_by_parent[parent] if parent else set()
    family_arts = used_artists_by_parent[parent] if parent else set()

    candidates: List[Dict[str, Any]] = []
    rules_for_genre = GENRE_RULES.get(genre, rules)  # prefer table entry

    for t in tracks_by_genre.get(genre, []):
        if not genre_match(genre, t, rules_for_genre):
            continue

        tid = tid_of(t)
        art = first_artist(t)

        # Uniqueness
        if parent:
            if tid and tid in family_tids:
                continue
            if art and art in family_arts:
                continue
        if GLOBAL_UNIQUENESS:
            if tid and tid in used_track_ids_global:
                continue
            if art and art in used_artists_global:
                continue

        candidates.append(t)

    if not candidates:
        return []

    years = sorted([y for y in (year_of(t) for t in candidates) if y is not None])
    hint = years[len(years) // 2] if years else None

    scored = [(score_track(t, rules_for_genre, seed_year_hint=hint), t) for t in candidates]
    scored.sort(key=lambda x: x[0], reverse=True)

    top_k: List[Dict[str, Any]] = []
    seen_artists: Set[str] = set()
    for _, t in scored:
        if len(top_k) >= K:
            break
        art = first_artist(t)
        if art in seen_artists:
            continue
        top_k.append(t)
        seen_artists.add(art)

        tid = tid_of(t)
        if parent:
            used_artists_by_parent[parent].add(art)
            if tid:
                used_track_ids_by_parent[parent].add(tid)
        if GLOBAL_UNIQUENESS:
            used_artists_global.add(art)
            if tid:
                used_track_ids_global.add(tid)

    return top_k

# ---------- Batch driver ----------

def build_seed_map(
    genres: Iterable[str],
    tracks_by_genre: Dict[str, List[Dict[str, Any]]],
    GLOBAL_UNIQUENESS: bool = True,
    parent: str | None = None,
    K: int = 4,
) -> Tuple[Dict[str, List[Dict[str, Any]]], Dict[str, int]]:
    used_track_ids_by_parent: Dict[str, Set[str]] = defaultdict(set)
    used_artists_by_parent: Dict[str, Set[str]] = defaultdict(set)
    used_track_ids_global: Set[str] = set()
    used_artists_global: Set[str] = set()

    results: Dict[str, List[Dict[str, Any]]] = {}
    coverage: Dict[str, int] = {}

    for g in genres:
        picks = select_seeds_for_genre(
            g,
            tracks_by_genre,
            GENRE_RULES.get(g, {}),
            parent,
            used_track_ids_by_parent,
            used_artists_by_parent,
            used_track_ids_global,
            used_artists_global,
            GLOBAL_UNIQUENESS=GLOBAL_UNIQUENESS,
            K=K,
        )
        results[g] = picks
        coverage[g] = len(picks)

    return results, coverage

# ---------- Quick self check ----------

def _self_test():
    tracks_by_genre = {
        "punk": [
            {"uri": "p1", "artists": ["The Clash"], "artist_genres": ["punk", "punk rock"], "name": "White Riot", "release_year": 1977, "popularity": 64},
            {"uri": "p2", "artists": ["Bubble"], "artist_genres": ["dance pop"], "name": "Cute Edit", "release_year": 2020, "popularity": 90},
            {"uri": "p3", "artists": ["Pop Punkers"], "artist_genres": ["pop punk"], "name": "Teenage Tune", "release_year": 2015, "popularity": 70},
        ],
        "metal": [
            {"uri": "m1", "artists": ["Metallica"], "artist_genres": ["metal","thrash metal"], "name": "Battery", "release_year": 1986, "popularity": 70},
            {"uri": "m2", "artists": ["Primus"], "artist_genres": ["funk metal"], "name": "Jerry Was A Race Car Driver", "release_year": 1991, "popularity": 68},
        ],
    }
    genres = ["punk", "metal"]
    results, coverage = build_seed_map(genres, tracks_by_genre, GLOBAL_UNIQUENESS=False, parent=None, K=4)

    # EXCLUSIONS enforced
    assert any(first_artist(t) == "The Clash" for t in results["punk"])
    assert all(t["uri"] != "p2" for t in results["punk"])  # dance pop excluded by EXCLUSIONS["punk"]
    assert all(t["uri"] != "p3" for t in results["punk"])  # pop punk excluded by EXCLUSIONS["punk"]
    assert any(first_artist(t) == "Metallica" for t in results["metal"])
    assert all(t["uri"] != "m2" for t in results["metal"])  # funk metal excluded by EXCLUSIONS["metal"]

    print("Self test passed: EXCLUSIONS merged and rules respected.")

if __name__ == "__main__":
    print("============================================================")
    print("Building full seed selection with corrected logic...")
    print("============================================================")

    # ---- Load your real track data ----
    # Replace this import with the way your project actually loads tracks_by_genre
    from data_loader import tracks_by_genre

    results, coverage = build_seed_map(
        genres=list(GENRE_RULES.keys()),
        tracks_by_genre=tracks_by_genre,
        GLOBAL_UNIQUENESS=True,
        parent=None,
        K=4,
    )

    all_tracks = [t for tracks in results.values() for t in tracks]
    unique_artists = {a for tracks in results.values()
                      for a in [(t.get('artists') or [''])[0] for t in tracks] if a}

    print(f"\nTotal seed selections: {len(all_tracks)}")
    print(f"Total unique artists across all seeds: {len(unique_artists)}")

    low_coverage = {g: len(v) for g, v in results.items() if len(v) < 4}
    if low_coverage:
        print("\n⚠️  GENRES WITH LOW COVERAGE:")
        for g, n in sorted(low_coverage.items(), key=lambda x: x[1]):
            print(f"   {g}: only {n} track(s)")

    print("\n============================================================")
    print("URIS FOR BATCH EXPORT:")
    print("============================================================\n")

    for genre, tracks in results.items():
        print(f"# {genre.upper()}")
        for t in tracks:
            name = t.get("name", "")
            artist = (t.get("artists") or [""])[0]
            uri = t.get("uri") or t.get("id")
            print(f"{uri:<40}  // {artist} — {name}")
        print()
