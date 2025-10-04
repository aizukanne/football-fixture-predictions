"""
DynamoDB Table Creation Script for League Standings Cache

This script creates the `league_standings_cache` table required for Phase 1
opponent strength stratification. The table caches league standings data
with a 24-hour TTL to optimize performance and reduce API calls.

Table Schema:
- Partition Key: cache_key (league_id-season)
- TTL: 24 hours for automatic cleanup
- Attributes: standings_data, team_positions, total_teams, timestamp

Usage:
    python -m src.infrastructure.create_league_standings_cache
"""

import boto3
import time
from datetime import datetime
from botocore.exceptions import ClientError
import logging
import sys
import os

# Add src to path for imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))
from src.utils.constants import _get_table_name

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def create_league_standings_cache_table():
    """
    Create the league_standings_cache DynamoDB table.
    
    This table is essential for Phase 1 opponent strength stratification
    performance optimization by caching API-Football standings data.
    
    Returns:
        bool: True if table created successfully, False otherwise
    """
    
    # Initialize DynamoDB client
    try:
        dynamodb = boto3.resource('dynamodb')
        client = boto3.client('dynamodb')
    except Exception as e:
        logger.error(f"Failed to initialize DynamoDB client: {e}")
        return False
    
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
        logger.error(f"Error checking table existence: {e}")
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
            }
        ]
    }
    
    try:
        # Create the table
        logger.info(f"Creating table {table_name}...")
        table = dynamodb.create_table(**table_definition)
        
        # Wait for table to be created
        logger.info("Waiting for table to become active...")
        table.wait_until_exists()
        
        # Enable TTL on the table
        logger.info("Enabling TTL for automatic cleanup...")
        client.update_time_to_live(
            TableName=table_name,
            TimeToLiveSpecification={
                'AttributeName': 'ttl',
                'Enabled': True
            }
        )
        
        logger.info(f"Table {table_name} created successfully!")
        logger.info("Table features:")
        logger.info("  - Partition Key: cache_key (league_id-season format)")
        logger.info("  - TTL enabled on 'ttl' attribute for 24-hour cache expiry")
        logger.info("  - Pay-per-request billing mode")
        logger.info("  - Supports Phase 1 opponent strength stratification")
        
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
        dynamodb = boto3.resource('dynamodb')
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
                logger.info("TTL enabled successfully")
            except Exception as e:
                logger.error(f"Failed to enable TTL: {e}")
                return False
        
        logger.info(f"Table {table_name} is properly configured:")
        logger.info(f"  - Status: {table.table_status}")
        logger.info(f"  - TTL Status: {ttl_status}")
        logger.info(f"  - Item Count: {table.item_count}")
        
        return True
        
    except Exception as e:
        logger.error(f"Failed to verify table setup: {e}")
        return False


def test_cache_operations():
    """
    Test basic cache operations to ensure the table is working.
    
    Returns:
        bool: True if tests pass
    """
    try:
        dynamodb = boto3.resource('dynamodb')
        table = dynamodb.Table(_get_table_name('league_standings_cache'))
        
        # Test data
        test_cache_key = 'test-league-2024'
        current_timestamp = datetime.now().timestamp()
        ttl_timestamp = int(current_timestamp + 3600)  # 1 hour TTL for test
        
        test_data = {
            'cache_key': test_cache_key,
            'timestamp': int(current_timestamp),  # Convert to int for DynamoDB
            'ttl': ttl_timestamp,
            'standings_data': [
                {'team_id': 1, 'team_name': 'Test Team 1', 'position': 1},
                {'team_id': 2, 'team_name': 'Test Team 2', 'position': 2}
            ],
            'team_positions': {
                '1': {'position': 1, 'tier': 'top'},
                '2': {'position': 2, 'tier': 'top'}
            },
            'total_teams': 2,
            'last_updated': '2024'
        }
        
        # Test write operation
        logger.info("Testing cache write operation...")
        table.put_item(Item=test_data)
        
        # Test read operation
        logger.info("Testing cache read operation...")
        response = table.get_item(Key={'cache_key': test_cache_key})
        
        if 'Item' not in response:
            logger.error("Failed to read test data from cache")
            return False
        
        retrieved_data = response['Item']
        if retrieved_data['cache_key'] != test_cache_key:
            logger.error("Retrieved data does not match test data")
            return False
        
        # Clean up test data
        logger.info("Cleaning up test data...")
        table.delete_item(Key={'cache_key': test_cache_key})
        
        logger.info("Cache operations test passed!")
        return True
        
    except Exception as e:
        logger.error(f"Cache operations test failed: {e}")
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
    
    # Wait a moment for table to be fully ready
    time.sleep(2)
    
    # Step 2: Verify table configuration
    if not verify_table_setup():
        logger.error("Table verification failed. Exiting.")
        return False
    
    # Step 3: Test basic operations
    if not test_cache_operations():
        logger.error("Cache operations test failed. Exiting.")
        return False
    
    logger.info("=== Setup Complete ===")
    logger.info("League standings cache table is ready for Phase 1 opponent stratification!")
    logger.info("The table supports:")
    logger.info("  ✅ Caching league standings with 24-hour TTL")
    logger.info("  ✅ Automatic cleanup of expired cache entries")
    logger.info("  ✅ High-performance lookups for opponent classification")
    logger.info("  ✅ Cost optimization through reduced API calls")
    
    return True


if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)