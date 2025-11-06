#!/usr/bin/env python3
"""
Diagnose why genres defined in GENRE_TREE have 0 tracks.
Filters out intentionally commented-out genres.
"""

import json
import sys
sys.path.insert(0, '.')

# Run the script to get all data
exec(open('killmegod.py').read())

print("\n" + "="*70)
print("DIAGNOSIS: GENRES WITH 0 TRACKS")
print("="*70)

missing_genres = []
for genre in PLAYABLE_GENRES:
    count = len(results.get(genre, []))
    if count == 0:
        missing_genres.append(genre)

if not missing_genres:
    print("\n✓ All genres have tracks! No missing genres.")
    sys.exit(0)

print(f"\nFound {len(missing_genres)} genres with 0 tracks:\n")

for genre in missing_genres:
    print(f"\n{'='*70}")
    print(f"GENRE: {genre}")
    print('='*70)

    # Check if genre has rules
    rules = GENRE_RULES.get(genre.lower(), {})
    if not rules:
        print("  ⚠️  No rules defined in GENRE_RULES")
        print("  → Will match any track with this genre tag")
    else:
        print(f"  Rules defined: {', '.join(rules.keys())}")

    # Check dataset for tracks with this genre tag
    matching_tracks = 0
    matching_sample = []
    for track in tracks[:5000]:  # Sample first 5k tracks for speed
        track_genres = [g.lower() for g in (track.get('artist_genres', []) or [])]
        if any(genre.lower() in g for g in track_genres):
            matching_tracks += 1
            if len(matching_sample) < 3:
                artist = (track.get('artists') or ['?'])[0]
                matching_sample.append(f"{artist} - {track.get('name', '?')}")

    if matching_tracks == 0:
        print(f"  ✗ NO TRACKS in dataset with '{genre}' tag")
        print("  → Dataset issue: Need to add tracks with this genre")
    else:
        print(f"  ✓ Found ~{matching_tracks} tracks with '{genre}' in genres")
        print("  Sample tracks:")
        for t in matching_sample:
            print(f"    • {t}")

        # Check if rules are filtering them out
        if rules:
            print("\n  ⚠️  Tracks exist but rules filter them out!")
            print("  Checking rules:")

            req = rules.get('require_artist_genres_any', [])
            if req:
                print(f"    require_artist_genres_any: {req[:3]}...")
                print("    → May be too strict")

            deny = rules.get('deny_artist_genres_any', [])
            if deny:
                print(f"    deny_artist_genres_any: {deny[:3]}...")

            min_year = rules.get('min_year')
            max_year = rules.get('max_year')
            if min_year or max_year:
                print(f"    Year range: {min_year or '?'} - {max_year or '?'}")

            pop_min = rules.get('popularity_min')
            pop_max = rules.get('popularity_max')
            if pop_min or pop_max:
                print(f"    Popularity range: {pop_min or '?'} - {pop_max or '?'}")

print("\n" + "="*70)
print("SUMMARY")
print("="*70)
print(f"Total missing: {len(missing_genres)}")
print("\nRecommendations:")
print("  1. For genres with NO dataset tracks: expand your dataset")
print("  2. For genres with tracks but strict rules: relax require_artist_genres_any")
print("  3. Consider removing very niche genres if dataset doesn't support them")
