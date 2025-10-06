"""
Data type conversion utilities for the football fixture predictions system.
Consolidates duplicate conversion functions from across the codebase.
"""

import json
import numpy as np
from decimal import Decimal
from datetime import datetime


def decimal_default(obj):
    """
    Function to convert Decimal to float for JSON serialization.
    Also handles numpy types and other numeric types.
    
    Args:
        obj: Object to convert for JSON serialization
        
    Returns:
        Converted object suitable for JSON serialization
    """
    if isinstance(obj, Decimal):
        return float(obj)
    # Handle numpy types
    if hasattr(obj, 'item'):  # numpy scalars
        return obj.item()
    if hasattr(obj, 'tolist'):  # numpy arrays
        return obj.tolist()
    # Handle other numeric types
    if isinstance(obj, (np.int64, np.int32, np.float64, np.float32)):
        return obj.item()
    # If we can't convert it, return the string representation
    return str(obj)


def convert_floats_to_decimal(data):
    """
    Recursively convert floats to Decimal objects for DynamoDB compatibility.
    
    Args:
        data: Data structure (list, dict, or primitive) to convert
        
    Returns:
        Data structure with floats converted to Decimal objects
    """
    if isinstance(data, list):
        return [convert_floats_to_decimal(item) for item in data]
    elif isinstance(data, dict):
        return {k: convert_floats_to_decimal(v) for k, v in data.items()}
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


def convert_for_json(obj):
    """
    Recursively convert numpy types to Python types so that json.dumps works.
    
    Args:
        obj: Object to convert
        
    Returns:
        Object with numpy types converted to Python types
    """
    if isinstance(obj, np.integer):
        return int(obj)
    elif isinstance(obj, np.floating):
        return float(obj)
    elif isinstance(obj, np.ndarray):
        return obj.tolist()
    elif isinstance(obj, dict):
        return {k: convert_for_json(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [convert_for_json(v) for v in obj]
    else:
        return obj


def convert_for_dynamodb(data):
    """
    Prepare data for DynamoDB storage by converting appropriate types.

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
    elif isinstance(data, np.integer):
        return int(data)
    elif isinstance(data, np.floating):
        return Decimal(str(float(data)))
    elif isinstance(data, np.ndarray):
        return convert_for_dynamodb(data.tolist())
    else:
        return data


def safe_decimal_conversion(value, default=Decimal('0.0')):
    """
    Safely convert a value to Decimal with fallback.
    
    Args:
        value: Value to convert to Decimal
        default: Default value if conversion fails
        
    Returns:
        Decimal representation of value or default
    """
    try:
        if isinstance(value, Decimal):
            return value
        elif isinstance(value, (int, float)):
            return Decimal(str(value))
        elif isinstance(value, str):
            return Decimal(value)
        else:
            return default
    except (ValueError, TypeError, decimal.InvalidOperation):
        return default


def safe_float_conversion(value, default=0.0):
    """
    Safely convert a value to float with fallback.
    
    Args:
        value: Value to convert to float
        default: Default value if conversion fails
        
    Returns:
        Float representation of value or default
    """
    try:
        if isinstance(value, (int, float)):
            return float(value)
        elif isinstance(value, Decimal):
            return float(value)
        elif isinstance(value, str):
            return float(value)
        else:
            return default
    except (ValueError, TypeError):
        return default