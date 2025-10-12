"""
Lightweight data type conversion utilities without numpy dependency.
Used by handlers that don't process numerical arrays.
"""

from decimal import Decimal
from datetime import datetime


def convert_for_dynamodb(data):
    """
    Prepare data for DynamoDB storage by converting appropriate types.
    This is a lightweight version without numpy support.

    Args:
        data: Data structure to prepare for DynamoDB

    Returns:
        Data structure ready for DynamoDB storage
    """
    if isinstance(data, dict):
        return {k: convert_for_dynamodb(v) for k, v in data.items()}
    elif isinstance(data, list):
        return [convert_for_dynamodb(item) for item in data]
    elif isinstance(data, datetime):
        return int(data.timestamp())
    elif isinstance(data, float):
        return Decimal(str(data))
    else:
        return data


def decimal_to_float(x):
    """
    Convert Decimal objects to floats recursively.
    
    Args:
        x: Data structure or primitive to convert
        
    Returns:
        Data structure with Decimal objects converted to floats
    """
    if isinstance(x, Decimal):
        return float(x)
    elif isinstance(x, dict):
        return {k: decimal_to_float(v) for k, v in x.items()}
    elif isinstance(x, list):
        return [decimal_to_float(v) for v in x]
    else:
        return x