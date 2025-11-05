#!/usr/bin/env python3
"""
Script to update match scores for October 1 - November 2, 2025.
Fills gaps in score data by triggering the match data handler.
"""

import sys
import os
from datetime import datetime

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.handlers.match_data_handler import lambda_handler


def main():
    """Trigger match data update for October 1 - November 2, 2025."""

    # Date range: October 1 - November 2, 2025
    start_date = datetime(2025, 10, 1, 0, 0, 0)
    end_date = datetime(2025, 11, 2, 23, 59, 59)

    start_timestamp = int(start_date.timestamp())
    end_timestamp = int(end_date.timestamp())

    print("=" * 80)
    print("MATCH SCORE UPDATE - October 1 to November 2, 2025")
    print("=" * 80)
    print(f"Start: {start_date}")
    print(f"End:   {end_date}")
    print(f"Start Timestamp: {start_timestamp}")
    print(f"End Timestamp:   {end_timestamp}")
    print("=" * 80)
    print()

    # Create event payload
    event = {
        "time_range": {
            "start": start_timestamp,
            "end": end_timestamp
        }
    }

    # Mock context (not used by the handler but required by Lambda signature)
    context = {}

    # Invoke the handler
    print("Invoking match data handler...")
    print()

    try:
        response = lambda_handler(event, context)

        print()
        print("=" * 80)
        print("UPDATE COMPLETE")
        print("=" * 80)
        print(f"Status Code: {response.get('statusCode')}")

        # Parse and display results
        import json
        body = json.loads(response.get('body', '{}'))

        print(f"\nResults:")
        print(f"  Processed Leagues: {body.get('processed_leagues', 0)}")
        print(f"  Updated Fixtures: {body.get('updated_fixtures', 0)}")
        print(f"  Failed Updates: {body.get('failed_updates', 0)}")

        # Show league breakdown
        league_results = body.get('league_results', [])
        if league_results:
            print(f"\nLeague Breakdown:")
            for league_result in league_results:
                if league_result.get('updated_count', 0) > 0:
                    print(f"  {league_result['league_name']} ({league_result['country']}): "
                          f"{league_result['updated_count']} fixtures updated")

        print("=" * 80)

        return response

    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        return None


if __name__ == "__main__":
    main()
