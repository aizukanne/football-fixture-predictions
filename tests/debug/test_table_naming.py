"""Test script to verify table naming with prefix/suffix"""

import os
import sys

# Add src to path
sys.path.insert(0, os.path.abspath('.'))

from src.utils.constants import _get_table_name, TABLE_PREFIX, TABLE_SUFFIX, ENVIRONMENT

print("=" * 70)
print("Table Naming Verification")
print("=" * 70)
print()
print(f"Environment Configuration:")
print(f"  ENVIRONMENT: {ENVIRONMENT}")
print(f"  TABLE_PREFIX: '{TABLE_PREFIX}'")
print(f"  TABLE_SUFFIX: '{TABLE_SUFFIX}'")
print()
print("=" * 70)
print("Table Names That Will Be Created:")
print("=" * 70)
print()

tables = [
    'game_fixtures',
    'league_parameters',
    'team_parameters',
    'venue_cache',
    'tactical_cache',
    'league_standings_cache',
    'fixture_events_cache'
]

for table in tables:
    full_name = _get_table_name(table)
    print(f"  {table:30s} -> {full_name}")

print()
print("=" * 70)
print("Verification Complete")
print("=" * 70)