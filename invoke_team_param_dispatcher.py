#!/usr/bin/env python3
"""
Invoke the team parameter dispatcher Lambda function to trigger recalculation.
This will populate the new manager analysis data in team parameters.
"""

import json
import boto3
import sys

def invoke_dispatcher(dry_run=False, league_ids=None, all_leagues=False):
    """
    Invoke the team parameter dispatcher Lambda function.

    Args:
        dry_run: If True, don't actually send SQS messages
        league_ids: List of specific league IDs to process (e.g., [39] for Premier League)
        all_leagues: If True, process all leagues
    """
    lambda_client = boto3.client('lambda', region_name='eu-west-2')

    # Build payload
    payload = {
        'trigger_type': 'manual',
        'force_recompute': True,
        'dry_run': dry_run
    }

    # Add league filter if specified
    if league_ids and not all_leagues:
        payload['league_filter'] = {
            'league_ids': league_ids
        }

    print("=" * 80)
    print("INVOKING TEAM PARAMETER DISPATCHER")
    print("=" * 80)
    print(f"Mode: {'DRY RUN' if dry_run else 'LIVE EXECUTION'}")
    if league_ids and not all_leagues:
        print(f"Leagues: {league_ids}")
    elif all_leagues:
        print(f"Leagues: ALL LEAGUES")
    else:
        print(f"Leagues: ALL LEAGUES (no filter)")
    print(f"Force Recompute: True")
    print("=" * 80)

    # Invoke Lambda
    try:
        response = lambda_client.invoke(
            FunctionName='football-team-parameter-dispatcher-prod',
            InvocationType='RequestResponse',
            Payload=json.dumps(payload)
        )

        # Parse response
        response_payload = json.loads(response['Payload'].read())

        print("\n✅ Lambda invoked successfully")
        print(f"Status Code: {response['StatusCode']}")

        # Parse body
        if 'body' in response_payload:
            body = json.loads(response_payload['body']) if isinstance(response_payload['body'], str) else response_payload['body']

            print("\n" + "=" * 80)
            print("DISPATCHER RESULTS")
            print("=" * 80)
            print(f"Total Leagues: {body.get('total_leagues', 'N/A')}")
            print(f"Messages Sent: {body.get('messages_sent', 'N/A')}")
            print(f"Successful: {body.get('successful', 'N/A')}")
            print(f"Failed: {body.get('failed', 'N/A')}")
            print(f"Execution Time: {body.get('execution_time_ms', 'N/A')}ms")
            print(f"Queue URL: {body.get('queue_url', 'N/A')}")

            if body.get('errors'):
                print(f"\n⚠️  Errors:")
                for error in body['errors']:
                    print(f"  - {error.get('league_name', 'Unknown')}: {error.get('error', 'Unknown error')}")

            if body.get('leagues_processed'):
                print(f"\n📋 Leagues Processed:")
                for league in body['leagues_processed'][:10]:  # Show first 10
                    status = "✓" if league.get('status') == 'sent' else "○"
                    print(f"  {status} {league.get('league_name', 'Unknown')} (ID: {league.get('league_id', 'N/A')})")

                if len(body['leagues_processed']) > 10:
                    print(f"  ... and {len(body['leagues_processed']) - 10} more")

            print("=" * 80)

            # Print full response if errors
            if body.get('errors') or body.get('failed', 0) > 0:
                print("\nFull Response:")
                print(json.dumps(body, indent=2))

            return body

        else:
            print("\n⚠️  Unexpected response format:")
            print(json.dumps(response_payload, indent=2))
            return None

    except Exception as e:
        print(f"\n❌ Error invoking Lambda: {e}")
        import traceback
        traceback.print_exc()
        return None


def main():
    """Main function."""
    import argparse

    parser = argparse.ArgumentParser(description='Invoke team parameter dispatcher')
    parser.add_argument('--dry-run', action='store_true', help='Dry run mode (no actual messages sent)')
    parser.add_argument('--league-ids', type=int, nargs='+', help='Specific league IDs to process (e.g., 39 140)')
    parser.add_argument('--all-leagues', action='store_true', help='Process all leagues')
    parser.add_argument('--test', action='store_true', help='Test with Premier League only')

    args = parser.parse_args()

    # Determine what to run
    if args.test:
        print("\n🧪 TEST MODE: Running for Championship (ID: 40) only\n")
        result = invoke_dispatcher(dry_run=args.dry_run, league_ids=[40], all_leagues=False)
    elif args.league_ids:
        result = invoke_dispatcher(dry_run=args.dry_run, league_ids=args.league_ids, all_leagues=False)
    elif args.all_leagues:
        print("\n⚠️  You are about to trigger recalculation for ALL leagues.")
        print("This will process 60+ leagues and may take significant time.")
        confirm = input("Continue? (yes/no): ")
        if confirm.lower() != 'yes':
            print("Aborted.")
            return
        result = invoke_dispatcher(dry_run=args.dry_run, all_leagues=True)
    else:
        print("\n❌ Error: You must specify either --test, --league-ids, or --all-leagues")
        parser.print_help()
        return

    if result:
        print("\n✅ DISPATCHER INVOCATION COMPLETE")
        if not args.dry_run:
            print("\n📊 Next Steps:")
            print("   1. Monitor SQS queue: football_football-team-parameter-updates_prod")
            print("   2. Check CloudWatch logs: /aws/lambda/football-team-parameter-handler-prod")
            print("   3. Verify team parameters include manager data")
            print(f"\n💡 Expected processing time: ~{result.get('total_leagues', 0) * 30}s for all teams")
    else:
        print("\n❌ DISPATCHER INVOCATION FAILED")
        sys.exit(1)


if __name__ == "__main__":
    main()
