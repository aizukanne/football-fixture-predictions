"""
Create All SQS Queues for Football Fixture Prediction System

This module creates a complete, independent SQS infrastructure for the
football prediction system. Does not rely on any existing queues.

Queues Created:
1. football-fixture-predictions - Main fixture processing queue
2. football-prediction-dlq - Dead letter queue for failed predictions
3. football-league-parameter-updates - League parameter computation
4. football-league-dlq - DLQ for league parameter failures
5. football-team-parameter-updates - Team parameter computation
6. football-team-dlq - DLQ for team parameter failures
7. football-cache-updates - Cache refresh operations
8. football-cache-dlq - DLQ for cache update failures
9. football-match-results - Match result processing
10. football-results-dlq - DLQ for match result failures

Author: Football Fixture Prediction System
Phase: Complete Infrastructure Setup
Version: 1.0
"""

import boto3
import json
import os
import sys
from botocore.exceptions import ClientError
from typing import Dict, List, Tuple

# Add project root to path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '../..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)


class SQSQueueManager:
    """Manages creation and configuration of all SQS queues."""

    def __init__(self, environment: str = None, region: str = 'eu-west-2'):
        """
        Initialize queue manager.

        Args:
            environment: Environment identifier (dev, staging, prod)
            region: AWS region for queue creation
        """
        self.sqs = boto3.client('sqs', region_name=region)
        self.environment = environment or os.getenv('ENVIRONMENT', 'dev')
        self.region = region
        self.created_queues = {}

        # Apply environment-based naming
        self.table_prefix = os.getenv('TABLE_PREFIX', '')
        self.table_suffix = os.getenv('TABLE_SUFFIX', '')

    def _get_queue_name(self, base_name: str) -> str:
        """
        Generate environment-specific queue name.

        Args:
            base_name: Base queue name

        Returns:
            Full queue name with environment suffix
        """
        parts = []
        if self.table_prefix:
            parts.append(self.table_prefix.rstrip('_'))
        parts.append(base_name)
        if self.table_suffix:
            parts.append(self.table_suffix.lstrip('_'))
        elif self.environment and self.environment != 'prod':
            # Add environment suffix for non-prod
            parts.append(self.environment)

        return '_'.join(parts) if len(parts) > 1 else base_name

    def create_queue_with_dlq(self, queue_name: str, dlq_name: str,
                               visibility_timeout: int, max_receive_count: int,
                               message_retention: int = 1209600) -> Dict[str, str]:
        """
        Create a queue with its Dead Letter Queue.

        Args:
            queue_name: Main queue name
            dlq_name: Dead Letter Queue name
            visibility_timeout: Visibility timeout in seconds
            max_receive_count: Max receive attempts before moving to DLQ
            message_retention: Message retention period in seconds (default 14 days)

        Returns:
            Dict with queue_url, queue_arn, dlq_url, dlq_arn
        """
        print(f"\n{'='*70}")
        print(f"Creating Queue: {queue_name}")
        print(f"{'='*70}")

        # Apply environment naming
        full_queue_name = self._get_queue_name(queue_name)
        full_dlq_name = self._get_queue_name(dlq_name)

        print(f"  Queue Name: {full_queue_name}")
        print(f"  DLQ Name: {full_dlq_name}")

        # Step 1: Create Dead Letter Queue
        print(f"\n  [1/3] Creating Dead Letter Queue...")
        try:
            dlq_response = self.sqs.create_queue(
                QueueName=full_dlq_name,
                Attributes={
                    'MessageRetentionPeriod': str(message_retention),
                    'ReceiveMessageWaitTimeSeconds': '20',  # Long polling
                }
            )
            dlq_url = dlq_response['QueueUrl']
            print(f"  ✅ DLQ Created: {dlq_url}")
        except ClientError as e:
            if e.response['Error']['Code'] == 'QueueAlreadyExists':
                dlq_url = self.sqs.get_queue_url(QueueName=full_dlq_name)['QueueUrl']
                print(f"  ✅ DLQ Already Exists: {dlq_url}")
            else:
                print(f"  ❌ Error creating DLQ: {e}")
                raise

        # Get DLQ ARN
        dlq_attrs = self.sqs.get_queue_attributes(
            QueueUrl=dlq_url,
            AttributeNames=['QueueArn']
        )
        dlq_arn = dlq_attrs['Attributes']['QueueArn']
        print(f"  DLQ ARN: {dlq_arn}")

        # Step 2: Create main queue with redrive policy
        print(f"\n  [2/3] Creating Main Queue...")

        redrive_policy = {
            'deadLetterTargetArn': dlq_arn,
            'maxReceiveCount': str(max_receive_count)
        }

        try:
            queue_response = self.sqs.create_queue(
                QueueName=full_queue_name,
                Attributes={
                    'MessageRetentionPeriod': str(message_retention),
                    'VisibilityTimeout': str(visibility_timeout),
                    'ReceiveMessageWaitTimeSeconds': '20',  # Long polling
                    'RedrivePolicy': json.dumps(redrive_policy),
                    'MaximumMessageSize': '262144',  # 256 KB
                }
            )
            queue_url = queue_response['QueueUrl']
            print(f"  ✅ Queue Created: {queue_url}")
        except ClientError as e:
            if e.response['Error']['Code'] == 'QueueAlreadyExists':
                queue_url = self.sqs.get_queue_url(QueueName=full_queue_name)['QueueUrl']
                print(f"  ✅ Queue Already Exists: {queue_url}")
            else:
                print(f"  ❌ Error creating queue: {e}")
                raise

        # Get queue ARN
        queue_attrs = self.sqs.get_queue_attributes(
            QueueUrl=queue_url,
            AttributeNames=['QueueArn']
        )
        queue_arn = queue_attrs['Attributes']['QueueArn']
        print(f"  Queue ARN: {queue_arn}")

        # Step 3: Add tags
        print(f"\n  [3/3] Adding Tags...")
        try:
            self.sqs.tag_queue(
                QueueUrl=queue_url,
                Tags={
                    'Project': 'football-fixture-predictions',
                    'Environment': self.environment,
                    'Component': queue_name,
                    'ManagedBy': 'Infrastructure Script'
                }
            )
            print(f"  ✅ Tags Added")
        except Exception as e:
            print(f"  ⚠️  Warning: Could not add tags: {e}")

        result = {
            'queue_name': full_queue_name,
            'queue_url': queue_url,
            'queue_arn': queue_arn,
            'dlq_name': full_dlq_name,
            'dlq_url': dlq_url,
            'dlq_arn': dlq_arn
        }

        self.created_queues[queue_name] = result
        return result

    def create_all_queues(self) -> Dict[str, Dict]:
        """
        Create all queues for the complete prediction system.

        Returns:
            Dict mapping queue names to their configuration
        """
        print("\n" + "="*70)
        print("FOOTBALL PREDICTION SYSTEM - COMPLETE SQS INFRASTRUCTURE")
        print("="*70)
        print(f"Environment: {self.environment}")
        print(f"Region: {self.region}")
        print("="*70)

        all_queues = {}

        # 1. Fixture Predictions Queue (main entry point)
        print("\n[Queue 1/5] Fixture Predictions")
        all_queues['fixture_predictions'] = self.create_queue_with_dlq(
            queue_name='football-fixture-predictions',
            dlq_name='football-prediction-dlq',
            visibility_timeout=300,  # 5 minutes
            max_receive_count=2
        )

        # 2. League Parameter Updates Queue
        print("\n[Queue 2/5] League Parameter Updates")
        all_queues['league_parameters'] = self.create_queue_with_dlq(
            queue_name='football-league-parameter-updates',
            dlq_name='football-league-dlq',
            visibility_timeout=900,  # 15 minutes
            max_receive_count=3
        )

        # 3. Team Parameter Updates Queue
        print("\n[Queue 3/5] Team Parameter Updates")
        all_queues['team_parameters'] = self.create_queue_with_dlq(
            queue_name='football-team-parameter-updates',
            dlq_name='football-team-dlq',
            visibility_timeout=1200,  # 20 minutes
            max_receive_count=3
        )

        # 4. Cache Updates Queue
        print("\n[Queue 4/5] Cache Updates")
        all_queues['cache_updates'] = self.create_queue_with_dlq(
            queue_name='football-cache-updates',
            dlq_name='football-cache-dlq',
            visibility_timeout=120,  # 2 minutes
            max_receive_count=2
        )

        # 5. Match Results Queue
        print("\n[Queue 5/5] Match Results")
        all_queues['match_results'] = self.create_queue_with_dlq(
            queue_name='football-match-results',
            dlq_name='football-results-dlq',
            visibility_timeout=60,  # 1 minute
            max_receive_count=3
        )

        return all_queues

    def print_summary(self):
        """Print summary of created queues."""
        print("\n" + "="*70)
        print("QUEUE CREATION SUMMARY")
        print("="*70)

        if not self.created_queues:
            print("No queues created")
            return

        print(f"\nTotal Queues Created: {len(self.created_queues) * 2} (including DLQs)")
        print(f"Environment: {self.environment}")
        print(f"Region: {self.region}")

        for purpose, config in self.created_queues.items():
            print(f"\n{purpose.upper().replace('_', ' ')}:")
            print(f"  Main Queue:")
            print(f"    Name: {config['queue_name']}")
            print(f"    URL:  {config['queue_url']}")
            print(f"  Dead Letter Queue:")
            print(f"    Name: {config['dlq_name']}")
            print(f"    URL:  {config['dlq_url']}")

    def export_configuration(self, filename: str = 'queue_config.json'):
        """
        Export queue configuration to JSON file.

        Args:
            filename: Output filename
        """
        output = {
            'environment': self.environment,
            'region': self.region,
            'queues': self.created_queues
        }

        filepath = os.path.join(project_root, filename)
        with open(filepath, 'w') as f:
            json.dump(output, f, indent=2)

        print(f"\n✅ Configuration exported to: {filepath}")

    def update_constants_file(self):
        """Update constants.py with the fixture predictions queue URL."""
        if 'fixture_predictions' not in self.created_queues:
            print("\n⚠️  Fixture predictions queue not found, cannot update constants")
            return

        queue_url = self.created_queues['fixture_predictions']['queue_url']
        constants_file = os.path.join(project_root, 'src/utils/constants.py')

        try:
            with open(constants_file, 'r') as f:
                content = f.read()

            # Replace the queue URL
            import re
            pattern = r"FIXTURES_QUEUE_URL = '[^']*'"
            replacement = f"FIXTURES_QUEUE_URL = '{queue_url}'"

            if 'FIXTURES_QUEUE_URL' in content:
                new_content = re.sub(pattern, replacement, content)
                with open(constants_file, 'w') as f:
                    f.write(new_content)
                print(f"\n✅ Updated {constants_file}")
                print(f"   FIXTURES_QUEUE_URL = '{queue_url}'")
            else:
                print(f"\n⚠️  FIXTURES_QUEUE_URL not found in constants.py")
                print(f"   Please add: FIXTURES_QUEUE_URL = '{queue_url}'")

        except Exception as e:
            print(f"\n⚠️  Could not update constants file: {e}")
            print(f"   Please manually set: FIXTURES_QUEUE_URL = '{queue_url}'")


def main():
    """Main function for queue creation."""
    import argparse

    parser = argparse.ArgumentParser(
        description='Create complete SQS infrastructure for Football Prediction System'
    )
    parser.add_argument(
        '--environment', '-e',
        default=os.getenv('ENVIRONMENT', 'dev'),
        help='Environment (dev, staging, prod)'
    )
    parser.add_argument(
        '--region', '-r',
        default='eu-west-2',
        help='AWS region (default: eu-west-2)'
    )
    parser.add_argument(
        '--export', '-x',
        default='queue_config.json',
        help='Export configuration to file'
    )
    parser.add_argument(
        '--update-constants',
        action='store_true',
        help='Update constants.py with queue URLs'
    )

    args = parser.parse_args()

    print("\n" + "="*70)
    print("FOOTBALL PREDICTION SYSTEM - SQS QUEUE SETUP")
    print("="*70)
    print(f"Environment: {args.environment}")
    print(f"Region: {args.region}")
    print("="*70)

    # Create queue manager
    manager = SQSQueueManager(
        environment=args.environment,
        region=args.region
    )

    # Create all queues
    print("\nCreating all queues...")
    queues = manager.create_all_queues()

    # Print summary
    manager.print_summary()

    # Export configuration
    if args.export:
        manager.export_configuration(args.export)

    # Update constants file
    if args.update_constants:
        manager.update_constants_file()

    print("\n" + "="*70)
    print("SETUP COMPLETE")
    print("="*70)
    print("\nNext Steps:")
    print("1. Update Lambda environment variables with queue URLs")
    print("2. Grant Lambda permissions to access queues")
    print("3. Deploy Lambda functions")
    print("4. Test with manual invocations")
    print("5. Enable EventBridge triggers")
    print()

    return 0


if __name__ == '__main__':
    sys.exit(main())
