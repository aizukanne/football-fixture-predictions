#!/usr/bin/env python3
"""
Manual trigger script for match predictions.

This script retrieves fixtures for a specific league and date range,
then sends them to the SQS queue for prediction processing.

Usage:
    python trigger_predictions_manual.py --league-id 39 --start-date 2026-02-20 --end-date 2026-02-23
    
Author: Football Fixture Prediction System
Purpose: Debug mode - Manual prediction triggering
"""

import os
import sys
import json
import boto3
import argparse
from datetime import datetime
from typing import List, Dict, Optional

# Add project root to path
project_root = os.path.dirname(os.path.abspath(__file__))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from src.data.fixture_retrieval import FixtureRetriever
from src.utils.fixture_formatter import FixtureFormatter
from src.config.leagues_config import get_league_info
from src.utils.constants import FIXTURES_QUEUE_URL, RAPIDAPI_KEY
from src.infrastructure.version_manager import VersionManager


class PredictionTrigger:
    """Manual trigger for match predictions with diagnostic logging."""
    
    def __init__(self, dry_run: bool = False):
        """
        Initialize prediction trigger.
        
        Args:
            dry_run: If True, don't actually send messages to SQS
        """
        self.dry_run = dry_run
        self.retriever = None
        self.formatter = FixtureFormatter()
        self.sqs = boto3.client('sqs') if not dry_run else None
        self.version_manager = VersionManager()
        
        # Diagnostic counters
        self.diagnostics = {
            'fixtures_retrieved': 0,
            'fixtures_formatted': 0,
            'fixtures_sent': 0,
            'api_errors': 0,
            'formatting_errors': 0,
            'queue_errors': 0,
            'warnings': []
        }
    
    def check_environment(self) -> bool:
        """
        Check required environment variables and permissions.
        
        Returns:
            True if environment is valid, False otherwise
        """
        print("=" * 70)
        print("ENVIRONMENT DIAGNOSTIC CHECK")
        print("=" * 70)
        
        issues = []
        
        # Check RAPIDAPI_KEY (uses fallback from constants if env var not set)
        if not RAPIDAPI_KEY:
            issues.append("❌ RAPIDAPI_KEY not available (check environment variable or constants.py)")
        else:
            api_key_source = "environment" if os.getenv('RAPIDAPI_KEY') else "constants.py (fallback)"
            print(f"✅ RAPIDAPI_KEY: {'*' * 20}{RAPIDAPI_KEY[-4:]} (from {api_key_source})")
        
        # Check FIXTURES_QUEUE_URL
        if not FIXTURES_QUEUE_URL or '{account_id}' in FIXTURES_QUEUE_URL:
            issues.append("❌ FIXTURES_QUEUE_URL not properly configured")
            print(f"❌ FIXTURES_QUEUE_URL: {FIXTURES_QUEUE_URL}")
        else:
            print(f"✅ FIXTURES_QUEUE_URL: {FIXTURES_QUEUE_URL}")
        
        # Check AWS credentials
        try:
            sts = boto3.client('sts')
            identity = sts.get_caller_identity()
            print(f"✅ AWS Account: {identity['Account']}")
            print(f"✅ AWS ARN: {identity['Arn']}")
        except Exception as e:
            issues.append(f"❌ AWS credentials error: {e}")
        
        # Check architecture version
        try:
            current_version = self.version_manager.get_current_version()
            print(f"✅ Architecture Version: {current_version}")
        except Exception as e:
            self.diagnostics['warnings'].append(f"Version manager error: {e}")
            print(f"⚠️  Version Manager: {e}")
        
        print("=" * 70)
        
        if issues:
            print("\n🚨 ENVIRONMENT ISSUES DETECTED:")
            for issue in issues:
                print(f"  {issue}")
            return False
        
        print("✅ Environment check passed\n")
        return True
    
    def trigger_predictions(self, league_id: int, start_date: str, 
                          end_date: str) -> Dict:
        """
        Trigger predictions for specific league and date range.
        
        Args:
            league_id: League identifier (e.g., 39 for Premier League)
            start_date: Start date in YYYY-MM-DD format
            end_date: End date in YYYY-MM-DD format
            
        Returns:
            Dictionary with execution summary and diagnostics
        """
        print("=" * 70)
        print("PREDICTION TRIGGER EXECUTION")
        print("=" * 70)
        
        # Get league information
        league_info = get_league_info(league_id)
        if not league_info:
            error_msg = f"League ID {league_id} not found in configuration"
            print(f"❌ {error_msg}")
            self.diagnostics['warnings'].append(error_msg)
            return {
                'success': False,
                'error': error_msg,
                'diagnostics': self.diagnostics
            }
        
        print(f"League: {league_info['name']}")
        print(f"Country: {league_info['country']}")
        print(f"League ID: {league_id}")
        print(f"Date Range: {start_date} to {end_date}")
        print(f"Mode: {'DRY RUN' if self.dry_run else 'LIVE'}")
        print("=" * 70)
        print()
        
        # Initialize retriever (needs API key)
        try:
            self.retriever = FixtureRetriever()
            print("✅ FixtureRetriever initialized")
        except ValueError as e:
            error_msg = f"Failed to initialize FixtureRetriever: {e}"
            print(f"❌ {error_msg}")
            self.diagnostics['api_errors'] += 1
            return {
                'success': False,
                'error': error_msg,
                'diagnostics': self.diagnostics
            }
        
        # Step 1: Retrieve fixtures
        print(f"\n📡 Retrieving fixtures from RapidAPI...")
        try:
            fixtures = self.retriever.get_league_fixtures(
                league_id=league_id,
                start_date=start_date,
                end_date=end_date
            )
            self.diagnostics['fixtures_retrieved'] = len(fixtures)
            
            if not fixtures:
                warning_msg = f"No fixtures found for league {league_id} between {start_date} and {end_date}"
                print(f"⚠️  {warning_msg}")
                self.diagnostics['warnings'].append(warning_msg)
                return {
                    'success': True,
                    'fixtures_processed': 0,
                    'message': 'No fixtures found in date range',
                    'diagnostics': self.diagnostics
                }
            
            print(f"✅ Retrieved {len(fixtures)} fixtures")
            
            # Display fixture details
            print(f"\n📋 FIXTURE DETAILS:")
            for i, fixture in enumerate(fixtures, 1):
                print(f"  {i}. {fixture['home_team']} vs {fixture['away_team']}")
                print(f"     Date: {fixture['date']}")
                print(f"     Fixture ID: {fixture['fixture_id']}")
                print(f"     Season: {fixture['season']}")
                
        except Exception as e:
            error_msg = f"Error retrieving fixtures: {e}"
            print(f"❌ {error_msg}")
            self.diagnostics['api_errors'] += 1
            return {
                'success': False,
                'error': error_msg,
                'diagnostics': self.diagnostics
            }
        
        # Step 2: Format fixtures
        print(f"\n🔧 Formatting fixtures for queue...")
        try:
            formatted_fixtures = self.formatter.format_fixtures_for_queue(
                fixtures=fixtures,
                league_info=league_info
            )
            self.diagnostics['fixtures_formatted'] = len(formatted_fixtures)
            
            if len(formatted_fixtures) < len(fixtures):
                warning_msg = f"Some fixtures failed validation: {len(fixtures) - len(formatted_fixtures)} skipped"
                print(f"⚠️  {warning_msg}")
                self.diagnostics['warnings'].append(warning_msg)
                self.diagnostics['formatting_errors'] = len(fixtures) - len(formatted_fixtures)
            
            print(f"✅ Formatted {len(formatted_fixtures)} fixtures")
            
        except Exception as e:
            error_msg = f"Error formatting fixtures: {e}"
            print(f"❌ {error_msg}")
            self.diagnostics['formatting_errors'] += 1
            return {
                'success': False,
                'error': error_msg,
                'diagnostics': self.diagnostics
            }
        
        # Step 3: Send to SQS queue
        if self.dry_run:
            print(f"\n🧪 DRY RUN MODE - Would send {len(formatted_fixtures)} fixtures to queue")
            print(f"   Queue URL: {FIXTURES_QUEUE_URL}")
            self.diagnostics['fixtures_sent'] = len(formatted_fixtures)
        else:
            print(f"\n📤 Sending fixtures to SQS queue...")
            try:
                # Add version metadata
                current_timestamp = int(datetime.now().timestamp())
                current_version = self.version_manager.get_current_version()
                
                for fixture in formatted_fixtures:
                    fixture['prediction_metadata'] = {
                        'architecture_version': current_version,
                        'ingestion_date': current_timestamp
                    }
                
                # Send to queue
                response = self._send_to_queue(formatted_fixtures, league_info)
                
                if response['success']:
                    self.diagnostics['fixtures_sent'] = len(formatted_fixtures)
                    print(f"✅ Successfully sent {len(formatted_fixtures)} fixtures to queue")
                    print(f"   Message ID: {response.get('message_id', 'N/A')}")
                else:
                    self.diagnostics['queue_errors'] += 1
                    error_msg = f"Failed to send to queue: {response.get('error', 'Unknown')}"
                    print(f"❌ {error_msg}")
                    return {
                        'success': False,
                        'error': error_msg,
                        'diagnostics': self.diagnostics
                    }
                    
            except Exception as e:
                error_msg = f"Error sending to queue: {e}"
                print(f"❌ {error_msg}")
                self.diagnostics['queue_errors'] += 1
                return {
                    'success': False,
                    'error': error_msg,
                    'diagnostics': self.diagnostics
                }
        
        # Summary
        print(f"\n{'=' * 70}")
        print("EXECUTION SUMMARY")
        print("=" * 70)
        print(f"✅ Fixtures Retrieved: {self.diagnostics['fixtures_retrieved']}")
        print(f"✅ Fixtures Formatted: {self.diagnostics['fixtures_formatted']}")
        print(f"✅ Fixtures Sent: {self.diagnostics['fixtures_sent']}")
        
        if self.diagnostics['api_errors'] > 0:
            print(f"❌ API Errors: {self.diagnostics['api_errors']}")
        if self.diagnostics['formatting_errors'] > 0:
            print(f"⚠️  Formatting Errors: {self.diagnostics['formatting_errors']}")
        if self.diagnostics['queue_errors'] > 0:
            print(f"❌ Queue Errors: {self.diagnostics['queue_errors']}")
        
        if self.diagnostics['warnings']:
            print(f"\n⚠️  WARNINGS ({len(self.diagnostics['warnings'])}):")
            for warning in self.diagnostics['warnings']:
                print(f"  - {warning}")
        
        print("=" * 70)
        
        return {
            'success': True,
            'fixtures_processed': len(formatted_fixtures),
            'message': f"Successfully triggered predictions for {len(formatted_fixtures)} fixtures",
            'diagnostics': self.diagnostics
        }
    
    def _send_to_queue(self, fixtures: List[Dict], league_info: Dict) -> Dict:
        """
        Send formatted fixtures to SQS queue.
        
        Args:
            fixtures: List of formatted fixture data
            league_info: League metadata
            
        Returns:
            Dict with success status and message ID or error
        """
        try:
            message_body = {
                'payload': fixtures,
                'league_info': league_info,
                'timestamp': int(datetime.now().timestamp()),
                'source': 'manual_trigger',
                'fixture_count': len(fixtures)
            }
            
            response = self.sqs.send_message(
                QueueUrl=FIXTURES_QUEUE_URL,
                MessageBody=json.dumps(message_body, default=str),
                MessageAttributes={
                    'league_id': {
                        'StringValue': str(league_info['id']),
                        'DataType': 'String'
                    },
                    'league_name': {
                        'StringValue': league_info['name'],
                        'DataType': 'String'
                    },
                    'country': {
                        'StringValue': league_info.get('country', 'Unknown'),
                        'DataType': 'String'
                    },
                    'fixture_count': {
                        'StringValue': str(len(fixtures)),
                        'DataType': 'Number'
                    },
                    'source': {
                        'StringValue': 'manual_trigger',
                        'DataType': 'String'
                    }
                }
            )
            
            return {
                'success': True,
                'message_id': response['MessageId']
            }
            
        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }


def main():
    """Main entry point for manual prediction triggering."""
    parser = argparse.ArgumentParser(
        description='Manually trigger match predictions for specific league and date range',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Trigger predictions for Premier League (Feb 20-23, 2026)
  python trigger_predictions_manual.py --league-id 39 --start-date 2026-02-20 --end-date 2026-02-23
  
  # Dry run mode (test without sending to queue)
  python trigger_predictions_manual.py --league-id 39 --start-date 2026-02-20 --end-date 2026-02-23 --dry-run
  
  # Check environment only
  python trigger_predictions_manual.py --check-env
        """
    )
    
    parser.add_argument('--league-id', type=int, help='League ID (e.g., 39 for Premier League)')
    parser.add_argument('--start-date', type=str, help='Start date in YYYY-MM-DD format')
    parser.add_argument('--end-date', type=str, help='End date in YYYY-MM-DD format')
    parser.add_argument('--dry-run', action='store_true', help='Test mode - do not send to SQS')
    parser.add_argument('--check-env', action='store_true', help='Only check environment configuration')
    
    args = parser.parse_args()
    
    # Initialize trigger
    trigger = PredictionTrigger(dry_run=args.dry_run)
    
    # Check environment
    if not trigger.check_environment():
        print("\n❌ Environment check failed. Please fix the issues above.")
        sys.exit(1)
    
    # If only checking environment, exit now
    if args.check_env:
        print("✅ Environment check completed successfully")
        sys.exit(0)
    
    # Validate arguments
    if not args.league_id or not args.start_date or not args.end_date:
        parser.print_help()
        print("\n❌ Error: --league-id, --start-date, and --end-date are required")
        sys.exit(1)
    
    # Validate date format
    try:
        datetime.strptime(args.start_date, '%Y-%m-%d')
        datetime.strptime(args.end_date, '%Y-%m-%d')
    except ValueError:
        print("❌ Error: Dates must be in YYYY-MM-DD format")
        sys.exit(1)
    
    # Execute trigger
    result = trigger.trigger_predictions(
        league_id=args.league_id,
        start_date=args.start_date,
        end_date=args.end_date
    )
    
    # Exit with appropriate code
    if result['success']:
        print("\n✅ Prediction trigger completed successfully")
        sys.exit(0)
    else:
        print(f"\n❌ Prediction trigger failed: {result.get('error', 'Unknown error')}")
        sys.exit(1)


if __name__ == '__main__':
    main()
