#!/usr/bin/env python3
"""
Trigger score update via SQS for October 1 - November 2, 2025.
Sends message to the checkScores SQS queue to trigger Lambda execution.
"""

import boto3
import json
from datetime import datetime

def main():
    """Send SQS message to trigger score update."""

    # Date range: October 1 - November 2, 2025
    start_date = datetime(2025, 10, 1, 0, 0, 0)
    end_date = datetime(2025, 11, 2, 23, 59, 59)

    start_timestamp = int(start_date.timestamp())
    end_timestamp = int(end_date.timestamp())

    print("=" * 80)
    print("TRIGGERING SCORE UPDATE VIA SQS")
    print("=" * 80)
    print(f"Date Range: {start_date} to {end_date}")
    print(f"Start Timestamp: {start_timestamp}")
    print(f"End Timestamp: {end_timestamp}")
    print(f"Duration: {(end_date - start_date).days} days")
    print("=" * 80)
    print()

    # Create SQS client
    sqs = boto3.client('sqs', region_name='us-east-1')

    # Get queue URL - try to find the checkScores queue
    try:
        # List queues to find the right one
        response = sqs.list_queues(QueueNamePrefix='checkScore')

        if 'QueueUrls' not in response or not response['QueueUrls']:
            print("❌ No queue found with prefix 'checkScore'")
            print("\nListing all available queues:")
            all_queues = sqs.list_queues()
            if 'QueueUrls' in all_queues:
                for url in all_queues['QueueUrls']:
                    queue_name = url.split('/')[-1]
                    print(f"  - {queue_name}")
            else:
                print("  No queues found")
            return

        queue_url = response['QueueUrls'][0]
        queue_name = queue_url.split('/')[-1]

        print(f"✓ Found queue: {queue_name}")
        print(f"  URL: {queue_url}")
        print()

    except Exception as e:
        print(f"❌ Error finding queue: {e}")
        return

    # Create message payload
    message_body = {
        "time_range": {
            "start": start_timestamp,
            "end": end_timestamp
        }
    }

    print("Sending message to SQS...")
    print(f"Payload: {json.dumps(message_body, indent=2)}")
    print()

    try:
        response = sqs.send_message(
            QueueUrl=queue_url,
            MessageBody=json.dumps(message_body)
        )

        print("=" * 80)
        print("✅ MESSAGE SENT SUCCESSFULLY")
        print("=" * 80)
        print(f"Message ID: {response['MessageId']}")
        print(f"Queue: {queue_name}")
        print()
        print("The checkScores Lambda will process this message and update scores")
        print("for all fixtures between October 1 and November 2, 2025.")
        print()
        print("Monitor CloudWatch Logs for the checkScores function to see progress.")
        print("=" * 80)

    except Exception as e:
        print(f"❌ Error sending message: {e}")


if __name__ == "__main__":
    main()
