#!/usr/bin/env python3
"""
Automatically fix overly broad deny rules that conflict with the target genre.
"""

import json
import re

# Load GENRE_RULES
exec(open('killmegod.py').read().split('# -------- Matching logic --------')[0])

# Terms that are too broad and cause false positives
OVERLY_BROAD_SINGLE_WORDS = ['pop', 'punk', 'rock', 'rap', 'trap', 'edm', 'house', 'jazz', 'funk']

fixes_made = []

for genre, rules in GENRE_RULES.items():
    deny_list = rules.get('deny_artist_genres_any', [])
    if not deny_list:
        continue

    # Check if genre itself contains any broad terms
    genre_words = set(genre.lower().split())

    new_deny_list = []
    removed = []

    for deny_term in deny_list:
        deny_words = deny_term.lower().split()

        # Remove if it's a single broad word that appears in the genre name
        if len(deny_words) == 1 and deny_term.lower() in OVERLY_BROAD_SINGLE_WORDS:
            # Check if this word is in the genre name
            if deny_term.lower() in genre.lower():
                removed.append(deny_term)
                continue

        # Remove if deny term words overlap with genre words
        if genre_words & set(deny_words):
            removed.append(deny_term)
            continue

        new_deny_list.append(deny_term)

    if removed:
        fixes_made.append((genre, removed, len(deny_list), len(new_deny_list)))
        rules['deny_artist_genres_any'] = new_deny_list

print("="*80)
print("DENY RULE FIXES")
print("="*80)
print(f"\nFixed {len(fixes_made)} genres:\n")

for genre, removed, old_count, new_count in fixes_made:
    print(f"{genre}:")
    print(f"  Removed {len(removed)} terms: {', '.join(removed)}")
    print(f"  Deny list: {old_count} → {new_count} items")
    print()

# Write updated rules back to file
print("\nGenerating updated GENRE_RULES...")
print("(You'll need to manually copy this into killmegod.py)")
print("\n" + "="*80)
print("UPDATED GENRE_RULES:")
print("="*80)

# Just show a few examples
for genre in ['post-punk', 'bebop', 'dubstep'][:3]:
    if genre in GENRE_RULES:
        print(f'\n"{genre}": {{')
        for key, val in GENRE_RULES[genre].items():
            if isinstance(val, list):
                print(f'    "{key}": {json.dumps(val)},')
            else:
                print(f'    "{key}": {json.dumps(val)},')
        print('},')

print("\n... (showing first 3, apply pattern to all fixed genres)")
