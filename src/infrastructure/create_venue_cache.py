"""
Create venue cache DynamoDB table for storing stadium details.

This module creates and configures the venue_cache table for:
- Caching venue details from API-Football
- 7-day TTL for venue information (stadium details rarely change)
- Global secondary index on coordinates for geographic queries
- Optimized for venue detail lookups and distance calculations

Phase 2: Home/Away Venue Analysis
Infrastructure component for venue data caching and performance optimization.
"""

import boto3
from botocore.exceptions import ClientError
from decimal import Decimal
import json
from typing import Dict, Optional

from ..data.database_client import dynamodb
from ..utils.constants import _get_table_name


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

        # Define table schema
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
                    'Key': 'Purpose',
                    'Value': 'VenueCaching'
                },
                {
                    'Key': 'Phase',
                    'Value': 'Phase2-VenueAnalysis'
                },
                {
                    'Key': 'TTL',
                    'Value': '7days'
                }
            ]
        }
        
        # Create the table
        response = dynamodb_client.create_table(**table_definition)
        
        print(f"Creating table {table_name}...")
        print(f"Table ARN: {response['TableDescription']['TableArn']}")
        
        # Wait for table to be created
        waiter = dynamodb_client.get_waiter('table_exists')
        waiter.wait(TableName=table_name, WaiterConfig={'Delay': 5, 'MaxAttempts': 20})
        
        print(f"Table {table_name} created successfully!")
        
        # Enable TTL (sometimes needs separate call)
        try:
            dynamodb_client.update_time_to_live(
                TableName=table_name,
                TimeToLiveSpecification={
                    'AttributeName': 'ttl',
                    'Enabled': True
                }
            )
            print("TTL enabled successfully")
        except ClientError as e:
            if 'ValidationException' in str(e) and 'TTL is already enabled' in str(e):
                print("TTL was already enabled")
            else:
                print(f"Warning: Could not enable TTL: {e}")
        
        return True
        
    except ClientError as e:
        print(f"Error creating venue cache table: {e}")
        return False
    except Exception as e:
        print(f"Unexpected error creating venue cache table: {e}")
        return False


def delete_venue_cache_table() -> bool:
    """
    Delete the venue_cache table (for cleanup/testing).

    Returns:
        True if table deleted successfully, False otherwise
    """
    try:
        dynamodb_client = dynamodb.meta.client
        table_name = _get_table_name('venue_cache')
        
        # Delete table
        dynamodb_client.delete_table(TableName=table_name)
        
        # Wait for table to be deleted
        waiter = dynamodb_client.get_waiter('table_not_exists')
        waiter.wait(TableName=table_name, WaiterConfig={'Delay': 5, 'MaxAttempts': 20})
        
        print(f"Table {table_name} deleted successfully!")
        return True
        
    except ClientError as e:
        if e.response['Error']['Code'] == 'ResourceNotFoundException':
            print("Table does not exist")
            return True
        else:
            print(f"Error deleting venue cache table: {e}")
            return False
    except Exception as e:
        print(f"Unexpected error deleting venue cache table: {e}")
        return False


def describe_venue_cache_table() -> Optional[Dict]:
    """
    Get detailed information about the venue_cache table.

    Returns:
        Table description dict or None if table doesn't exist
    """
    try:
        dynamodb_client = dynamodb.meta.client
        table_name = _get_table_name('venue_cache')
        
        response = dynamodb_client.describe_table(TableName=table_name)
        table_info = response['TableDescription']
        
        print(f"Table Name: {table_info['TableName']}")
        print(f"Table Status: {table_info['TableStatus']}")
        print(f"Item Count: {table_info.get('ItemCount', 'Unknown')}")
        print(f"Table Size: {table_info.get('TableSizeBytes', 0)} bytes")
        print(f"Billing Mode: {table_info.get('BillingModeSummary', {}).get('BillingMode', 'Unknown')}")
        
        # TTL information
        ttl_info = table_info.get('TimeToLiveDescription', {})
        if ttl_info:
            print(f"TTL Status: {ttl_info.get('TimeToLiveStatus', 'Unknown')}")
            print(f"TTL Attribute: {ttl_info.get('AttributeName', 'Unknown')}")
        
        # GSI information
        gsi_list = table_info.get('GlobalSecondaryIndexes', [])
        for gsi in gsi_list:
            print(f"GSI: {gsi['IndexName']} - Status: {gsi['IndexStatus']}")
        
        return table_info
        
    except ClientError as e:
        if e.response['Error']['Code'] == 'ResourceNotFoundException':
            print("Table does not exist")
            return None
        else:
            print(f"Error describing venue cache table: {e}")
            return None
    except Exception as e:
        print(f"Unexpected error describing venue cache table: {e}")
        return None


def test_venue_cache_operations() -> bool:
    """
    Test basic operations on the venue_cache table.
    
    Returns:
        True if all operations successful, False otherwise
    """
    try:
        from datetime import datetime, timedelta

        try:
            table = dynamodb.Table(_get_table_name('venue_cache'))
        except Exception as e:
            print(f"Could not initialize venue_cache table: {e}")
            return False
        
        # Test data
        test_venue = {
            'venue_id': 999999,  # Test venue ID
            'venue_name': 'Test Stadium',
            'capacity': 50000,
            'surface': 'grass',
            'coordinates': {
                'latitude': Decimal('51.5074'),  # London coordinates
                'longitude': Decimal('-0.1278')
            },
            'climate_data': {
                'altitude': Decimal('11'),
                'typical_weather': 'temperate'
            },
            'cached_at': datetime.now().isoformat(),
            'ttl': int((datetime.now() + timedelta(days=7)).timestamp())
        }
        
        # Test write
        print("Testing venue cache write...")
        table.put_item(Item=test_venue)
        print("Write successful")
        
        # Test read
        print("Testing venue cache read...")
        response = table.get_item(Key={'venue_id': 999999})
        if 'Item' in response:
            item = response['Item']
            print(f"Read successful: {item['venue_name']}")
        else:
            print("Error: Item not found after write")
            return False
        
        # Test delete
        print("Testing venue cache delete...")
        table.delete_item(Key={'venue_id': 999999})
        print("Delete successful")
        
        # Verify delete
        response = table.get_item(Key={'venue_id': 999999})
        if 'Item' not in response:
            print("Delete verification successful")
        else:
            print("Warning: Item still exists after delete")
        
        return True
        
    except Exception as e:
        print(f"Error testing venue cache operations: {e}")
        return False


def setup_venue_cache_infrastructure() -> bool:
    """
    Complete setup of venue cache infrastructure.
    
    This function:
    1. Creates the venue_cache table
    2. Configures TTL and GSI
    3. Tests basic operations
    4. Returns setup status
    
    Returns:
        True if setup completed successfully, False otherwise
    """
    print("Setting up venue cache infrastructure...")
    
    # Step 1: Create table
    if not create_venue_cache_table():
        print("Failed to create venue cache table")
        return False
    
    # Step 2: Describe table to verify setup
    table_info = describe_venue_cache_table()
    if not table_info:
        print("Failed to verify table creation")
        return False
    
    # Step 3: Test operations
    if not test_venue_cache_operations():
        print("Failed venue cache operation tests")
        return False
    
    print("✅ Venue cache infrastructure setup completed successfully!")
    print("\nTable Features:")
    print("- 7-day TTL for automatic data expiration")
    print("- Global secondary index on coordinates")
    print("- Pay-per-request billing")
    print("- Optimized for venue lookups and geographic queries")
    
    return True


if __name__ == '__main__':
    """
    Run venue cache setup when executed directly.
    """
    print("=== Venue Cache Infrastructure Setup ===")
    success = setup_venue_cache_infrastructure()
    
    if success:
        print("\n🎉 Setup completed successfully!")
        print("\nNext steps:")
        print("1. Venue data will be automatically cached on first API calls")
        print("2. Cache entries expire after 7 days")
        print("3. Geographic queries enabled via coordinates GSI")
    else:
        print("\n❌ Setup failed. Please check error messages above.")
        exit(1)