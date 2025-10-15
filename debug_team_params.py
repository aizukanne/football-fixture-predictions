#!/usr/bin/env python3
"""
Debug script to trace exactly what happens when calculating team parameters.
Tests the exact flow that the Lambda would use.
"""

import sys
import os
from datetime import datetime

sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

print("\n" + "="*80)
print("DEBUG: Team Parameter Calculation for Manchester United")
print("="*80)

# Set API key
os.environ['RAPIDAPI_KEY'] = '4c37223acemsh65b1a8b456b72c1p15a99ajsnd4a09ab346a4'

try:
    from src.parameters.team_calculator import calculate_tactical_parameters
    from decimal import Decimal
    import pandas as pd

    team_id = 33  # Manchester United
    league_id = 39
    season = 2024
    prediction_date = datetime.now()

    print(f"\n1. Calling calculate_tactical_parameters({team_id}, {league_id}, {season})...")
    print("-" * 80)

    tactical_params = calculate_tactical_parameters(
        team_id=team_id,
        league_id=league_id,
        season=season,
        prediction_date=prediction_date
    )

    print("\n" + "="*80)
    print("TACTICAL PARAMETERS RESULT")
    print("="*80)

    # Check manager fields
    manager_fields = {k: v for k, v in tactical_params.items() if 'manager' in k.lower()}

    print(f"\nManager fields found: {len(manager_fields)}")
    for field, value in sorted(manager_fields.items()):
        if isinstance(value, Decimal):
            value = float(value)
        elif isinstance(value, dict):
            value = "{...}"
        print(f"  {field}: {value}")

    # Key question: Is manager data real or default?
    manager_name = tactical_params.get('manager_name', 'N/A')
    manager_available = tactical_params.get('manager_profile_available', False)

    print(f"\n{'='*80}")
    print("DIAGNOSIS")
    print("="*80)
    print(f"Manager Name: {manager_name}")
    print(f"Profile Available: {manager_available}")

    if manager_name == 'Unknown' or not manager_available:
        print(f"\n❌ PROBLEM: Manager data is using defaults!")
        print(f"\nPossible causes:")
        print(f"  1. TacticalAnalyzer.get_manager_tactical_profile() not being called")
        print(f"  2. ManagerAnalyzer.get_manager_profile() returning defaults")
        print(f"  3. API call failing silently")
    else:
        print(f"\n✅ SUCCESS: Real manager data retrieved!")
        print(f"   Manager: {manager_name}")

except Exception as e:
    print(f"\n❌ ERROR: {e}")
    import traceback
    traceback.print_exc()
