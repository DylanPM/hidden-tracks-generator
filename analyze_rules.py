#!/usr/bin/env python3
"""
Comprehensive analysis of GENRE_RULES to identify patterns and problems.
"""

import sys
import re
sys.path.insert(0, '.')

# Load GENRE_RULES
exec(open('killmegod.py').read().split('PLAYABLE_GENRES =')[0])

print("="*80)
print("GENRE_RULES ANALYSIS")
print("="*80)

print(f"\nTotal genres with rules: {len(GENRE_RULES)}")

# Analyze rule types
rule_types = {}
for genre, rules in GENRE_RULES.items():
    for rule_key in rules.keys():
        if rule_key not in rule_types:
            rule_types[rule_key] = 0
        rule_types[rule_key] += 1

print("\nRule type usage:")
for rule_type, count in sorted(rule_types.items(), key=lambda x: x[1], reverse=True):
    print(f"  {rule_type:<30} {count:>3} genres")

# Find self-conflicting deny rules
print("\n" + "="*80)
print("SELF-CONFLICTING DENY RULES (deny contains target genre)")
print("="*80)

self_conflicts = []
for genre, rules in GENRE_RULES.items():
    deny_list = rules.get('deny_artist_genres_any', [])
    genre_words = set(genre.lower().split())

    for deny_term in deny_list:
        deny_words = deny_term.lower().split()
        # Check if deny term would match the genre itself via substring
        if any(dw in genre.lower() for dw in deny_words):
            self_conflicts.append((genre, deny_term, 'substring match'))
        # Check if genre contains deny word
        if any(dw in genre_words for dw in deny_words):
            self_conflicts.append((genre, deny_term, 'word overlap'))

if self_conflicts:
    for genre, deny_term, reason in self_conflicts[:20]:
        print(f"  {genre:<25} denies '{deny_term}' ({reason})")
    if len(self_conflicts) > 20:
        print(f"  ... and {len(self_conflicts) - 20} more")
else:
    print("  None found")

# Find overly broad deny terms
print("\n" + "="*80)
print("OVERLY BROAD DENY TERMS (short words that catch many substrings)")
print("="*80)

broad_denies = {}
for genre, rules in GENRE_RULES.items():
    deny_list = rules.get('deny_artist_genres_any', [])
    for deny_term in deny_list:
        if len(deny_term) <= 5 and not deny_term.startswith('r&b'):
            if deny_term not in broad_denies:
                broad_denies[deny_term] = []
            broad_denies[deny_term].append(genre)

for term, genres in sorted(broad_denies.items(), key=lambda x: len(x[1]), reverse=True)[:15]:
    print(f"  '{term}':<15 used by {len(genres):>2} genres: {', '.join(genres[:3])}...")

# Check require vs deny conflicts
print("\n" + "="*80)
print("REQUIRE vs DENY CONFLICTS (same genre in both lists)")
print("="*80)

conflicts = []
for genre, rules in GENRE_RULES.items():
    require = set([r.lower() for r in rules.get('require_artist_genres_any', [])])
    deny = set([d.lower() for d in rules.get('deny_artist_genres_any', [])])

    overlap = require & deny
    if overlap:
        conflicts.append((genre, list(overlap)))

if conflicts:
    for genre, overlaps in conflicts[:10]:
        print(f"  {genre}: {overlaps}")
else:
    print("  None found")

# Analyze year ranges
print("\n" + "="*80)
print("YEAR RANGE ANALYSIS")
print("="*80)

year_ranges = []
for genre, rules in GENRE_RULES.items():
    min_year = rules.get('min_year')
    max_year = rules.get('max_year')
    if min_year and max_year:
        span = max_year - min_year
        year_ranges.append((genre, min_year, max_year, span))

print("\nNarrowest year ranges (potentially too restrictive):")
for genre, min_y, max_y, span in sorted(year_ranges, key=lambda x: x[3])[:10]:
    print(f"  {genre:<25} {min_y}-{max_y} ({span} years)")

print("\nWidest year ranges:")
for genre, min_y, max_y, span in sorted(year_ranges, key=lambda x: x[3], reverse=True)[:10]:
    print(f"  {genre:<25} {min_y}-{max_y} ({span} years)")

# Analyze popularity ranges
print("\n" + "="*80)
print("POPULARITY RANGE ANALYSIS")
print("="*80)

pop_ranges = []
for genre, rules in GENRE_RULES.items():
    pop_min = rules.get('popularity_min')
    pop_max = rules.get('popularity_max')
    if pop_min and pop_max:
        span = pop_max - pop_min
        pop_ranges.append((genre, pop_min, pop_max, span))

print("\nNarrowest popularity ranges (potentially too restrictive):")
for genre, min_p, max_p, span in sorted(pop_ranges, key=lambda x: x[3])[:10]:
    print(f"  {genre:<25} {min_p}-{max_p} (span: {span})")

# Count genres with whitelists
print("\n" + "="*80)
print("WHITELIST USAGE")
print("="*80)

whitelist_count = sum(1 for rules in GENRE_RULES.values() if rules.get('whitelist_artists'))
print(f"Genres with whitelist: {whitelist_count}/{len(GENRE_RULES)}")

largest_whitelists = []
for genre, rules in GENRE_RULES.items():
    wl = rules.get('whitelist_artists', [])
    if wl:
        largest_whitelists.append((genre, len(wl)))

print("\nLargest whitelists:")
for genre, count in sorted(largest_whitelists, reverse=True)[:10]:
    print(f"  {genre:<25} {count} artists")

print("\n" + "="*80)
print("RECOMMENDATIONS")
print("="*80)
print("""
1. Add word boundary matching to deny rules
   - Change: "punk" deny shouldn't catch "post-punk"
   - Use: \\b{term}\\b regex for exact word matching

2. Remove overly short deny terms
   - "pop", "punk", "rock" are too broad
   - Use compound terms: "pop rock", "punk rock" instead

3. Fix self-conflicting rules
   - post-punk shouldn't deny "punk"
   - bebop shouldn't deny "bop"

4. Relax year ranges for genres with few tracks
   - Expand ranges by 5-10 years for genres with <5 tracks

5. Consider tiered deny system
   - HARD_DENY: Never allow (e.g., "christmas", "soundtrack")
   - SOFT_DENY: Penalize score but don't exclude

6. Simplify require_artist_genres_any
   - Many have redundant entries
   - Consolidate similar terms
""")
