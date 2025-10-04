"""
DynamoDB Table Deployment Script

This script deploys all required DynamoDB tables for the Football Fixture
Prediction System with environment-specific naming and configuration.

Features:
- Environment-based table naming (TABLE_PREFIX, TABLE_SUFFIX)
- Interactive and automated deployment modes
- Comprehensive table creation with proper schemas
- Verification and testing of deployed tables
- Support for multiple environments (dev, staging, prod)

Usage:
    # Interactive mode (prompts for environment details)
    python -m src.infrastructure.deploy_tables

    # Automated mode with environment variables
    TABLE_PREFIX=myapp_ TABLE_SUFFIX=_prod ENVIRONMENT=prod python -m src.infrastructure.deploy_tables

    # Test mode (prints configuration without deploying)
    python -m src.infrastructure.deploy_tables --dry-run

Author: Football Fixture Prediction System
Phase: Infrastructure - Table Isolation for AWS Deployment
"""

import boto3
import logging
import sys
import os
import argparse
from typing import Dict, List, Tuple
from botocore.exceptions import ClientError

# Add src to path for imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))
from src.utils.constants import _get_table_name, get_table_config, ENVIRONMENT, TABLE_PREFIX, TABLE_SUFFIX

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class TableDeployer:
    """Manages deployment of all DynamoDB tables for the prediction system."""

    def __init__(self, dry_run: bool = False):
        """
        Initialize the table deployer.

        Args:
            dry_run: If True, print configuration without deploying tables
        """
        self.dry_run = dry_run
        self.dynamodb = boto3.resource('dynamodb')
        self.client = boto3.client('dynamodb')
        self.deployment_results = {}

    def print_configuration(self):
        """Print current table configuration."""
        config = get_table_config()

        logger.info("=" * 70)
        logger.info("TABLE DEPLOYMENT CONFIGURATION")
        logger.info("=" * 70)
        logger.info(f"Environment: {config['environment']}")
        logger.info(f"Table Prefix: '{config['prefix']}' (empty = no prefix)")
        logger.info(f"Table Suffix: '{config['suffix']}' (empty = no suffix)")
        logger.info("")
        logger.info("Tables to be deployed:")
        logger.info("-" * 70)

        for base_name, full_name in config['tables'].items():
            logger.info(f"  {base_name:30s} -> {full_name}")

        logger.info("=" * 70)

    def create_game_fixtures_table(self) -> bool:
        """
        Create the game_fixtures table for storing fixture predictions.

        Returns:
            True if successful, False otherwise
        """
        table_name = _get_table_name('game_fixtures')

        if self.dry_run:
            logger.info(f"[DRY RUN] Would create table: {table_name}")
            return True

        try:
            # Check if table exists
            try:
                self.dynamodb.Table(table_name).load()
                logger.info(f"Table {table_name} already exists")
                return True
            except ClientError as e:
                if e.response['Error']['Code'] != 'ResourceNotFoundException':
                    raise

            # Create table
            logger.info(f"Creating table: {table_name}")

            table = self.dynamodb.create_table(
                TableName=table_name,
                KeySchema=[
                    {'AttributeName': 'fixture_id', 'KeyType': 'HASH'}
                ],
                AttributeDefinitions=[
                    {'AttributeName': 'fixture_id', 'AttributeType': 'N'}
                ],
                BillingMode='PAY_PER_REQUEST',
                Tags=[
                    {'Key': 'Project', 'Value': 'football-fixture-predictions'},
                    {'Key': 'Environment', 'Value': ENVIRONMENT},
                    {'Key': 'Purpose', 'Value': 'fixture-predictions'}
                ]
            )

            table.wait_until_exists()
            logger.info(f"✅ Table {table_name} created successfully")
            return True

        except Exception as e:
            logger.error(f"❌ Failed to create {table_name}: {e}")
            return False

    def create_league_parameters_table(self) -> bool:
        """
        Create the league_parameters table for league-level statistics.

        Returns:
            True if successful, False otherwise
        """
        table_name = _get_table_name('league_parameters')

        if self.dry_run:
            logger.info(f"[DRY RUN] Would create table: {table_name}")
            return True

        try:
            # Check if table exists
            try:
                self.dynamodb.Table(table_name).load()
                logger.info(f"Table {table_name} already exists")
                return True
            except ClientError as e:
                if e.response['Error']['Code'] != 'ResourceNotFoundException':
                    raise

            # Create table
            logger.info(f"Creating table: {table_name}")

            table = self.dynamodb.create_table(
                TableName=table_name,
                KeySchema=[
                    {'AttributeName': 'league_id', 'KeyType': 'HASH'},
                    {'AttributeName': 'season', 'KeyType': 'RANGE'}
                ],
                AttributeDefinitions=[
                    {'AttributeName': 'league_id', 'AttributeType': 'N'},
                    {'AttributeName': 'season', 'AttributeType': 'N'}
                ],
                BillingMode='PAY_PER_REQUEST',
                Tags=[
                    {'Key': 'Project', 'Value': 'football-fixture-predictions'},
                    {'Key': 'Environment', 'Value': ENVIRONMENT},
                    {'Key': 'Purpose', 'Value': 'league-statistics'}
                ]
            )

            table.wait_until_exists()
            logger.info(f"✅ Table {table_name} created successfully")
            return True

        except Exception as e:
            logger.error(f"❌ Failed to create {table_name}: {e}")
            return False

    def create_team_parameters_table(self) -> bool:
        """
        Create the team_parameters table for team-level statistics.

        Returns:
            True if successful, False otherwise
        """
        table_name = _get_table_name('team_parameters')

        if self.dry_run:
            logger.info(f"[DRY RUN] Would create table: {table_name}")
            return True

        try:
            # Check if table exists
            try:
                self.dynamodb.Table(table_name).load()
                logger.info(f"Table {table_name} already exists")
                return True
            except ClientError as e:
                if e.response['Error']['Code'] != 'ResourceNotFoundException':
                    raise

            # Create table
            logger.info(f"Creating table: {table_name}")

            table = self.dynamodb.create_table(
                TableName=table_name,
                KeySchema=[
                    {'AttributeName': 'team_id', 'KeyType': 'HASH'}
                ],
                AttributeDefinitions=[
                    {'AttributeName': 'team_id', 'AttributeType': 'N'}
                ],
                BillingMode='PAY_PER_REQUEST',
                Tags=[
                    {'Key': 'Project', 'Value': 'football-fixture-predictions'},
                    {'Key': 'Environment', 'Value': ENVIRONMENT},
                    {'Key': 'Purpose', 'Value': 'team-statistics'}
                ]
            )

            table.wait_until_exists()
            logger.info(f"✅ Table {table_name} created successfully")
            return True

        except Exception as e:
            logger.error(f"❌ Failed to create {table_name}: {e}")
            return False

    def create_venue_cache_table(self) -> bool:
        """
        Create the venue_cache table for venue/stadium data.

        Returns:
            True if successful, False otherwise
        """
        table_name = _get_table_name('venue_cache')

        if self.dry_run:
            logger.info(f"[DRY RUN] Would create table: {table_name}")
            return True

        try:
            # Check if table exists
            try:
                self.dynamodb.Table(table_name).load()
                logger.info(f"Table {table_name} already exists")
                return True
            except ClientError as e:
                if e.response['Error']['Code'] != 'ResourceNotFoundException':
                    raise

            # Create table
            logger.info(f"Creating table: {table_name}")

            table = self.dynamodb.create_table(
                TableName=table_name,
                KeySchema=[
                    {'AttributeName': 'venue_id', 'KeyType': 'HASH'}
                ],
                AttributeDefinitions=[
                    {'AttributeName': 'venue_id', 'AttributeType': 'N'},
                    {'AttributeName': 'latitude', 'AttributeType': 'N'},
                    {'AttributeName': 'longitude', 'AttributeType': 'N'}
                ],
                GlobalSecondaryIndexes=[
                    {
                        'IndexName': 'coordinates-index',
                        'KeySchema': [
                            {'AttributeName': 'latitude', 'KeyType': 'HASH'},
                            {'AttributeName': 'longitude', 'KeyType': 'RANGE'}
                        ],
                        'Projection': {'ProjectionType': 'ALL'}
                    }
                ],
                BillingMode='PAY_PER_REQUEST',
                Tags=[
                    {'Key': 'Project', 'Value': 'football-fixture-predictions'},
                    {'Key': 'Environment', 'Value': ENVIRONMENT},
                    {'Key': 'Purpose', 'Value': 'venue-cache'},
                    {'Key': 'TTL', 'Value': '7days'}
                ]
            )

            table.wait_until_exists()

            # Enable TTL
            self.client.update_time_to_live(
                TableName=table_name,
                TimeToLiveSpecification={
                    'AttributeName': 'ttl',
                    'Enabled': True
                }
            )

            logger.info(f"✅ Table {table_name} created successfully with TTL enabled")
            return True

        except Exception as e:
            logger.error(f"❌ Failed to create {table_name}: {e}")
            return False

    def create_tactical_cache_table(self) -> bool:
        """
        Create the tactical_analysis_cache table for tactical data.

        Returns:
            True if successful, False otherwise
        """
        table_name = _get_table_name('tactical_cache')

        if self.dry_run:
            logger.info(f"[DRY RUN] Would create table: {table_name}")
            return True

        try:
            # Check if table exists
            try:
                self.dynamodb.Table(table_name).load()
                logger.info(f"Table {table_name} already exists")
                return True
            except ClientError as e:
                if e.response['Error']['Code'] != 'ResourceNotFoundException':
                    raise

            # Create table
            logger.info(f"Creating table: {table_name}")

            table = self.dynamodb.create_table(
                TableName=table_name,
                KeySchema=[
                    {'AttributeName': 'cache_key', 'KeyType': 'HASH'}
                ],
                AttributeDefinitions=[
                    {'AttributeName': 'cache_key', 'AttributeType': 'S'}
                ],
                BillingMode='PAY_PER_REQUEST',
                Tags=[
                    {'Key': 'Project', 'Value': 'football-fixture-predictions'},
                    {'Key': 'Environment', 'Value': ENVIRONMENT},
                    {'Key': 'Purpose', 'Value': 'tactical-cache'},
                    {'Key': 'TTL', 'Value': '48hours'}
                ]
            )

            table.wait_until_exists()

            # Enable TTL
            self.client.update_time_to_live(
                TableName=table_name,
                TimeToLiveSpecification={
                    'AttributeName': 'ttl',
                    'Enabled': True
                }
            )

            logger.info(f"✅ Table {table_name} created successfully with TTL enabled")
            return True

        except Exception as e:
            logger.error(f"❌ Failed to create {table_name}: {e}")
            return False

    def create_league_standings_cache_table(self) -> bool:
        """
        Create the league_standings_cache table for standings data.

        Returns:
            True if successful, False otherwise
        """
        table_name = _get_table_name('league_standings_cache')

        if self.dry_run:
            logger.info(f"[DRY RUN] Would create table: {table_name}")
            return True

        try:
            # Check if table exists
            try:
                self.dynamodb.Table(table_name).load()
                logger.info(f"Table {table_name} already exists")
                return True
            except ClientError as e:
                if e.response['Error']['Code'] != 'ResourceNotFoundException':
                    raise

            # Create table
            logger.info(f"Creating table: {table_name}")

            table = self.dynamodb.create_table(
                TableName=table_name,
                KeySchema=[
                    {'AttributeName': 'cache_key', 'KeyType': 'HASH'}
                ],
                AttributeDefinitions=[
                    {'AttributeName': 'cache_key', 'AttributeType': 'S'}
                ],
                BillingMode='PAY_PER_REQUEST',
                Tags=[
                    {'Key': 'Project', 'Value': 'football-fixture-predictions'},
                    {'Key': 'Environment', 'Value': ENVIRONMENT},
                    {'Key': 'Purpose', 'Value': 'standings-cache'},
                    {'Key': 'TTL', 'Value': '24hours'}
                ]
            )

            table.wait_until_exists()

            # Enable TTL
            self.client.update_time_to_live(
                TableName=table_name,
                TimeToLiveSpecification={
                    'AttributeName': 'ttl',
                    'Enabled': True
                }
            )

            logger.info(f"✅ Table {table_name} created successfully with TTL enabled")
            return True

        except Exception as e:
            logger.error(f"❌ Failed to create {table_name}: {e}")
            return False

    def deploy_all_tables(self) -> Dict[str, bool]:
        """
        Deploy all required DynamoDB tables.

        Returns:
            Dictionary mapping table names to deployment status
        """
        logger.info("\n" + "=" * 70)
        logger.info("STARTING TABLE DEPLOYMENT")
        logger.info("=" * 70 + "\n")

        # Print configuration
        self.print_configuration()

        if not self.dry_run:
            logger.info("\nDeploying tables...")

        # Deploy all tables
        tables = [
            ('game_fixtures', self.create_game_fixtures_table),
            ('league_parameters', self.create_league_parameters_table),
            ('team_parameters', self.create_team_parameters_table),
            ('venue_cache', self.create_venue_cache_table),
            ('tactical_cache', self.create_tactical_cache_table),
            ('league_standings_cache', self.create_league_standings_cache_table)
        ]

        results = {}
        for table_name, create_func in tables:
            logger.info(f"\n{'=' * 70}")
            results[table_name] = create_func()

        # Print summary
        logger.info("\n" + "=" * 70)
        logger.info("DEPLOYMENT SUMMARY")
        logger.info("=" * 70)

        success_count = sum(1 for v in results.values() if v)
        total_count = len(results)

        for table_name, success in results.items():
            status = "✅ SUCCESS" if success else "❌ FAILED"
            full_name = _get_table_name(table_name)
            logger.info(f"{status:15s} {table_name:30s} -> {full_name}")

        logger.info("=" * 70)
        logger.info(f"Deployment Results: {success_count}/{total_count} tables deployed successfully")
        logger.info("=" * 70 + "\n")

        return results

    def verify_deployment(self) -> bool:
        """
        Verify all tables are deployed and accessible.

        Returns:
            True if all tables are accessible, False otherwise
        """
        if self.dry_run:
            logger.info("[DRY RUN] Would verify table deployment")
            return True

        logger.info("\n" + "=" * 70)
        logger.info("VERIFYING DEPLOYMENT")
        logger.info("=" * 70 + "\n")

        config = get_table_config()
        all_accessible = True

        for base_name, full_name in config['tables'].items():
            try:
                table = self.dynamodb.Table(full_name)
                table.load()
                status = table.table_status

                if status == 'ACTIVE':
                    logger.info(f"✅ {base_name:30s} Status: {status}")
                else:
                    logger.warning(f"⚠️  {base_name:30s} Status: {status} (not active)")
                    all_accessible = False

            except ClientError as e:
                logger.error(f"❌ {base_name:30s} Error: {e}")
                all_accessible = False

        logger.info("=" * 70)

        if all_accessible:
            logger.info("✅ All tables are deployed and accessible")
        else:
            logger.error("❌ Some tables are not accessible")

        logger.info("=" * 70 + "\n")

        return all_accessible


def interactive_setup():
    """
    Interactive setup that prompts user for environment configuration.
    """
    print("\n" + "=" * 70)
    print("FOOTBALL FIXTURE PREDICTION SYSTEM - TABLE DEPLOYMENT")
    print("=" * 70 + "\n")

    print("Current environment variables:")
    print(f"  TABLE_PREFIX:  '{os.getenv('TABLE_PREFIX', '')}' (empty = no prefix)")
    print(f"  TABLE_SUFFIX:  '{os.getenv('TABLE_SUFFIX', '')}' (empty = no suffix)")
    print(f"  ENVIRONMENT:   '{os.getenv('ENVIRONMENT', 'dev')}'")
    print()

    response = input("Do you want to change these settings? (y/N): ").strip().lower()

    if response == 'y':
        print("\nEnter new values (press Enter to keep current value):")

        prefix = input(f"  TABLE_PREFIX [{os.getenv('TABLE_PREFIX', '')}]: ").strip()
        if prefix:
            os.environ['TABLE_PREFIX'] = prefix

        suffix = input(f"  TABLE_SUFFIX [{os.getenv('TABLE_SUFFIX', '')}]: ").strip()
        if suffix:
            os.environ['TABLE_SUFFIX'] = suffix

        env = input(f"  ENVIRONMENT [{os.getenv('ENVIRONMENT', 'dev')}]: ").strip()
        if env:
            os.environ['ENVIRONMENT'] = env

        print("\nUpdated configuration:")
        print(f"  TABLE_PREFIX:  '{os.getenv('TABLE_PREFIX', '')}'")
        print(f"  TABLE_SUFFIX:  '{os.getenv('TABLE_SUFFIX', '')}'")
        print(f"  ENVIRONMENT:   '{os.getenv('ENVIRONMENT', 'dev')}'")

    print("\n" + "=" * 70)
    response = input("Proceed with deployment? (y/N): ").strip().lower()

    return response == 'y'


def main():
    """
    Main deployment function.
    """
    parser = argparse.ArgumentParser(
        description='Deploy DynamoDB tables for Football Fixture Prediction System'
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Print configuration without deploying tables'
    )
    parser.add_argument(
        '--no-interactive',
        action='store_true',
        help='Skip interactive prompts (use environment variables only)'
    )
    parser.add_argument(
        '--verify-only',
        action='store_true',
        help='Only verify existing tables, do not deploy'
    )

    args = parser.parse_args()

    # Interactive setup if not disabled
    if not args.no_interactive and not args.dry_run and not args.verify_only:
        if not interactive_setup():
            logger.info("Deployment cancelled by user")
            return 0

    # Create deployer
    deployer = TableDeployer(dry_run=args.dry_run)

    # Verify only mode
    if args.verify_only:
        success = deployer.verify_deployment()
        return 0 if success else 1

    # Deploy tables
    results = deployer.deploy_all_tables()

    # Verify deployment if not dry run
    if not args.dry_run:
        verification_success = deployer.verify_deployment()

        if verification_success and all(results.values()):
            logger.info("🎉 Deployment completed successfully!")
            logger.info("\nNext steps:")
            logger.info("  1. Update your application configuration with the new table names")
            logger.info("  2. Test the deployment with sample data")
            logger.info("  3. Monitor CloudWatch for any issues")
            return 0
        else:
            logger.error("⚠️  Deployment completed with errors")
            return 1
    else:
        logger.info("\n[DRY RUN] No tables were actually created")
        logger.info("Remove --dry-run flag to perform actual deployment")
        return 0


if __name__ == '__main__':
    sys.exit(main())
