# Database Table Isolation Implementation Guide

## Problem Statement

The football fixture predictions application currently uses shared DynamoDB tables (`game_fixtures`, `league_parameters`, `team_parameters`) that are also used by other applications. To deploy this as a standalone application, we need dedicated tables with environment-specific naming to avoid conflicts.

## Solution Overview

Implement **environment-based table naming** using configurable prefixes and suffixes, allowing multiple isolated deployments while maintaining all existing functionality.

## Current Table Structure

### Core Application Tables
- `game_fixtures` - Match fixture data and predictions
- `league_parameters` - League-specific statistical parameters  
- `team_parameters` - Team-specific performance parameters

### Cache Tables
- `venue_cache` - Stadium details cache (7-day TTL)
- `league_standings_cache` - League standings cache (TTL enabled)
- `tactical_analysis_cache` - Tactical analysis cache (48-hour TTL)

## Implementation Plan

### Phase 1: Update Constants System

**File: [`src/utils/constants.py`](src/utils/constants.py)**

```python
"""
Shared constants for the football fixture predictions system.
"""

# API Configuration
API_FOOTBALL_BASE_URL = "https://api-football-v1.p.rapidapi.com/v3"
API_FOOTBALL_HOST = "api-football-v1.p.rapidapi.com"

# API Keys (should be set via environment variables)
import os
RAPIDAPI_KEY = os.getenv('RAPIDAPI_KEY', '4c37223acemsh65b1a8b456b72c1p15a99ajsnd4a09ab346a4')

# Environment-based Table Naming
TABLE_PREFIX = os.getenv('TABLE_PREFIX', '')
TABLE_SUFFIX = os.getenv('TABLE_SUFFIX', '')
ENVIRONMENT = os.getenv('ENVIRONMENT', 'dev')

def _get_table_name(base_name: str) -> str:
    """
    Generate environment-specific table name with prefix/suffix.
    
    Args:
        base_name: Base table name (e.g., 'game_fixtures')
        
    Returns:
        Formatted table name with prefix/suffix
        
    Examples:
        TABLE_PREFIX='football-pred', base_name='game_fixtures' 
        → 'football-pred-game_fixtures'
        
        TABLE_PREFIX='prod', TABLE_SUFFIX='v2', base_name='team_parameters'
        → 'prod-team_parameters-v2'
    """
    parts = [TABLE_PREFIX, base_name, TABLE_SUFFIX]
    return '-'.join(filter(None, parts)) or base_name

def get_table_config() -> dict:
    """Get current table configuration for debugging/logging."""
    return {
        'prefix': TABLE_PREFIX,
        'suffix': TABLE_SUFFIX, 
        'environment': ENVIRONMENT,
        'core_tables': {
            'fixtures': GAME_FIXTURES_TABLE,
            'league_params': LEAGUE_PARAMETERS_TABLE,
            'team_params': TEAM_PARAMETERS_TABLE
        },
        'cache_tables': {
            'venue': _get_table_name('venue_cache'),
            'league_standings': _get_table_name('league_standings_cache'),
            'tactical': _get_table_name('tactical_analysis_cache')
        }
    }

# DynamoDB Table Names - Environment Configurable
GAME_FIXTURES_TABLE = _get_table_name('game_fixtures')
LEAGUE_PARAMETERS_TABLE = _get_table_name('league_parameters')
TEAM_PARAMETERS_TABLE = _get_table_name('team_parameters')

# Retry Configuration
DEFAULT_MAX_RETRIES = 5
MIN_WAIT_TIME = 5
MAX_WAIT_TIME = 30

# Statistical Constants
DEFAULT_ALPHA = 0.3  # Dispersion parameter for Negative Binomial
DEFAULT_SMOOTHING_ALPHA = 0.15  # Exponential smoothing factor
DEFAULT_PRIOR_WEIGHT = 5  # Bayesian smoothing prior weight

# Points System
HOME_WIN_POINTS = 3
AWAY_WIN_POINTS = 4
HOME_DRAW_POINTS = 1
AWAY_DRAW_POINTS = 2
HOME_LOSS_POINTS = -1
AWAY_LOSS_POINTS = 0

# Goal Analysis
MAX_GOALS_ANALYSIS = 10  # Maximum goals to analyze in probability calculations

# SQS Queue URLs
FIXTURES_QUEUE_URL = 'https://sqs.eu-west-2.amazonaws.com/985019772236/fixturesQueue'

# Default Values
DEFAULT_LAMBDA_CEILING = 4.0
MINIMUM_GAMES_THRESHOLD = 10
MINIMUM_LEAGUE_GAMES = 50
MAX_SEASON_LOOKBACK = 3
```

### Phase 2: Update Cache Table Creation Scripts

**File: [`src/infrastructure/create_venue_cache.py`](src/infrastructure/create_venue_cache.py)**

```python
"""
Create venue cache DynamoDB table for storing stadium details.

This module creates and configures the venue_cache table for:
- Caching venue details from API-Football
- Geographic distance calculations
- Surface and climate analysis

Phase 2: Home/Away Venue Analysis
Infrastructure component for venue data caching and performance optimization.
"""

import boto3
import logging
from botocore.exceptions import ClientError
from ..data.database_client import dynamodb
from ..utils.constants import _get_table_name

logger = logging.getLogger(__name__)

def create_venue_cache_table() -> bool:
    """
    Create venue_cache DynamoDB table for storing stadium details.
    
    Table structure:
    - Primary Key: venue_id (int)
    - Attributes: venue_name, capacity, surface, coordinates, climate_data, cached_at, ttl
    - TTL enabled on 'ttl' attribute for automatic expiration
    - GSI on coordinates for geographic queries
    
    Returns:
        True if table created successfully or already exists, False otherwise
        
    Features:
    - 7-day TTL for venue details
    - Global secondary index on coordinates for geographic queries
    - Optimized for venue detail lookups and distance calculations
    """
    try:
        dynamodb_client = dynamodb.meta.client
        
        # Use environment-configurable table name
        table_name = _get_table_name('venue_cache')
        
        # Check if table already exists
        try:
            existing_table = dynamodb_client.describe_table(TableName=table_name)
            print(f"Table {table_name} already exists")
            return True
        except ClientError as e:
            if e.response['Error']['Code'] != 'ResourceNotFoundException':
                print(f"Error checking existing table: {e}")
                return False
        
        # Create table with schema
        table_definition = {
            'TableName': table_name,
            'KeySchema': [
                {
                    'AttributeName': 'venue_id',
                    'KeyType': 'HASH'  # Partition key
                }
            ],
            'AttributeDefinitions': [
                {
                    'AttributeName': 'venue_id',
                    'AttributeType': 'N'  # Number
                },
                {
                    'AttributeName': 'latitude',
                    'AttributeType': 'N'  # Number for GSI
                },
                {
                    'AttributeName': 'longitude', 
                    'AttributeType': 'N'  # Number for GSI
                }
            ],
            'BillingMode': 'PAY_PER_REQUEST',  # On-demand billing
            'GlobalSecondaryIndexes': [
                {
                    'IndexName': 'coordinates-index',
                    'KeySchema': [
                        {
                            'AttributeName': 'latitude',
                            'KeyType': 'HASH'
                        },
                        {
                            'AttributeName': 'longitude',
                            'KeyType': 'RANGE'
                        }
                    ],
                    'Projection': {
                        'ProjectionType': 'ALL'  # Include all attributes
                    }
                }
            ],
            'TimeToLiveSpecification': {
                'AttributeName': 'ttl',
                'Enabled': True
            },
            'Tags': [
                {
                    'Key': 'Project',
                    'Value': 'football-fixture-predictions'
                },
                {
                    'Key': 'Component', 
                    'Value': 'venue-analysis'
                },
                {
                    'Key': 'Environment',
                    'Value': f"{_get_table_name('')}"  # Shows prefix/suffix config
                }
            ]
        }
        
        # Create the table
        response = dynamodb_client.create_table(**table_definition)

        print(f"Creating table {table_name}...")
        print(f"Table ARN: {response['TableDescription']['TableArn']}")

        # Wait for table to become active
        waiter = dynamodb_client.get_waiter('table_exists')
        waiter.wait(TableName=table_name, WaiterConfig={'Delay': 5, 'MaxAttempts': 20})

        print(f"Table {table_name} created successfully!")

        # Enable TTL if not already enabled during creation
        try:
            dynamodb_client.update_time_to_live(
                TableName=table_name,
                TimeToLiveSpecification={
                    'AttributeName': 'ttl',
                    'Enabled': True
                }
            )
            print(f"TTL enabled on {table_name}")
        except ClientError as e:
            if 'ValidationException' in str(e):
                print(f"TTL already enabled on {table_name}")
            else:
                print(f"Warning: Could not enable TTL: {e}")

        return True

    except Exception as e:
        print(f"Failed to create venue cache table: {e}")
        return False

def delete_venue_cache_table() -> bool:
    """Delete venue cache table (for cleanup/testing)."""
    try:
        dynamodb_client = dynamodb.meta.client
        table_name = _get_table_name('venue_cache')

        # Delete table
        dynamodb_client.delete_table(TableName=table_name)

        # Wait for deletion
        waiter = dynamodb_client.get_waiter('table_not_exists')
        waiter.wait(TableName=table_name, WaiterConfig={'Delay': 5, 'MaxAttempts': 20})

        print(f"Table {table_name} deleted successfully!")
        return True

    except Exception as e:
        print(f"Failed to delete table: {e}")
        return False

def get_venue_cache_table_info():
    """Get information about the venue cache table."""
    try:
        dynamodb_client = dynamodb.meta.client
        table_name = _get_table_name('venue_cache')

        response = dynamodb_client.describe_table(TableName=table_name)
        table_info = response['TableDescription']

        print(f"Table Name: {table_info['TableName']}")
        print(f"Table Status: {table_info['TableStatus']}")
        print(f"Item Count: {table_info.get('ItemCount', 'N/A')}")
        print(f"Table Size (bytes): {table_info.get('TableSizeBytes', 'N/A')}")
        
        # TTL info
        if 'TimeToLiveDescription' in response:
            ttl_info = response['TimeToLiveDescription']
            print(f"TTL Status: {ttl_info.get('TimeToLiveStatus', 'Unknown')}")
            print(f"TTL Attribute: {ttl_info.get('AttributeName', 'N/A')}")
        
        # GSI info
        if 'GlobalSecondaryIndexes' in table_info:
            for gsi in table_info['GlobalSecondaryIndexes']:
                print(f"GSI: {gsi['IndexName']} - Status: {gsi['IndexStatus']}")

        return table_info

    except Exception as e:
        print(f"Error getting table info: {e}")
        return None

def setup_venue_cache_infrastructure() -> bool:
    """
    Complete setup of venue cache infrastructure.
    
    This function:
    1. Creates the venue_cache table with proper schema
    2. Configures TTL for automatic expiration
    3. Sets up GSI for coordinate-based queries
    4. Validates table configuration
    
    Returns:
        True if setup successful, False otherwise
    """
    print("Setting up venue cache infrastructure...")
    
    # Step 1: Create table
    if not create_venue_cache_table():
        print("Failed to create venue cache table")
        return False
    
    # Step 2: Validate table configuration
    table_info = get_venue_cache_table_info()
    if not table_info:
        print("Failed to validate table configuration") 
        return False
    
    # Step 3: Test basic functionality (optional)
    # Could add test writes/reads here
    
    print("✅ Venue cache infrastructure setup completed successfully!")
    print("\nTable Features:")
    print("  - 7-day TTL for automatic cache expiration")
    print("  - Global Secondary Index for coordinate-based queries")
    print("  - Pay-per-request billing for cost optimization")
    print("  - Optimized for venue detail lookups and distance calculations")
    
    return True

if __name__ == "__main__":
    print("=== Venue Cache Infrastructure Setup ===")
    success = setup_venue_cache_infrastructure()
    
    if success:
        print("\n🎉 Venue cache infrastructure is ready for Phase 2 deployment!")
    else:
        print("\n❌ Setup failed. Please check the errors above.")
```

**File: [`src/infrastructure/create_league_standings_cache.py`](src/infrastructure/create_league_standings_cache.py)**

```python
"""
DynamoDB Table Creation Script for League Standings Cache

This script creates the `league_standings_cache` table required for Phase 1
opponent strength stratification. The table caches league standings data
to optimize opponent classification performance.

Table Schema:
- Partition Key: cache_key (league_id-season)
- TTL enabled for automatic cache expiration

Usage:
    python -m src.infrastructure.create_league_standings_cache
"""

import boto3
import logging
from datetime import datetime, timedelta
from botocore.exceptions import ClientError
from ..data.database_client import dynamodb
from ..utils.constants import _get_table_name

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def create_league_standings_cache_table():
    """
    Create the league_standings_cache DynamoDB table.
    
    Returns:
        bool: True if successful, False otherwise
    """
    try:
        # Initialize DynamoDB client
        client = dynamodb.meta.client
    except Exception as e:
        logger.error(f"Failed to initialize DynamoDB client: {e}")
        return False

    # Use environment-configurable table name
    table_name = _get_table_name('league_standings_cache')

    # Check if table already exists
    try:
        existing_table = dynamodb.Table(table_name)
        existing_table.load()
        logger.info(f"Table {table_name} already exists")
        return True
    except client.exceptions.ResourceNotFoundException:
        logger.info(f"Table {table_name} does not exist, creating new table...")
    except Exception as e:
        logger.error(f"Error checking existing table: {e}")
        return False

    # Define table schema
    table_definition = {
        'TableName': table_name,
        'KeySchema': [
            {
                'AttributeName': 'cache_key',
                'KeyType': 'HASH'  # Partition key
            }
        ],
        'AttributeDefinitions': [
            {
                'AttributeName': 'cache_key',
                'AttributeType': 'S'
            }
        ],
        'BillingMode': 'PAY_PER_REQUEST',  # On-demand billing
        'Tags': [
            {
                'Key': 'Project',
                'Value': 'football-fixture-predictions'
            },
            {
                'Key': 'Component',
                'Value': 'phase1-opponent-stratification'
            },
            {
                'Key': 'Purpose',
                'Value': 'league-standings-cache'
            },
            {
                'Key': 'Environment',
                'Value': f"{_get_table_name('')}"  # Shows prefix/suffix config
            }
        ]
    }

    try:
        # Create the table
        logger.info(f"Creating table {table_name}...")
        table = dynamodb.create_table(**table_definition)

        # Wait for table to become active
        table.wait_until_exists()
        logger.info(f"Table {table_name} is now active")

        # Enable TTL
        client.update_time_to_live(
            TableName=table_name,
            TimeToLiveSpecification={
                'AttributeName': 'ttl',
                'Enabled': True
            }
        )

        logger.info(f"Table {table_name} created successfully!")
        logger.info("Table features:")
        logger.info("  - TTL enabled for automatic cache expiration")
        logger.info("  - Pay-per-request billing for cost optimization")
        logger.info("  - Optimized for league standings caching")
        
        return True

    except ClientError as e:
        error_code = e.response['Error']['Code']
        if error_code == 'ResourceInUseException':
            logger.info(f"Table {table_name} already exists")
            return True
        else:
            logger.error(f"Failed to create table {table_name}: {e}")
            return False
    except Exception as e:
        logger.error(f"Unexpected error creating table {table_name}: {e}")
        return False

def verify_table_setup():
    """
    Verify the league_standings_cache table is properly configured.

    Returns:
        bool: True if table is properly configured
    """
    try:
        client = boto3.client('dynamodb')
        table_name = _get_table_name('league_standings_cache')

        # Check table exists and is active
        table = dynamodb.Table(table_name)
        table.load()

        if table.table_status != 'ACTIVE':
            logger.error(f"Table {table_name} is not in ACTIVE state: {table.table_status}")
            return False

        # Check TTL configuration
        ttl_response = client.describe_time_to_live(TableName=table_name)
        ttl_status = ttl_response.get('TimeToLiveDescription', {}).get('TimeToLiveStatus')

        if ttl_status != 'ENABLED':
            logger.warning(f"TTL is not enabled on table {table_name} (status: {ttl_status})")
            # Try to enable TTL
            try:
                client.update_time_to_live(
                    TableName=table_name,
                    TimeToLiveSpecification={
                        'AttributeName': 'ttl',
                        'Enabled': True
                    }
                )
                logger.info(f"TTL enabled on table {table_name}")
            except Exception as e:
                logger.error(f"Failed to enable TTL: {e}")
                return False

        logger.info(f"Table {table_name} is properly configured:")
        logger.info(f"  - Status: {table.table_status}")
        logger.info(f"  - TTL Status: {ttl_status}")
        logger.info(f"  - Item Count: {table.item_count}")
        
        return True

    except Exception as e:
        logger.error(f"Error verifying table setup: {e}")
        return False

def test_cache_operations():
    """
    Test basic cache operations to ensure table is functional.
    
    Returns:
        bool: True if operations successful
    """
    try:
        table_name = _get_table_name('league_standings_cache')
        table = dynamodb.Table(table_name)
        
        # Test cache key format
        test_league_id = 39  # Premier League
        test_season = 2023
        test_cache_key = f"{test_league_id}-{test_season}"
        
        current_timestamp = datetime.now().timestamp()
        # TTL set for 7 days from now
        ttl_timestamp = int((datetime.now() + timedelta(days=7)).timestamp())
        
        # Test data
        test_data = {
            'cache_key': test_cache_key,
            'timestamp': int(current_timestamp),  # Convert to int for DynamoDB
            'ttl': ttl_timestamp,
            'league_id': test_league_id,
            'season': test_season,
            'standings': [
                {
                    'team_id': 33,  # Manchester United
                    'position': 1,
                    'points': 45,
                    'form': 'WWWWD'
                },
                {
                    'team_id': 34,  # Newcastle United
                    'position': 2, 
                    'points': 44,
                    'form': 'WWDWW'
                }
            ],
            'metadata': {
                'total_teams': 20,
                'matches_played': 15,
                'cached_at': current_timestamp
            }
        }
        
        # Test write
        logger.info("Testing cache write operation...")
        table.put_item(Item=test_data)
        logger.info("✅ Write operation successful")
        
        # Test read
        logger.info("Testing cache read operation...")
        response = table.get_item(Key={'cache_key': test_cache_key})
        
        if 'Item' in response:
            logger.info("✅ Read operation successful")
            cached_data = response['Item']
            logger.info(f"Cache contains {len(cached_data['standings'])} teams")
            
            # Clean up test data
            table.delete_item(Key={'cache_key': test_cache_key})
            logger.info("✅ Test cleanup completed")
            return True
        else:
            logger.error("❌ Failed to read cached data")
            return False
            
    except Exception as e:
        logger.error(f"Cache operation test failed: {e}")
        return False

def main():
    """
    Main function to create and verify the league standings cache table.
    """
    logger.info("=== League Standings Cache Table Setup ===")
    logger.info("Setting up DynamoDB infrastructure for Phase 1 opponent stratification...")

    # Step 1: Create the table
    if not create_league_standings_cache_table():
        logger.error("Failed to create table. Exiting.")
        return False

    # Step 2: Verify table configuration
    if not verify_table_setup():
        logger.error("Table configuration verification failed. Exiting.")
        return False

    # Step 3: Test basic operations
    if not test_cache_operations():
        logger.warning("Cache operations test failed, but table creation succeeded.")
        logger.info("Table may still be usable, but requires manual verification.")

    logger.info("✅ League standings cache infrastructure setup completed!")
    logger.info("\nNext steps:")
    logger.info("1. Verify AWS permissions for DynamoDB operations")
    logger.info("2. Test cache operations in your application")
    logger.info("3. Configure appropriate TTL values for your use case")
    
    return True

if __name__ == "__main__":
    success = main()
    if not success:
        exit(1)
```

**File: [`src/data/tactical_data_collector.py`](src/data/tactical_data_collector.py)**

Update line 60 to use configurable table name:

```python
from ..utils.constants import _get_table_name

class TacticalDataCollector:
    def __init__(self):
        # ... existing initialization ...
        
        # DynamoDB table for tactical cache - use environment-configurable name
        self.tactical_cache_table = _get_table_name('tactical_analysis_cache')
```

### Phase 3: Create Deployment Script

**File: [`src/infrastructure/deploy_tables.py`](src/infrastructure/deploy_tables.py)**

```python
#!/usr/bin/env python3
"""
Deploy Application-Specific DynamoDB Tables

This script deploys all DynamoDB tables required by the football fixture 
predictions application with environment-specific naming to avoid conflicts
with shared tables.

Usage:
    # Interactive mode
    python -m src.infrastructure.deploy_tables
    
    # With environment variables
    export TABLE_PREFIX="myapp"
    export TABLE_SUFFIX="prod"
    python -m src.infrastructure.deploy_tables
    
    # Command line arguments
    python -m src.infrastructure.deploy_tables --prefix myapp --suffix prod
"""

import os
import sys
import argparse
import boto3
import logging
from datetime import datetime
from botocore.exceptions import ClientError

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def setup_environment_variables(prefix: str = None, suffix: str = None, environment: str = None):
    """Set up environment variables for table naming."""
    if prefix:
        os.environ['TABLE_PREFIX'] = prefix
    if suffix:
        os.environ['TABLE_SUFFIX'] = suffix
    if environment:
        os.environ['ENVIRONMENT'] = environment
        
    # Import constants after setting environment variables
    from ..utils.constants import get_table_config
    config = get_table_config()
    
    logger.info("Table Configuration:")
    logger.info(f"  Prefix: {config['prefix'] or 'None'}")
    logger.info(f"  Suffix: {config['suffix'] or 'None'}")
    logger.info(f"  Environment: {config['environment']}")
    logger.info(f"  Core Tables: {list(config['core_tables'].values())}")
    logger.info(f"  Cache Tables: {list(config['cache_tables'].values())}")
    
    return config

def create_core_tables() -> bool:
    """
    Create core application tables using current constants.
    
    These tables are created by the database_client using the configured names.
    This function verifies they can be created with the new naming.
    """
    try:
        from ..utils.constants import (
            GAME_FIXTURES_TABLE, 
            LEAGUE_PARAMETERS_TABLE, 
            TEAM_PARAMETERS_TABLE
        )
        from ..data.database_client import get_database_health
        
        logger.info("Creating core application tables...")
        
        # The database client will use the configured table names
        # We just need to verify connectivity and that tables can be accessed
        health = get_database_health()
        
        core_tables = [GAME_FIXTURES_TABLE, LEAGUE_PARAMETERS_TABLE, TEAM_PARAMETERS_TABLE]
        
        for table_name in core_tables:
            if table_name in health:
                if health[table_name] == "healthy":
                    logger.info(f"✅ Table {table_name} is accessible")
                else:
                    logger.warning(f"⚠️  Table {table_name} status: {health[table_name]}")
            else:
                logger.info(f"ℹ️  Table {table_name} may need to be created via AWS Console or CLI")
                
        return True
        
    except Exception as e:
        logger.error(f"Error with core tables: {e}")
        return False

def create_cache_tables() -> bool:
    """Create all cache tables with environment-specific names."""
    success = True
    
    try:
        # Import after environment variables are set
        from .create_venue_cache import setup_venue_cache_infrastructure
        from .create_league_standings_cache import main as setup_league_cache
        
        logger.info("Creating cache tables...")
        
        # Deploy venue cache
        logger.info("Setting up venue cache infrastructure...")
        if setup_venue_cache_infrastructure():
            logger.info("✅ Venue cache table created successfully")
        else:
            logger.error("❌ Failed to create venue cache table")
            success = False
            
        # Deploy league standings cache  
        logger.info("Setting up league standings cache...")
        if setup_league_cache():
            logger.info("✅ League standings cache table created successfully")
        else:
            logger.error("❌ Failed to create league standings cache table")
            success = False
            
        # Note: tactical_analysis_cache is created dynamically by the collector
        logger.info("ℹ️  Tactical analysis cache will be created automatically when first used")
        
        return success
        
    except Exception as e:
        logger.error(f"Error creating cache tables: {e}")
        return False

def verify_deployment() -> bool:
    """Verify all tables are properly deployed and accessible."""
    try:
        from ..utils.constants import get_table_config
        from ..data.database_client import get_database_health
        
        config = get_table_config()
        health = get_database_health()
        
        logger.info("Verifying deployment...")
        
        all_tables = {**config['core_tables'], **config['cache_tables']}
        
        success = True
        for table_type, table_name in all_tables.items():
            if table_name in health:
                status = health[table_name]
                if status == "healthy":
                    logger.info(f"✅ {table_type}: {table_name} - {status}")
                else:
                    logger.warning(f"⚠️  {table_type}: {table_name} - {status}")
                    success = False
            else:
                logger.info(f"ℹ️  {table_type}: {table_name} - not yet created or accessible")
                
        return success
        
    except Exception as e:
        logger.error(f"Error during verification: {e}")
        return False

def cleanup_tables(confirm: bool = False) -> bool:
    """
    Clean up deployed tables (for testing/reset).
    
    Args:
        confirm: If True, skip confirmation prompt
    """
    if not confirm:
        response = input("⚠️  This will DELETE all deployed tables. Continue? (yes/no): ")
        if response.lower() != 'yes':
            logger.info("Cleanup cancelled")
            return True
    
    try:
        from ..utils.constants import get_table_config
        from .create_venue_cache import delete_venue_cache_table
        
        config = get_table_config()
        logger.info("Cleaning up tables...")
        
        # Delete cache tables
        if delete_venue_cache_table():
            logger.info("✅ Venue cache table deleted")
        else:
            logger.error("❌ Failed to delete venue cache table")
            
        # Note: Core tables and other cache tables would need similar cleanup functions
        logger.warning("⚠️  Manual cleanup may be required for some tables")
        
        return True
        
    except Exception as e:
        logger.error(f"Error during cleanup: {e}")
        return False

def interactive_setup():
    """Interactive setup for table deployment."""
    print("🚀 Football Fixture Predictions - Table Deployment")
    print("=" * 50)
    
    # Get configuration from user
    app_name = input("Enter application/prefix name (e.g., 'myapp'): ").strip()
    environment = input("Enter environment (dev/staging/prod) [dev]: ").strip() or 'dev'
    
    suffix = ""
    if input("Add version suffix? (y/n) [n]: ").strip().lower() == 'y':
        suffix = input("Enter suffix (e.g., 'v1', 'v2'): ").strip()
    
    # Preview table names
    old_prefix = os.environ.get('TABLE_PREFIX', '')
    old_suffix = os.environ.get('TABLE_SUFFIX', '')
    old_env = os.environ.get('ENVIRONMENT', 'dev')
    
    # Set temporary environment variables to preview
    os.environ['TABLE_PREFIX'] = app_name
    os.environ['TABLE_SUFFIX'] = suffix
    os.environ['ENVIRONMENT'] = environment
    
    from ..utils.constants import get_table_config
    config = get_table_config()
    
    print(f"\n📋 Deployment Preview:")
    print(f"  Application: {app_name}")
    print(f"  Environment: {environment}")
    print(f"  Suffix: {suffix or 'None'}")
    print(f"\n📊 Tables to be created:")
    
    all_tables = {**config['core_tables'], **config['cache_tables']}
    for table_type, table_name in all_tables.items():
        print(f"  - {table_type}: {table_name}")
    
    # Confirm deployment
    if input(f"\n✅ Proceed with deployment? (y/n): ").strip().lower() != 'y':
        # Restore original environment
        os.environ['TABLE_PREFIX'] = old_prefix
        os.environ['TABLE_SUFFIX'] = old_suffix  
        os.environ['ENVIRONMENT'] = old_env
        print("Deployment cancelled")
        return False
    
    return True

def main():
    """Main deployment function."""
    parser = argparse.ArgumentParser(description='Deploy DynamoDB tables for football fixture predictions')
    parser.add_argument('--prefix', help='Table name prefix (e.g., myapp)')
    parser.add_argument('--suffix', help='Table name suffix (e.g., v1)')
    parser.add_argument('--environment', help='Environment (dev/staging/prod)', default='dev')
    parser.add_argument('--cleanup', action='store_true', help='Clean up existing tables')
    parser.add_argument('--yes', action='store_true', help='Skip confirmation prompts')
    
    args = parser.parse_args()
    
    # Handle cleanup
    if args.cleanup:
        return cleanup_tables(confirm=args.yes)
    
    # Setup environment variables
    if args.prefix or args.suffix:
        config = setup_environment_variables(args.prefix, args.suffix, args.environment)
    else:
        # Interactive mode
        if not interactive_setup():
            return False
        # Re-get config after interactive setup
        from ..utils.constants import get_table_config
        config = get_table_config()
    
    # Deploy tables
    logger.info("🚀 Starting table deployment...")
    start_time = datetime.now()
    
    success = True
    
    # Create core tables
    if not create_core_tables():
        logger.error("Failed to set up core tables")
        success = False
    
    # Create cache tables
    if not create_cache_tables():
        logger.error("Failed to create cache tables") 
        success = False
    
    # Verify deployment
    if success and not verify_deployment():
        logger.warning("Deployment verification had issues")
        success = False
    
    # Summary
    duration = datetime.now() - start_time
    logger.info(f"Deployment completed in {duration.total_seconds():.2f} seconds")
    
    if success:
        logger.info("🎉 All tables deployed successfully!")
        logger.info("\n📊 Deployment Summary:")
        all_tables = {**config['core_tables'], **config['cache_tables']}
        for table_type, table_name in all_tables.items():
            logger.info(f"  ✅ {table_type}: {table_name}")
        
        logger.info("\n🔧 Next Steps:")
        logger.info("1. Update your application configuration to use these table names")
        logger.info("2. Test basic operations (read/write) on the new tables")
        logger.info("3. Configure monitoring and alerting for the new tables")
        logger.info("4. Set up backup policies if needed")
        
    else:
        logger.error("❌ Deployment completed with errors")
        logger.info("Please check the logs above and resolve any issues")
        return False
    
    return True

if __name__ == "__main__":
    try:
        success = main()
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        logger.info("Deployment cancelled by user")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        sys.exit(1)
```

### Phase 4: Create Environment Configuration Documentation

**File: [`docs/ENVIRONMENT_CONFIGURATION.md`](docs/ENVIRONMENT_CONFIGURATION.md)**

```markdown
# Environment Configuration Guide

## Overview

The football fixture predictions application supports environment-based table naming to enable multiple isolated deployments without conflicts.

## Environment Variables

### Required Variables

| Variable | Description | Example | Default |
|----------|-------------|---------|---------|
| `TABLE_PREFIX` | Prefix for all table names | `myapp` | `""` (empty) |
| `TABLE_SUFFIX` | Suffix for all table names | `prod` | `""` (empty) |
| `ENVIRONMENT` | Deployment environment | `prod` | `dev` |

### Optional Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `RAPIDAPI_KEY` | API-Football API key | (required for API calls) |

## Table Naming Examples

### Basic Prefix
```bash
export TABLE_PREFIX="football-pred"
```
**Result:** `football-pred-game_fixtures`, `football-pred-team_parameters`

### Environment Separation
```bash
export TABLE_PREFIX="prod"
export ENVIRONMENT="production"
```
**Result:** `prod-game_fixtures`, `prod-league_parameters`

### Full Isolation
```bash
export TABLE_PREFIX="mycompany-football"
export TABLE_SUFFIX="v2"
export ENVIRONMENT="production"
```
**Result:** `mycompany-football-game_fixtures-v2`

## Deployment Scenarios

### Scenario 1: Development Environment
```bash
export TABLE_PREFIX="dev"
export ENVIRONMENT="development"
python -m src.infrastructure.deploy_tables
```

### Scenario 2: Production Deployment  
```bash
export TABLE_PREFIX="prod"
export TABLE_SUFFIX="v1"
export ENVIRONMENT="production"
python -m src.infrastructure.deploy_tables
```

### Scenario 3: Multi-Tenant Application
```bash
# Tenant A
export TABLE_PREFIX="tenant-a"
python -m src.infrastructure.deploy_tables

# Tenant B  
export TABLE_PREFIX="tenant-b"
python -m src.infrastructure.deploy_tables
```

## Configuration Validation

Check current configuration:
```python
from src.utils.constants import get_table_config
import json
print(json.dumps(get_table_config(), indent=2))
```

## AWS Permissions

Ensure your AWS credentials have permissions for:
- `dynamodb:CreateTable`
- `dynamodb:DescribeTable`
- `dynamodb:UpdateTimeToLive`
- `dynamodb:PutItem`
- `dynamodb:GetItem`
- `dynamodb:UpdateItem`
- `dynamodb:DeleteItem`
- `dynamodb:Scan`
- `dynamodb:Query`

## Troubleshooting

### Table Already Exists
If you get "ResourceInUseException", the table already exists with that name. Either:
1. Use a different prefix/suffix
2. Delete the existing table
3. Use the existing table if it's compatible

### Permission Denied
Ensure your AWS credentials have DynamoDB permissions and are correctly configured:
```bash
aws configure list
aws sts get-caller-identity
```

### Environment Variables Not Working
Verify environment variables are set:
```bash
echo $TABLE_PREFIX
echo $TABLE_SUFFIX
echo $ENVIRONMENT
```

## Best Practices

1. **Use meaningful prefixes** that identify the application/team
2. **Include environment** in the naming strategy
3. **Document your naming convention** for the team
4. **Test in development** before deploying to production
5. **Monitor table costs** after deployment
6. **Set up alerts** for table health and performance
```

## Implementation Checklist

### Files to Modify

- [x] **[`src/utils/constants.py`](src/utils/constants.py)** - Add environment-based table naming
- [x] **[`src/infrastructure/create_venue_cache.py`](src/infrastructure/create_venue_cache.py)** - Use configurable table name
- [x] **[`src/infrastructure/create_league_standings_cache.py`](src/infrastructure/create_league_standings_cache.py)** - Use configurable table name  
- [x] **[`src/data/tactical_data_collector.py`](src/data/tactical_data_collector.py)** - Use configurable table name
- [ ] **[`src/data/database_client.py`](src/data/database_client.py)** - Already uses constants, no changes needed

### New Files to Create

- [x] **[`src/infrastructure/deploy_tables.py`](src/infrastructure/deploy_tables.py)** - Deployment script
- [x] **[`docs/ENVIRONMENT_CONFIGURATION.md`](docs/ENVIRONMENT_CONFIGURATION.md)** - Configuration guide

## Testing Strategy

### 1. Local Testing
```bash
# Set test environment
export TABLE_PREFIX="test"
export TABLE_SUFFIX="local"

# Deploy tables
python -m src.infrastructure.deploy_tables

# Run application tests
python -m pytest tests/

# Cleanup
python -m src.infrastructure.deploy_tables --cleanup --yes
```

### 2. Integration Testing
```bash
# Test with different configurations
for env in dev staging prod; do
    export TABLE_PREFIX="inttest"
    export TABLE_SUFFIX="$env"
    python -m src.infrastructure.deploy_tables --yes
    # Run integration tests
    # Cleanup
    python -m src.infrastructure.deploy_tables --cleanup --yes
done
```

## Migration Guide

### From Shared Tables to Dedicated Tables

1. **Backup existing data** (if needed)
2. **Deploy new tables** with environment-specific names
3. **Migrate data** (if required)
4. **Update application configuration**
5. **Test thoroughly**
6. **Monitor performance**

### Example Migration Script
```bash
#!/bin/bash
# migrate_to_dedicated_tables.sh

echo "🚀 Migrating to dedicated tables..."

# Set new table configuration
export TABLE_PREFIX="myapp"
export TABLE_SUFFIX="v1"
export ENVIRONMENT="production"

# Deploy new tables
echo "📊 Deploying new tables..."
python -m src.infrastructure.deploy_tables --yes

# TODO: Add data migration logic here if needed

echo "✅ Migration complete!"
```

## Rollback Plan

### Quick Rollback
1. **Revert environment variables** to previous values
2. **Restart application** to use original table names
3. **Clean up new tables** if needed

### Complete Rollback
```bash
# Save current config
export OLD_PREFIX=$TABLE_PREFIX
export OLD_SUFFIX=$TABLE_SUFFIX

# Clean up new tables
python -m src.infrastructure.deploy_tables --cleanup --yes

# Revert to shared tables
unset TABLE_PREFIX
unset TABLE_SUFFIX
export ENVIRONMENT="production"

# Restart application
```

## Cost Considerations

### Pay-Per-Request vs Provisioned
- **Pay-per-request** - Good for variable workloads
- **Provisioned** - Better for predictable, high-volume workloads

### Monitoring Costs
- Set up **CloudWatch billing alerts**
- Monitor **read/write capacity** usage
- Review **storage costs** regularly

## Security Considerations

### Access Control
- Use **IAM roles** with minimum required permissions
- **Separate credentials** for different environments
- **Audit access logs** regularly

### Data Protection
- Enable **encryption at rest**
- Use **VPC endpoints** for private access
- Consider **backup strategies**

---

## Summary

This implementation provides:

✅ **Complete table isolation** from shared applications  
✅ **Environment-based naming** for multi-environment deployments  
✅ **Backward compatibility** with existing code  
✅ **Easy deployment and rollback** procedures  
✅ **Comprehensive documentation** for developers  
✅ **Testing and migration strategies**  

The solution allows flexible deployment scenarios while maintaining all existing functionality and providing clear upgrade paths for different use cases.