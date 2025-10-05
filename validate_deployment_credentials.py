#!/usr/bin/env python3
"""
Deployment Credentials Validation Script
Tests AWS and RAPIDAPI credentials before production deployment
"""

import os
import sys
import boto3
import requests
from botocore.exceptions import ClientError, NoCredentialsError

# Add src to path
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))
from src.utils.constants import RAPIDAPI_KEY, API_FOOTBALL_BASE_URL, API_FOOTBALL_HOST

def print_header(title):
    """Print a formatted header"""
    print("\n" + "=" * 70)
    print(f" {title}")
    print("=" * 70)

def print_result(check_name, status, details=""):
    """Print check result"""
    symbol = "✅" if status else "❌"
    print(f"{symbol} {check_name}")
    if details:
        print(f"   {details}")

def check_rapidapi_key():
    """Validate RAPIDAPI_KEY and test API-Football access"""
    print_header("RAPIDAPI KEY VALIDATION")
    
    # Check if key exists
    if not RAPIDAPI_KEY or RAPIDAPI_KEY == "your_key_here":
        print_result("RAPIDAPI_KEY", False, "Key not configured or using placeholder")
        return False
    
    print_result("RAPIDAPI_KEY Found", True, f"Key: {RAPIDAPI_KEY[:20]}...")
    
    # Test API access
    print("\nTesting API-Football connection...")
    try:
        headers = {
            'X-RapidAPI-Key': RAPIDAPI_KEY,
            'X-RapidAPI-Host': API_FOOTBALL_HOST
        }
        
        # Test with a simple endpoint (leagues)
        response = requests.get(
            f"{API_FOOTBALL_BASE_URL}/leagues",
            headers=headers,
            params={'id': 39},  # Premier League
            timeout=10
        )
        
        if response.status_code == 200:
            data = response.json()
            print_result("API Connection", True, "Successfully connected to API-Football")
            
            # Check quota
            if 'requests' in response.headers.get('x-ratelimit-requests-remaining', ''):
                remaining = response.headers.get('x-ratelimit-requests-remaining', 'Unknown')
                limit = response.headers.get('x-ratelimit-requests-limit', 'Unknown')
                print(f"   API Quota: {remaining}/{limit} requests remaining")
            
            return True
        elif response.status_code == 401:
            print_result("API Connection", False, "Invalid API key - 401 Unauthorized")
            return False
        elif response.status_code == 429:
            print_result("API Connection", False, "Rate limit exceeded - need higher tier")
            return False
        else:
            print_result("API Connection", False, f"API returned status code: {response.status_code}")
            return False
            
    except requests.exceptions.RequestException as e:
        print_result("API Connection", False, f"Connection error: {str(e)}")
        return False

def check_aws_credentials():
    """Validate AWS credentials configuration"""
    print_header("AWS CREDENTIALS VALIDATION")
    
    # Check environment variables
    aws_access_key = os.getenv('AWS_ACCESS_KEY_ID')
    aws_secret_key = os.getenv('AWS_SECRET_ACCESS_KEY')
    aws_region = os.getenv('AWS_DEFAULT_REGION', os.getenv('AWS_REGION', 'not set'))
    
    print(f"AWS_ACCESS_KEY_ID: {'Set' if aws_access_key else 'Not set'}")
    print(f"AWS_SECRET_ACCESS_KEY: {'Set' if aws_secret_key else 'Not set'}")
    print(f"AWS Region: {aws_region}")
    
    # Test AWS credentials
    print("\nTesting AWS access...")
    try:
        # Try to get caller identity
        sts = boto3.client('sts')
        identity = sts.get_caller_identity()
        
        print_result("AWS Credentials", True, f"Account: {identity['Account']}")
        print(f"   User/Role: {identity['Arn']}")
        
        return True
        
    except NoCredentialsError:
        print_result("AWS Credentials", False, "No AWS credentials found")
        print("\n   Configure credentials using one of:")
        print("   1. Environment variables: AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY")
        print("   2. AWS CLI: aws configure")
        print("   3. IAM role (if running on EC2)")
        return False
        
    except ClientError as e:
        print_result("AWS Credentials", False, f"AWS Error: {str(e)}")
        return False
        
    except Exception as e:
        print_result("AWS Credentials", False, f"Unexpected error: {str(e)}")
        return False

def check_dynamodb_access():
    """Test DynamoDB access"""
    print_header("DYNAMODB ACCESS VALIDATION")
    
    try:
        dynamodb = boto3.client('dynamodb')
        
        # List tables to verify access
        response = dynamodb.list_tables(Limit=1)
        
        print_result("DynamoDB Access", True, "Can access DynamoDB service")
        print(f"   Region: {dynamodb.meta.region_name}")
        
        # Check if any of our tables exist
        all_tables = dynamodb.list_tables()['TableNames']
        football_tables = [t for t in all_tables if 'fixture' in t.lower() or 'parameter' in t.lower()]
        
        if football_tables:
            print(f"   Found {len(football_tables)} football-related tables")
            for table in football_tables[:5]:  # Show first 5
                print(f"     - {table}")
        else:
            print("   No football-related tables found (expected before deployment)")
        
        return True
        
    except ClientError as e:
        error_code = e.response['Error']['Code']
        if error_code == 'AccessDenied':
            print_result("DynamoDB Access", False, "Access denied - check IAM permissions")
        else:
            print_result("DynamoDB Access", False, f"Error: {error_code}")
        return False
        
    except Exception as e:
        print_result("DynamoDB Access", False, f"Error: {str(e)}")
        return False

def check_environment_variables():
    """Check deployment environment variables"""
    print_header("ENVIRONMENT VARIABLES VALIDATION")
    
    env_vars = {
        'TABLE_PREFIX': os.getenv('TABLE_PREFIX', 'Not set (using default: empty)'),
        'TABLE_SUFFIX': os.getenv('TABLE_SUFFIX', 'Not set (using default: empty)'),
        'ENVIRONMENT': os.getenv('ENVIRONMENT', 'Not set (using default: dev)'),
        'RAPIDAPI_KEY': 'Set' if RAPIDAPI_KEY else 'Not set',
        'AWS_DEFAULT_REGION': os.getenv('AWS_DEFAULT_REGION', 'Not set')
    }
    
    all_good = True
    for var, value in env_vars.items():
        if 'Not set' in value and var != 'TABLE_PREFIX' and var != 'TABLE_SUFFIX':
            print_result(var, False, value)
            all_good = False
        else:
            print_result(var, True, value)
    
    return all_good

def main():
    """Run all validation checks"""
    print_header("DEPLOYMENT CREDENTIALS VALIDATION")
    print("Football Fixture Prediction System v6.0")
    print("Validating credentials before production deployment...")
    
    results = {
        'rapidapi': check_rapidapi_key(),
        'aws_credentials': check_aws_credentials(),
        'dynamodb': check_dynamodb_access(),
        'environment': check_environment_variables()
    }
    
    # Summary
    print_header("VALIDATION SUMMARY")
    
    all_passed = all(results.values())
    
    if all_passed:
        print("✅ ALL CHECKS PASSED - READY FOR DEPLOYMENT")
        print("\nNext steps:")
        print("1. Deploy DynamoDB tables: python -m src.infrastructure.deploy_tables")
        print("2. Create Lambda package: Follow deployment guide")
        print("3. Deploy Lambda function with environment variables")
        return 0
    else:
        print("❌ SOME CHECKS FAILED - DEPLOYMENT NOT READY")
        print("\nFailed checks:")
        for check, passed in results.items():
            if not passed:
                print(f"  - {check}")
        print("\nPlease resolve the issues above before deploying.")
        return 1

if __name__ == "__main__":
    sys.exit(main())