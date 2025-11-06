#!/usr/bin/env python3
"""Quick analysis of missing genres in killmegod.py output"""

import json
import sys
import re

# Load the generated manifest
with open('genre_constellation_manifest.json', 'r') as f:
    manifest = json.load(f)

# Extract expected genres from GENRE_TREE in killmegod.py
with open('killmegod.py', 'r') as f:
    content = f.read()

# Find all "_seeds" entries
seeds_in_tree = set(re.findall(r'"_seeds":\s*"([^"]+)"', content))

# Find all genres that actually got seeds in the manifest
def extract_genres_with_seeds(node, found=None):
    if found is None:
        found = set()
    if isinstance(node, dict):
        if 'seeds' in node and node['seeds']:
            # Try to figure out genre name - not perfect but close enough
            pass
        if 'subgenres' in node:
            for name, child in node['subgenres'].items():
                if isinstance(child, dict) and 'seeds' in child and child['seeds']:
                    found.add(name)
                extract_genres_with_seeds(child, found)
    return found

genres_with_seeds = set()
for root_name, root_node in manifest.items():
    if root_name in ['global', 'build']:
        continue
    if isinstance(root_node, dict):
        if 'seeds' in root_node and root_node['seeds']:
            genres_with_seeds.add(root_name)
        if 'subgenres' in root_node:
            for name, child in root_node['subgenres'].items():
                if isinstance(child, dict) and 'seeds' in child and child['seeds']:
                    genres_with_seeds.add(name)
                if isinstance(child, dict) and 'subgenres' in child:
                    for name2, child2 in child['subgenres'].items():
                        if isinstance(child2, dict) and 'seeds' in child2 and child2['seeds']:
                            genres_with_seeds.add(name2)

print(f"Seeds defined in GENRE_TREE: {len(seeds_in_tree)}")
print(f"Genres with seeds in manifest: {len(genres_with_seeds)}")
print(f"\nMISSING GENRES (in tree but no seeds in manifest):")
print("="*60)

missing = sorted(seeds_in_tree - genres_with_seeds)
for genre in missing:
    print(f"  ✗ {genre}")

print(f"\nTotal missing: {len(missing)}")
