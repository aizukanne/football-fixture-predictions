# Football Fixture Prediction System v6.0

**Advanced Football Match Outcome Prediction System**

[![Deployment Status](https://img.shields.io/badge/Deployment-Complete-success)](docs/deployment/DEPLOYMENT_COMPLETE_SUMMARY.md)
[![AWS Region](https://img.shields.io/badge/AWS-eu--west--2-orange)](https://aws.amazon.com/about-aws/global-infrastructure/regions_az/)
[![Python](https://img.shields.io/badge/Python-3.13-blue)](https://www.python.org/)
[![System Status](https://img.shields.io/badge/Status-Operational-brightgreen)](docs/guides/OPERATIONAL_WORKFLOW_GUIDE.md)

---

## 🎯 System Overview

A sophisticated machine learning system for predicting football match outcomes using a 6-phase advanced prediction model deployed on AWS Lambda.

### Key Features

- **6-Phase Prediction Model:**
  1. Core Statistical Engine (Poisson distribution)
  2. Opponent Stratification (Smart vs Dumb teams)
  3. Home/Away Venue Analysis
  4. Temporal Evolution Tracking
  5. Tactical Intelligence (formations, managers)
  6. Adaptive Strategy Selection & Confidence Calibration

- **AWS Serverless Architecture:**
  - 5 Lambda Functions (Python 3.13)
  - 6 DynamoDB Tables
  - 10 SQS Queues (with DLQs)
  - Event-driven workflow

- **Production-Ready:**
  - Multi-environment support
  - Comprehensive error handling
  - CloudWatch monitoring
  - Automated parameter updates

---

## 🚀 Quick Start

### Using the Deployed System

**Step 1: Initialize League Parameters**
```bash
aws lambda invoke \
    --function-name football-league-parameter-handler-prod \
    --payload '{"league_id": 39, "season": 2024}' \
    --region eu-west-2 \
    response.json
```

**Step 2: Initialize Team Parameters**
```bash
aws sqs send-message \
    --queue-url https://sqs.eu-west-2.amazonaws.com/985019772236/football_football-team-parameter-updates_prod \
    --message-body '{"action": "update_league_teams", "league_id": 39, "season": 2024}' \
    --region eu-west-2
```

**Step 3: Ingest Fixtures & Generate Predictions**
```bash
aws lambda invoke \
    --function-name football-fixture-ingestion-prod \
    --payload '{"action": "fetch_today"}' \
    --region eu-west-2 \
    response.json
```

📖 **For complete instructions:** [Operational Workflow Guide](docs/guides/OPERATIONAL_WORKFLOW_GUIDE.md)

---

## 📚 Documentation

### Quick Links

**Getting Started:**
- [Operational Workflow Guide](docs/guides/OPERATIONAL_WORKFLOW_GUIDE.md) ⭐ **START HERE**
- [Quick Start Deployment](docs/guides/QUICK_START_DEPLOYMENT.md)
- [API Documentation](docs/guides/API_DOCUMENTATION.md)

**Deployment:**
- [Deployment Complete Summary](docs/deployment/DEPLOYMENT_COMPLETE_SUMMARY.md)
- [Deployment Guide](docs/deployment/DEPLOYMENT_GUIDE.md)
- [Environment Configuration](docs/deployment/ENVIRONMENT_CONFIGURATION.md)

**Architecture:**
- [Event-Driven System Architecture](docs/architecture/EVENT_DRIVEN_PREDICTION_SYSTEM_ARCHITECTURE.md)
- [Implementation Guide](docs/architecture/Implementation%20Guide/)
- [Table Isolation Guide](docs/architecture/TABLE_ISOLATION_IMPLEMENTATION_GUIDE.md)

**📂 Browse all documentation:** [docs/README.md](docs/README.md)

---

## 🏗️ System Architecture

```
┌──────────────────────────────────────────────────────────────┐
│                  AWS Production Environment                  │
│                      eu-west-2 Region                        │
├──────────────────────────────────────────────────────────────┤
│                                                              │
│  Lambda Functions (Python 3.13 + scipy-layer)               │
│  ├─ API Service              (Query predictions)            │
│  ├─ Fixture Ingestion        (Daily retrieval)              │
│  ├─ Prediction Handler       (Generate predictions)         │
│  ├─ League Parameter Handler (Weekly updates)               │
│  └─ Team Parameter Handler   (Weekly updates)               │
│                                                              │
│  DynamoDB Tables (6)                                         │
│  ├─ game_fixtures_prod       (Predictions)                  │
│  ├─ league_parameters_prod   (League stats)                 │
│  ├─ team_parameters_prod     (Team stats)                   │
│  └─ [3 cache tables with TTL]                               │
│                                                              │
│  SQS Queues (5 main + 5 DLQs)                               │
│  ├─ fixture-predictions      (Prediction requests)          │
│  ├─ league-parameter-updates (League computations)          │
│  ├─ team-parameter-updates   (Team computations)            │
│  └─ [2 additional queues]                                   │
│                                                              │
└──────────────────────────────────────────────────────────────┘
```

---

## 💡 How It Works

### Execution Order (CRITICAL)

The system **MUST** be initialized in this specific order:

```
1. League Parameter Handler  → Calculate league baselines
   ↓
2. Team Parameter Handler    → Calculate team strengths
   ↓
3. Fixture Ingestion        → Retrieve upcoming matches
   ↓
4. Prediction Handler       → Generate predictions (AUTOMATIC)
   ↓
5. API Service             → Query predictions
```

**Why this order?**
- League parameters provide the baseline statistics
- Team parameters calculate relative strengths using league context
- Predictions combine both with fixture details

📖 **Detailed workflow:** [Operational Workflow Guide](docs/guides/OPERATIONAL_WORKFLOW_GUIDE.md)

---

## 🔧 Configuration

### AWS Resources
- **Account:** 985019772236
- **Region:** eu-west-2 (Europe - London)
- **IAM Role:** FootballPredictionLambdaRole
- **Lambda Layer:** scipy-layer:4 (numpy, pandas, scipy, scikit-learn)

### Environment Variables
```bash
AWS_DEFAULT_REGION=eu-west-2
ENVIRONMENT=prod
TABLE_PREFIX=football_
TABLE_SUFFIX=_prod
```

Load with:
```bash
source setup_deployment_env.sh
```

---

## 📊 System Status

| Component | Count | Status |
|-----------|-------|--------|
| Lambda Functions | 5 | ✅ Deployed |
| DynamoDB Tables | 6 | ✅ Active |
| SQS Queues | 10 | ✅ Active |
| Deployment | 100% | ✅ Complete |

**Last Deployed:** 2025-10-05  
**System Version:** v6.0  
**Deployment Status:** 🟢 Fully Operational

---

## 🧪 Testing

### Run Tests
```bash
# System integration tests
python3 tests/test_complete_system_integration.py

# Phase-specific tests
python3 tests/test_phase4_tactical_intelligence.py
python3 tests/test_phase5_adaptive_strategy.py
python3 tests/test_phase6_confidence_calibration.py
```

### Production Readiness Check
```bash
python3 tests/production_readiness_check.py
```

---

## 📈 Monitoring

### CloudWatch Logs
```bash
# View API Service logs
aws logs tail /aws/lambda/football-api-service-prod --follow --region eu-west-2

# View Prediction Handler logs
aws logs tail /aws/lambda/football-prediction-handler-prod --follow --region eu-west-2
```

### Check System Health
```bash
# List all deployed functions
aws lambda list-functions --region eu-west-2 \
    --query "Functions[?contains(FunctionName, 'football')].FunctionName"

# Check SQS queue depths
aws sqs get-queue-attributes \
    --queue-url https://sqs.eu-west-2.amazonaws.com/985019772236/football_football-fixture-predictions_prod \
    --attribute-names ApproximateNumberOfMessages \
    --region eu-west-2
```

---

## 💰 Cost Estimate

**Monthly Operational Cost:** ~$7-16

| Service | Monthly Cost |
|---------|--------------|
| DynamoDB (On-Demand) | $5-10 |
| Lambda (50K invocations) | $0.20 |
| SQS (100K requests) | $0.04 |
| CloudWatch (Logs + metrics) | $2-5 |

---

## 🔐 Security

- ✅ IAM least-privilege permissions
- ✅ Environment-based resource isolation
- ✅ Credentials not in version control
- ✅ DynamoDB encryption at rest
- ✅ CloudWatch logging enabled
- ✅ SQS Dead Letter Queues for error handling

---

## 📞 Support & Documentation

**Main Documentation:** [docs/README.md](docs/README.md)

**Quick Access:**
- [How to Use](docs/guides/OPERATIONAL_WORKFLOW_GUIDE.md) - Step-by-step operational guide
- [API Reference](docs/guides/API_DOCUMENTATION.md) - API endpoints and usage
- [Deployment Status](docs/deployment/DEPLOYMENT_COMPLETE_SUMMARY.md) - Current deployment state
- [Troubleshooting](docs/guides/OPERATIONAL_WORKFLOW_GUIDE.md#troubleshooting) - Common issues

**Project Structure:**
```
├── docs/                    # All documentation
│   ├── guides/             # User guides and API docs
│   ├── deployment/         # Deployment guides and configs
│   ├── architecture/       # System design and implementation
│   └── reports/            # Test reports and validation
├── src/                    # Source code
│   ├── handlers/           # Lambda function handlers
│   ├── parameters/         # Parameter calculators
│   ├── prediction/         # Prediction engine
│   ├── features/           # Feature extractors
│   └── data/              # Data access layer
├── scripts/               # Deployment scripts
└── tests/                 # Test suites
```

---

## 📄 License

[LICENSE](LICENSE)

---

## 🙏 Acknowledgments

- **API-Football** - Match data provider
- **AWS Lambda** - Serverless compute platform
- **Python Scientific Stack** - numpy, pandas, scipy, scikit-learn

---

**System Status:** 🟢 **OPERATIONAL**  
**Documentation:** 📚 **COMPLETE**  
**Deployment:** ✅ **PRODUCTION READY**

For detailed operational instructions, see the [Operational Workflow Guide](docs/guides/OPERATIONAL_WORKFLOW_GUIDE.md).
