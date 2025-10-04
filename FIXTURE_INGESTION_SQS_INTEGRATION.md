# Fixture Ingestion SQS Integration - Clarification

**Date**: October 4, 2025
**Status**: 📋 Integration Clarification

---

## SQS Queue Integration Status

### Current State

Based on the Event-Driven Prediction System Architecture document, here's the actual SQS integration:

#### Existing Queue (Currently Used)
- **Queue URL**: `https://sqs.eu-west-2.amazonaws.com/985019772236/fixturesQueue`
- **Queue Name**: `fixturesQueue` (legacy name)
- **Status**: ✅ **Already Exists** in AWS
- **Usage**: Referenced in `src/utils/constants.py`

#### Event-Driven Architecture Queue (Recommended)
- **Queue Name**: `football-fixture-predictions`
- **Purpose**: Daily fixture predictions with concurrent processing
- **Configuration**:
  - **Visibility Timeout**: 5 minutes
  - **Max Receive Count**: 2
  - **Dead Letter Queue**: `football-prediction-dlq`
  - **Batch Size**: 10 fixtures
- **Status**: 📋 **Defined but not yet deployed**

---

## Integration Point Analysis

### How Fixture Ingestion Handler Uses SQS

The fixture ingestion handler (`src/handlers/fixture_ingestion_handler.py`) integrates with SQS as follows:

#### 1. **Queue URL Source**
```python
from ..utils.constants import FIXTURES_QUEUE_URL

# In handler
sqs = boto3.client('sqs')
response = sqs.send_message(
    QueueUrl=FIXTURES_QUEUE_URL,  # From constants
    MessageBody=json.dumps(message_body),
    ...
)
```

#### 2. **Current Configuration**
From `src/utils/constants.py:88`:
```python
FIXTURES_QUEUE_URL = 'https://sqs.eu-west-2.amazonaws.com/985019772236/fixturesQueue'
```

This means:
- ✅ The queue **already exists** in AWS account `985019772236`
- ✅ The queue is in region `eu-west-2` (London)
- ✅ The fixture ingestion handler **can immediately send messages** to it
- ⚠️  However, it's using the **legacy queue name** (`fixturesQueue`) instead of the new event-driven architecture name (`football-fixture-predictions`)

---

## Recommended Actions

### Option 1: Use Existing Queue (Quick Start)

**Advantages:**
- ✅ No infrastructure changes needed
- ✅ Can deploy fixture ingestion handler immediately
- ✅ Queue already has proper permissions

**Steps:**
1. Deploy fixture ingestion handler
2. Test with existing queue
3. Verify prediction handler consumes messages correctly

**Code**: No changes needed - current implementation ready to use.

### Option 2: Migrate to Event-Driven Architecture Queue (Best Practice)

**Advantages:**
- ✅ Aligns with new event-driven architecture
- ✅ Proper Dead Letter Queue (DLQ) configuration
- ✅ Standardized naming convention
- ✅ Better monitoring and error handling

**Steps:**

#### 1. Create New Queue Infrastructure

```python
# src/infrastructure/create_sqs_queues.py
import boto3

def create_fixture_prediction_queue():
    """Create football-fixture-predictions queue per event-driven architecture."""
    sqs = boto3.client('sqs')

    # Step 1: Create DLQ
    dlq_response = sqs.create_queue(
        QueueName='football-prediction-dlq',
        Attributes={
            'MessageRetentionPeriod': '1209600',  # 14 days
        }
    )
    dlq_url = dlq_response['QueueUrl']

    # Get DLQ ARN
    dlq_attrs = sqs.get_queue_attributes(
        QueueUrl=dlq_url,
        AttributeNames=['QueueArn']
    )
    dlq_arn = dlq_attrs['Attributes']['QueueArn']

    # Step 2: Create main queue
    queue_response = sqs.create_queue(
        QueueName='football-fixture-predictions',
        Attributes={
            'VisibilityTimeout': '300',  # 5 minutes
            'MessageRetentionPeriod': '1209600',  # 14 days
            'ReceiveMessageWaitTimeSeconds': '20',  # Long polling
            'RedrivePolicy': json.dumps({
                'deadLetterTargetArn': dlq_arn,
                'maxReceiveCount': '2'
            })
        }
    )

    return queue_response['QueueUrl']
```

#### 2. Update Constants

```python
# src/utils/constants.py
# Update line 88 to use new queue
FIXTURES_QUEUE_URL = os.getenv(
    'FIXTURES_QUEUE_URL',
    'https://sqs.eu-west-2.amazonaws.com/985019772236/football-fixture-predictions'
)
```

#### 3. Update Prediction Handler

Ensure `src/handlers/prediction_handler.py` is configured to consume from the new queue.

### Option 3: Environment-Based Queue Selection (Most Flexible)

**Advantages:**
- ✅ Supports both legacy and new architecture
- ✅ Environment-specific queue names
- ✅ Easy testing and migration

**Implementation:**

```python
# src/utils/constants.py
import os

def _get_queue_url(base_queue_name: str) -> str:
    """
    Get environment-specific SQS queue URL.

    Priority:
    1. FIXTURES_QUEUE_URL environment variable (explicit override)
    2. Environment-based naming (TABLE_PREFIX/TABLE_SUFFIX)
    3. Default legacy queue URL
    """
    # Check for explicit override
    explicit_url = os.getenv('FIXTURES_QUEUE_URL')
    if explicit_url:
        return explicit_url

    # Use environment-based naming
    table_prefix = os.getenv('TABLE_PREFIX', '')
    table_suffix = os.getenv('TABLE_SUFFIX', '')

    if table_prefix or table_suffix:
        # Build queue name like tables
        parts = []
        if table_prefix:
            parts.append(table_prefix.rstrip('_'))
        parts.append(base_queue_name)
        if table_suffix:
            parts.append(table_suffix.lstrip('_'))
        queue_name = '_'.join(parts)
    else:
        queue_name = base_queue_name

    # Construct URL (assumes same account and region)
    account_id = '985019772236'  # From existing queue
    region = 'eu-west-2'
    return f'https://sqs.{region}.amazonaws.com/{account_id}/{queue_name}'

# Use the function
FIXTURES_QUEUE_URL = _get_queue_url('fixturesQueue')
```

---

## Complete Queue Architecture

According to the Event-Driven Architecture document, there are **5 main queues**:

| Queue Name | Purpose | Visibility Timeout | Max Receive | DLQ | Status |
|------------|---------|-------------------|-------------|-----|---------|
| `football-league-parameter-updates` | League parameter computation | 15 min | 3 | `football-league-dlq` | 📋 To create |
| `football-team-parameter-updates` | Team parameter computation | 20 min | 3 | `football-team-dlq` | 📋 To create |
| `football-fixture-predictions` | Daily fixture predictions | 5 min | 2 | `football-prediction-dlq` | 📋 To create |
| `football-cache-updates` | Cache refresh operations | 2 min | 2 | `football-cache-dlq` | 📋 To create |
| `football-match-results` | Match result processing | 1 min | 3 | `football-results-dlq` | 📋 To create |

**Legacy Queue:**
| Queue Name | Status |
|------------|--------|
| `fixturesQueue` | ✅ Exists (currently used) |

---

## Recommended Implementation Path

### Phase 1: Quick Start (Immediate)
1. ✅ Use existing `fixturesQueue`
2. ✅ Deploy fixture ingestion handler
3. ✅ Verify integration with prediction handler

### Phase 2: Event-Driven Migration (Week 2-3)
1. Create all 5 new queues + DLQs per architecture document
2. Update constants to use new queue names
3. Migrate prediction handler to new queue
4. Test end-to-end flow
5. Decommission legacy `fixturesQueue`

### Phase 3: Environment Isolation (Month 2)
1. Implement environment-based queue naming
2. Support dev/staging/prod queue separation
3. Add queue creation to deployment scripts
4. Document queue management procedures

---

## Current Implementation Status

### What's Ready ✅
- ✅ Fixture ingestion handler code complete
- ✅ SQS integration implemented
- ✅ Message formatting compatible with prediction handler
- ✅ Error handling and retry logic
- ✅ Queue URL configured in constants

### What Exists in AWS ✅
- ✅ Legacy queue `fixturesQueue` operational
- ✅ Queue has proper permissions
- ✅ Queue accessible from account 985019772236

### What's Missing 📋
- 📋 Event-driven architecture queues not yet created
- 📋 Dead Letter Queues (DLQs) not configured
- 📋 Queue creation automation script
- 📋 Environment-based queue naming

### What to Do Next

**For Immediate Deployment:**
```bash
# 1. The queue already exists - no creation needed!
# 2. Just deploy the fixture ingestion handler
aws lambda update-function-code \
  --function-name football-fixture-ingestion \
  --zip-file fileb://deployment-package.zip

# 3. Set environment variable (already configured in constants.py)
aws lambda update-function-configuration \
  --function-name football-fixture-ingestion \
  --environment Variables="{
    RAPIDAPI_KEY=your_key,
    FIXTURES_QUEUE_URL=https://sqs.eu-west-2.amazonaws.com/985019772236/fixturesQueue
  }"

# 4. Test
aws lambda invoke \
  --function-name football-fixture-ingestion \
  --payload '{"trigger_type":"manual_test"}' \
  response.json
```

**For Event-Driven Architecture Migration:**
```bash
# Run the queue creation script (to be created)
python3 -m src.infrastructure.create_all_sqs_queues --environment prod

# This will create:
# - football-fixture-predictions
# - football-prediction-dlq
# - (and 4 other queue pairs)
```

---

## Summary

### The Key Answer to Your Question:

**"How was SQS integrated to the ingestion code?"**

1. **The queue ALREADY EXISTS** in AWS (legacy queue `fixturesQueue`)
2. **The URL is hardcoded** in `src/utils/constants.py:88`
3. **The fixture ingestion handler** uses this constant via import
4. **No queue creation needed** for immediate deployment
5. **Event-driven architecture** recommends NEW queues (not yet created)

### Integration Flow:
```
fixture_ingestion_handler.py
    ↓ (imports)
constants.py (FIXTURES_QUEUE_URL)
    ↓ (uses)
boto3.client('sqs').send_message(QueueUrl=FIXTURES_QUEUE_URL, ...)
    ↓ (sends to)
AWS SQS: fixturesQueue (ALREADY EXISTS)
    ↓ (consumed by)
prediction_handler.py (EXISTING)
```

### Current State:
- ✅ **Ready to deploy** - No infrastructure changes needed
- ✅ **Queue exists** - Can send messages immediately
- ⚠️  **Future work** - Migrate to event-driven architecture queues

---

**Status**: Fixture ingestion handler ready for deployment using existing SQS queue.
**Next Action**: Deploy handler and test with existing queue, then plan migration to event-driven architecture queues.
