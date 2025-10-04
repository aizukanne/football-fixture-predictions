# Environment Configuration Guide

## Overview

The Football Fixture Prediction System supports environment-based table isolation, allowing multiple independent deployments to coexist in the same AWS account without table name conflicts. This is essential for:

- **Multi-environment deployments** (dev, staging, prod)
- **Multi-tenant applications** (separate instances per customer)
- **Testing and CI/CD pipelines** (isolated test environments)
- **Team collaboration** (individual developer sandboxes)

## Table Naming Strategy

### Base Table Names

The system uses the following base table names:

| Base Name | Purpose | TTL |
|-----------|---------|-----|
| `game_fixtures` | Fixture predictions and results | None |
| `league_parameters` | League-level statistics | None |
| `team_parameters` | Team-level statistics | None |
| `venue_cache` | Venue/stadium data cache | 7 days |
| `tactical_cache` | Tactical analysis cache | 48 hours |
| `league_standings_cache` | League standings cache | 24 hours |

### Environment-Based Naming

Table names are generated using the pattern:

```
{TABLE_PREFIX}{base_name}{TABLE_SUFFIX}
```

**Examples:**

| Prefix | Base Name | Suffix | Result |
|--------|-----------|--------|--------|
| (none) | `game_fixtures` | (none) | `game_fixtures` |
| `myapp_` | `game_fixtures` | (none) | `myapp_game_fixtures` |
| (none) | `game_fixtures` | `_prod` | `game_fixtures_prod` |
| `myapp_` | `game_fixtures` | `_prod` | `myapp_game_fixtures_prod` |
| `dev_john_` | `venue_cache` | `_test` | `dev_john_venue_cache_test` |

## Environment Variables

### Required Variables

#### `ENVIRONMENT`
- **Purpose**: Identifies the deployment environment
- **Default**: `dev`
- **Valid values**: `dev`, `staging`, `prod`, or any custom identifier
- **Example**: `ENVIRONMENT=prod`

#### `TABLE_PREFIX`
- **Purpose**: Prefix added to all table names
- **Default**: (empty string)
- **Format**: Any alphanumeric string (trailing underscore optional)
- **Example**: `TABLE_PREFIX=myapp_`
- **Use cases**:
  - Multi-tenant deployments: `TABLE_PREFIX=customer1_`
  - Application namespacing: `TABLE_PREFIX=football_`
  - Team identification: `TABLE_PREFIX=team_alpha_`

#### `TABLE_SUFFIX`
- **Purpose**: Suffix added to all table names
- **Default**: (empty string)
- **Format**: Any alphanumeric string (leading underscore optional)
- **Example**: `TABLE_SUFFIX=_prod`
- **Use cases**:
  - Environment differentiation: `TABLE_SUFFIX=_staging`
  - Version tagging: `TABLE_SUFFIX=_v2`
  - Geographic regions: `TABLE_SUFFIX=_eu_west_1`

## Configuration Examples

### Development Environment

**Single developer:**
```bash
export ENVIRONMENT=dev
export TABLE_PREFIX=""
export TABLE_SUFFIX=""
```

**Result:** `game_fixtures`, `venue_cache`, etc.

**Multiple developers (isolated sandboxes):**
```bash
export ENVIRONMENT=dev
export TABLE_PREFIX="dev_john_"
export TABLE_SUFFIX=""
```

**Result:** `dev_john_game_fixtures`, `dev_john_venue_cache`, etc.

### Staging Environment

```bash
export ENVIRONMENT=staging
export TABLE_PREFIX="myapp_"
export TABLE_SUFFIX="_staging"
```

**Result:** `myapp_game_fixtures_staging`, `myapp_venue_cache_staging`, etc.

### Production Environment

```bash
export ENVIRONMENT=prod
export TABLE_PREFIX="myapp_"
export TABLE_SUFFIX="_prod"
```

**Result:** `myapp_game_fixtures_prod`, `myapp_venue_cache_prod`, etc.

### Multi-Tenant Deployment

**Customer 1:**
```bash
export ENVIRONMENT=prod
export TABLE_PREFIX="customer1_"
export TABLE_SUFFIX="_prod"
```

**Result:** `customer1_game_fixtures_prod`, `customer1_venue_cache_prod`, etc.

**Customer 2:**
```bash
export ENVIRONMENT=prod
export TABLE_PREFIX="customer2_"
export TABLE_SUFFIX="_prod"
```

**Result:** `customer2_game_fixtures_prod`, `customer2_venue_cache_prod`, etc.

### CI/CD Testing

**GitHub Actions PR #123:**
```bash
export ENVIRONMENT=ci
export TABLE_PREFIX="ci_"
export TABLE_SUFFIX="_pr123"
```

**Result:** `ci_game_fixtures_pr123`, `ci_venue_cache_pr123`, etc.

## Deployment

### Interactive Deployment

Run the deployment script in interactive mode:

```bash
python -m src.infrastructure.deploy_tables
```

The script will:
1. Display current environment variables
2. Prompt for changes (optional)
3. Show table names that will be created
4. Ask for confirmation
5. Deploy all tables
6. Verify deployment

### Automated Deployment

Set environment variables and run non-interactively:

```bash
# Set environment variables
export TABLE_PREFIX="myapp_"
export TABLE_SUFFIX="_prod"
export ENVIRONMENT=prod

# Deploy tables
python -m src.infrastructure.deploy_tables --no-interactive
```

### Dry Run (Test Mode)

Preview table names without creating tables:

```bash
TABLE_PREFIX=myapp_ TABLE_SUFFIX=_prod python -m src.infrastructure.deploy_tables --dry-run
```

### Verify Existing Deployment

Check status of deployed tables:

```bash
python -m src.infrastructure.deploy_tables --verify-only
```

## AWS Lambda Configuration

### Setting Environment Variables

When deploying to AWS Lambda, configure environment variables through:

#### AWS Console
1. Open Lambda function
2. Configuration → Environment variables
3. Add variables:
   - `ENVIRONMENT`: `prod`
   - `TABLE_PREFIX`: `myapp_`
   - `TABLE_SUFFIX`: `_prod`

#### AWS CLI
```bash
aws lambda update-function-configuration \
  --function-name football-fixture-prediction \
  --environment Variables="{
    ENVIRONMENT=prod,
    TABLE_PREFIX=myapp_,
    TABLE_SUFFIX=_prod
  }"
```

#### CloudFormation / SAM
```yaml
Resources:
  PredictionFunction:
    Type: AWS::Lambda::Function
    Properties:
      Environment:
        Variables:
          ENVIRONMENT: prod
          TABLE_PREFIX: myapp_
          TABLE_SUFFIX: _prod
```

#### Terraform
```hcl
resource "aws_lambda_function" "prediction_function" {
  environment {
    variables = {
      ENVIRONMENT  = "prod"
      TABLE_PREFIX = "myapp_"
      TABLE_SUFFIX = "_prod"
    }
  }
}
```

## IAM Permissions

### DynamoDB Permissions

Lambda execution role needs permissions for environment-specific tables:

#### Option 1: Wildcard Permissions (Recommended for flexibility)
```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "dynamodb:PutItem",
        "dynamodb:GetItem",
        "dynamodb:UpdateItem",
        "dynamodb:DeleteItem",
        "dynamodb:Query",
        "dynamodb:Scan"
      ],
      "Resource": [
        "arn:aws:dynamodb:*:*:table/*game_fixtures*",
        "arn:aws:dynamodb:*:*:table/*league_parameters*",
        "arn:aws:dynamodb:*:*:table/*team_parameters*",
        "arn:aws:dynamodb:*:*:table/*venue_cache*",
        "arn:aws:dynamodb:*:*:table/*tactical_cache*",
        "arn:aws:dynamodb:*:*:table/*league_standings_cache*"
      ]
    }
  ]
}
```

#### Option 2: Explicit Table Names (Most secure)
```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "dynamodb:PutItem",
        "dynamodb:GetItem",
        "dynamodb:UpdateItem",
        "dynamodb:DeleteItem",
        "dynamodb:Query",
        "dynamodb:Scan"
      ],
      "Resource": [
        "arn:aws:dynamodb:eu-west-2:123456789012:table/myapp_game_fixtures_prod",
        "arn:aws:dynamodb:eu-west-2:123456789012:table/myapp_league_parameters_prod",
        "arn:aws:dynamodb:eu-west-2:123456789012:table/myapp_team_parameters_prod",
        "arn:aws:dynamodb:eu-west-2:123456789012:table/myapp_venue_cache_prod",
        "arn:aws:dynamodb:eu-west-2:123456789012:table/myapp_tactical_cache_prod",
        "arn:aws:dynamodb:eu-west-2:123456789012:table/myapp_league_standings_cache_prod"
      ]
    }
  ]
}
```

## Verification

### Check Table Configuration

Use the built-in configuration checker:

```python
from src.utils.constants import get_table_config

config = get_table_config()
print(f"Environment: {config['environment']}")
print(f"Prefix: '{config['prefix']}'")
print(f"Suffix: '{config['suffix']}'")
print("\nTable Mappings:")
for base, full in config['tables'].items():
    print(f"  {base:30s} -> {full}")
```

**Example output:**
```
Environment: prod
Prefix: 'myapp_'
Suffix: '_prod'

Table Mappings:
  game_fixtures                  -> myapp_game_fixtures_prod
  league_parameters              -> myapp_league_parameters_prod
  team_parameters                -> myapp_team_parameters_prod
  venue_cache                    -> myapp_venue_cache_prod
  tactical_cache                 -> myapp_tactical_cache_prod
  league_standings_cache         -> myapp_league_standings_cache_prod
```

### Test Table Access

Create a test script to verify table accessibility:

```python
import boto3
from src.utils.constants import _get_table_name

dynamodb = boto3.resource('dynamodb')

# Test each table
tables = [
    'game_fixtures',
    'league_parameters',
    'team_parameters',
    'venue_cache',
    'tactical_cache',
    'league_standings_cache'
]

for base_name in tables:
    table_name = _get_table_name(base_name)
    try:
        table = dynamodb.Table(table_name)
        table.load()
        print(f"✅ {base_name:30s} -> {table_name} (Status: {table.table_status})")
    except Exception as e:
        print(f"❌ {base_name:30s} -> {table_name} (Error: {e})")
```

## Troubleshooting

### Issue: Tables Not Found

**Symptoms:**
- `ResourceNotFoundException` errors
- Application cannot read/write to tables

**Solutions:**
1. Verify environment variables are set correctly:
   ```bash
   echo $TABLE_PREFIX
   echo $TABLE_SUFFIX
   echo $ENVIRONMENT
   ```

2. Check table configuration:
   ```python
   from src.utils.constants import get_table_config
   print(get_table_config())
   ```

3. List actual tables in AWS:
   ```bash
   aws dynamodb list-tables
   ```

4. Compare expected vs actual table names

### Issue: Permission Denied

**Symptoms:**
- `AccessDeniedException` errors
- Cannot create/access tables

**Solutions:**
1. Verify IAM role has correct permissions
2. Check table ARNs match deployed tables
3. Ensure Lambda execution role is properly configured
4. Test with AWS CLI:
   ```bash
   aws dynamodb describe-table --table-name myapp_game_fixtures_prod
   ```

### Issue: Tables Exist in Wrong Environment

**Symptoms:**
- Tables deployed with unexpected names
- Multiple versions of same table

**Solutions:**
1. Delete incorrectly named tables (CAREFUL!):
   ```bash
   aws dynamodb delete-table --table-name wrong_table_name
   ```

2. Set correct environment variables
3. Re-run deployment:
   ```bash
   python -m src.infrastructure.deploy_tables
   ```

### Issue: Different Environments Conflicting

**Symptoms:**
- Dev environment affecting prod data
- Test data appearing in production

**Solutions:**
1. Ensure each environment has unique prefix/suffix
2. Use separate AWS accounts for prod vs non-prod
3. Implement strict IAM policies preventing cross-environment access
4. Add environment validation in application code:
   ```python
   from src.utils.constants import ENVIRONMENT

   if ENVIRONMENT == 'prod':
       # Extra validation for production
       assert TABLE_PREFIX.endswith('prod') or TABLE_SUFFIX.endswith('prod')
   ```

## Best Practices

### 1. Environment Naming Conventions

Use consistent naming patterns:
- **Development**: `dev`, `development`, `dev_{developer_name}`
- **Staging**: `staging`, `stage`, `uat`
- **Production**: `prod`, `production`
- **Testing**: `test`, `ci`, `test_{pr_number}`

### 2. Prefix/Suffix Strategy

Choose one strategy and stick to it:

**Option A: Suffix-based (Recommended)**
- Prefix: Application identifier (e.g., `myapp_`)
- Suffix: Environment (e.g., `_prod`, `_staging`)
- Example: `myapp_game_fixtures_prod`

**Option B: Prefix-based**
- Prefix: Environment + Application (e.g., `prod_myapp_`)
- Suffix: (none)
- Example: `prod_myapp_game_fixtures`

**Option C: Both (Multi-tenant)**
- Prefix: Customer identifier (e.g., `customer1_`)
- Suffix: Environment (e.g., `_prod`)
- Example: `customer1_game_fixtures_prod`

### 3. Documentation

Document your naming convention:
```markdown
# Project Table Naming Convention

- Development: `dev_{developer}_*`
- Staging: `myapp_*_staging`
- Production: `myapp_*_prod`

Examples:
- dev_john_game_fixtures
- myapp_game_fixtures_staging
- myapp_game_fixtures_prod
```

### 4. Automated Cleanup

Set up automated cleanup for temporary environments:
```bash
# Delete all tables for CI environment
aws dynamodb list-tables \
  --query "TableNames[?starts_with(@, 'ci_') && ends_with(@, '_pr123')]" \
  --output text | xargs -I {} aws dynamodb delete-table --table-name {}
```

### 5. Monitoring

Monitor table usage per environment:
- CloudWatch metrics filtered by table name
- Cost allocation tags (added during table creation)
- Usage alerts per environment

### 6. Security

- Use separate AWS accounts for production
- Implement least-privilege IAM policies
- Enable CloudTrail logging for all table access
- Regular audit of table access patterns
- Encrypt sensitive environments (staging, prod) with KMS

## Migration Guide

### Migrating Existing Deployment

If you have existing tables without environment-based naming:

#### Step 1: Backup Existing Data
```bash
# Export existing table data
aws dynamodb scan --table-name game_fixtures --output json > game_fixtures_backup.json
# Repeat for all tables
```

#### Step 2: Deploy New Tables
```bash
export TABLE_PREFIX="myapp_"
export TABLE_SUFFIX="_prod"
export ENVIRONMENT=prod

python -m src.infrastructure.deploy_tables
```

#### Step 3: Migrate Data
```python
import boto3
import json

dynamodb = boto3.resource('dynamodb')

# Load backup
with open('game_fixtures_backup.json') as f:
    data = json.load(f)

# Write to new table
new_table = dynamodb.Table('myapp_game_fixtures_prod')
for item in data['Items']:
    new_table.put_item(Item=item)
```

#### Step 4: Update Application
Update Lambda environment variables to use new table names.

#### Step 5: Verify
Test application with new tables.

#### Step 6: Delete Old Tables
```bash
aws dynamodb delete-table --table-name game_fixtures
# Repeat for all old tables
```

## Summary

Environment-based table isolation provides:

✅ **Isolation**: Multiple environments without conflicts
✅ **Flexibility**: Support for dev, staging, prod, multi-tenant
✅ **Safety**: Prevent accidental cross-environment data access
✅ **Scalability**: Easy to add new environments
✅ **Cost tracking**: Environment-based cost allocation
✅ **CI/CD friendly**: Automated test environment creation/teardown

For questions or issues, refer to the [main documentation](../README.md) or [deployment guide](DEPLOYMENT_GUIDE.md).
