"""
Schema formatter utility for GenAI pundit system.

Loads and formats the team parameter schema for AI consumption,
providing essential documentation without overwhelming context.
"""

import json
import os
from pathlib import Path


def load_parameter_schema():
    """
    Load and format team parameter schema for AI consumption.

    Returns a formatted JSON string containing essential schema information
    for interpreting team parameters in fixture analysis.

    Returns:
        str: Formatted JSON string with schema documentation
    """
    # Locate schema file (two levels up from config directory)
    schema_path = Path(__file__).parent.parent.parent / 'team_parameter_schema.json'

    if not schema_path.exists():
        raise FileNotFoundError(f"Schema file not found at {schema_path}")

    with open(schema_path, 'r') as f:
        full_schema = json.load(f)

    # Extract essential parts for AI (condensed but complete)
    ai_schema = {
        'schema_version': full_schema['schema_version'],
        'description': full_schema['description'],

        'phase_architecture': full_schema['phase_architecture'],

        'scale_definitions': full_schema['scale_definitions'],

        'field_registry': {
            'phase_0_base': full_schema['field_registry']['phase_0_base'],
            'multipliers': full_schema['field_registry']['multipliers'],
            'phase_1_segmented': full_schema['field_registry']['phase_1_segmented'],
            'phase_2_venue': full_schema['field_registry']['phase_2_venue'],
            'phase_3_temporal': full_schema['field_registry']['phase_3_temporal'],
            'phase_4_tactical': full_schema['field_registry']['phase_4_tactical'],
            'phase_5_classification': full_schema['field_registry']['phase_5_classification']
        },

        'usage_examples': full_schema['usage_examples'],

        'calculation_notes': full_schema['calculation_notes']
    }

    return json.dumps(ai_schema, indent=2)


def get_schema_summary():
    """
    Get a condensed schema summary for quick reference.

    Returns a minimal version focusing on scale types and key interpretations.
    Useful if full schema is too large for context.

    Returns:
        str: Formatted summary string
    """
    schema_path = Path(__file__).parent.parent.parent / 'team_parameter_schema.json'

    if not schema_path.exists():
        raise FileNotFoundError(f"Schema file not found at {schema_path}")

    with open(schema_path, 'r') as f:
        full_schema = json.load(f)

    summary = {
        'schema_version': full_schema['schema_version'],
        'phase_architecture': full_schema['phase_architecture'],
        'scale_definitions': full_schema['scale_definitions'],
        'usage_examples': full_schema['usage_examples']
    }

    return json.dumps(summary, indent=2)


if __name__ == '__main__':
    # Test loading
    try:
        schema = load_parameter_schema()
        print("✓ Schema loaded successfully")
        print(f"✓ Schema size: {len(schema)} characters (~{len(schema)//4} tokens)")

        summary = get_schema_summary()
        print(f"✓ Summary size: {len(summary)} characters (~{len(summary)//4} tokens)")
    except Exception as e:
        print(f"✗ Error loading schema: {e}")
