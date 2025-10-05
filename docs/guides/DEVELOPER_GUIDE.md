# Developer Guide
**Football Fixture Prediction System - Development Documentation**

Version: 6.0 | Last Updated: October 4, 2025

---

## Table of Contents

1. [Development Setup](#development-setup)
2. [Project Structure](#project-structure)
3. [Architecture](#architecture)
4. [Adding New Features](#adding-new-features)
5. [Testing](#testing)
6. [Code Style](#code-style)
7. [Contributing](#contributing)
8. [Common Tasks](#common-tasks)

---

## Development Setup

### Prerequisites

- Python 3.8 or higher
- Git
- AWS CLI (for DynamoDB access)
- RapidAPI account with API-Football subscription

### Initial Setup

```bash
# Clone the repository
git clone https://github.com/yourusername/football-fixture-predictions.git
cd football-fixture-predictions

# Create virtual environment
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
pip install -r requirements-dev.txt

# Set up environment variables
cp .env.example .env
# Edit .env with your API keys

# Verify installation
python3 -m pytest tests/ -v
```

### IDE Setup

**VS Code (Recommended)**

Install extensions:
- Python
- Pylance
- Python Test Explorer

**.vscode/settings.json:**
```json
{
    "python.linting.enabled": true,
    "python.linting.pylintEnabled": true,
    "python.formatting.provider": "black",
    "python.testing.pytestEnabled": true,
    "python.testing.unittestEnabled": false,
    "editor.formatOnSave": true,
    "editor.rulers": [100]
}
```

**PyCharm**

1. Open project
2. Configure Python interpreter (Python 3.8+)
3. Enable pytest as test runner
4. Configure pylint as code inspector

---

## Project Structure

```
football-fixture-predictions/
├── src/                        # Source code
│   ├── analytics/              # Performance analytics
│   │   ├── accuracy_tracker.py
│   │   ├── confidence_calibrator.py
│   │   └── performance_dashboard.py
│   ├── data/                   # Data access layer
│   │   ├── api_client.py       # External API integration
│   │   ├── database_client.py  # Database operations
│   │   └── tactical_data_collector.py
│   ├── features/               # Feature extraction
│   │   ├── opponent_classifier.py     # Phase 1
│   │   ├── venue_analyzer.py          # Phase 2
│   │   ├── form_analyzer.py           # Phase 3
│   │   ├── tactical_analyzer.py       # Phase 4
│   │   ├── manager_analyzer.py        # Phase 4
│   │   ├── team_classifier.py         # Phase 5
│   │   └── strategy_router.py         # Phase 5
│   ├── infrastructure/         # System infrastructure
│   │   ├── version_manager.py
│   │   └── transition_manager.py
│   ├── parameters/             # Parameter calculation
│   │   ├── team_calculator.py
│   │   ├── league_calculator.py
│   │   └── multiplier_calculator.py
│   ├── prediction/             # Prediction engine
│   │   └── prediction_engine.py
│   ├── reporting/              # Reporting & insights
│   │   └── executive_reports.py
│   ├── statistics/             # Statistical models
│   │   ├── distributions.py
│   │   ├── bayesian.py
│   │   └── optimization.py
│   └── utils/                  # Utilities
│       ├── constants.py
│       ├── converters.py
│       └── geographic.py
├── tests/                      # Test suite
├── docs/                       # Documentation
├── Implementation Guide/       # Phase implementation guides
└── README.md

### Module Responsibilities

| Module | Responsibility | Key Classes |
|--------|---------------|-------------|
| **data** | External data access | APIClient, DatabaseClient |
| **features** | Feature extraction | Analyzers (Venue, Tactical, etc.) |
| **infrastructure** | System management | VersionManager, TransitionManager |
| **parameters** | Param calculation | team_calculator, league_calculator |
| **prediction** | Core predictions | prediction_engine |
| **statistics** | Statistical models | Bayesian, distributions |
| **analytics** | Performance tracking | ConfidenceCalibrator, AccuracyTracker |

---

## Architecture

### 6-Phase Architecture

```
Phase 0: Version Tracking
    ↓
Phase 1: Opponent Stratification
    ↓
Phase 2: Venue Analysis
    ↓
Phase 3: Temporal Evolution
    ↓
Phase 4: Tactical Intelligence
    ↓
Phase 5: Adaptive Strategy
    ↓
Phase 6: Confidence Calibration
    ↓
Final Prediction
```

### Data Flow

```
User Request
    ↓
prediction_engine.py
    ↓
├── team_calculator.py (get parameters)
│   ├── opponent_classifier.py
│   ├── venue_analyzer.py
│   ├── form_analyzer.py
│   └── tactical_analyzer.py
│       └── manager_analyzer.py
├── team_classifier.py (classify team)
├── strategy_router.py (route strategy)
│   └── archetype_analyzer.py
└── confidence_calibrator.py
    ↓
Response
```

### Design Patterns

**1. Strategy Pattern** - `strategy_router.py`
```python
# Different prediction strategies based on context
strategies = {
    'standard_with_quality_boost': StandardStrategy,
    'formation_heavy_weighting': TacticalStrategy,
    'temporal_heavy_weighting': TemporalStrategy
}
```

**2. Factory Pattern** - Analyzers
```python
# Create appropriate analyzer based on type
def get_analyzer(analyzer_type):
    analyzers = {
        'venue': VenueAnalyzer,
        'tactical': TacticalAnalyzer,
        'form': FormAnalyzer
    }
    return analyzers[analyzer_type]()
```

**3. Singleton Pattern** - Version Manager
```python
class VersionManager:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
```

**4. Decorator Pattern** - Caching
```python
def cache_result(ttl_seconds):
    def decorator(func):
        cache = {}
        def wrapper(*args, **kwargs):
            key = (args, frozenset(kwargs.items()))
            if key in cache:
                return cache[key]
            result = func(*args, **kwargs)
            cache[key] = result
            return result
        return wrapper
    return decorator
```

---

## Adding New Features

### Adding a New Analyzer

**Step 1: Create Analyzer Class**

Create `src/features/new_analyzer.py`:

```python
"""
new_analyzer.py - Description of new analysis feature

This module provides:
- Feature 1
- Feature 2
"""

import logging
from typing import Dict, List, Optional
from decimal import Decimal

from ..data.api_client import APIClient
from ..infrastructure.version_manager import VersionManager

logger = logging.getLogger(__name__)


class NewAnalyzer:
    """Analyzes new feature."""

    def __init__(self):
        self.api_client = APIClient()
        self.version_manager = VersionManager()

    def analyze_feature(self, team_id: int, league_id: int, season: int) -> Dict:
        """
        Analyze new feature for a team.

        Args:
            team_id: Team identifier
            league_id: League identifier
            season: Season year

        Returns:
            Analysis results
        """
        try:
            # Fetch data
            data = self._fetch_data(team_id, league_id, season)

            # Perform analysis
            result = self._perform_analysis(data)

            return result

        except Exception as e:
            logger.error(f"Error analyzing feature: {e}")
            return self._get_default_result()

    def _fetch_data(self, team_id, league_id, season):
        """Fetch required data."""
        # Implementation
        pass

    def _perform_analysis(self, data):
        """Perform the analysis."""
        # Implementation
        pass

    def _get_default_result(self):
        """Return default result when analysis fails."""
        return {
            'analyzed': False,
            'default_used': True
        }


# Convenience function
def analyze_new_feature(team_id: int, league_id: int, season: int) -> Dict:
    """
    Convenience function to analyze new feature.

    Args:
        team_id: Team identifier
        league_id: League identifier
        season: Season year

    Returns:
        Analysis results
    """
    analyzer = NewAnalyzer()
    return analyzer.analyze_feature(team_id, league_id, season)
```

**Step 2: Add Tests**

Create `tests/test_new_analyzer.py`:

```python
import pytest
from src.features.new_analyzer import NewAnalyzer, analyze_new_feature


class TestNewAnalyzer:
    """Test suite for NewAnalyzer."""

    def test_analyzer_initialization(self):
        """Test analyzer initializes correctly."""
        analyzer = NewAnalyzer()
        assert analyzer is not None
        assert analyzer.api_client is not None

    def test_analyze_feature(self):
        """Test feature analysis."""
        result = analyze_new_feature(
            team_id=33,
            league_id=39,
            season=2024
        )
        assert isinstance(result, dict)
        assert 'analyzed' in result

    def test_fallback_on_error(self):
        """Test fallback when data unavailable."""
        analyzer = NewAnalyzer()
        result = analyzer._get_default_result()
        assert result['default_used'] is True


def test_convenience_function():
    """Test convenience function works."""
    result = analyze_new_feature(33, 39, 2024)
    assert result is not None
```

**Step 3: Integrate with Team Calculator**

Edit `src/parameters/team_calculator.py`:

```python
# Add import
from ..features.new_analyzer import NewAnalyzer

# In fit_team_params() function, add:
new_analyzer = NewAnalyzer()
new_params = new_analyzer.analyze_feature(team_id, league_id, season)

# Add to final params
params['new_feature'] = new_params
```

**Step 4: Update Documentation**

Add to `docs/API_DOCUMENTATION.md`:

```markdown
### New Feature Analysis

#### `analyze_new_feature()`

**Module:** `src.features.new_analyzer`

**Signature:**
```python
def analyze_new_feature(
    team_id: int,
    league_id: int,
    season: int
) -> Dict
```

**Returns:**
Description of return value
```

**Step 5: Run Tests**

```bash
# Run new tests
python3 -m pytest tests/test_new_analyzer.py -v

# Run all tests
python3 -m pytest tests/ -v

# Check coverage
python3 -m pytest tests/ --cov=src.features.new_analyzer --cov-report=html
```

---

## Testing

### Test Structure

```
tests/
├── unit/                       # Unit tests
│   ├── test_analyzers.py
│   ├── test_calculators.py
│   └── test_utils.py
├── integration/                # Integration tests
│   ├── test_phase1_integration.py
│   └── test_complete_system.py
├── fixtures/                   # Test data
│   └── sample_data.json
└── conftest.py                 # Pytest configuration
```

### Writing Tests

**Unit Test Example:**

```python
import pytest
from decimal import Decimal
from src.features.venue_analyzer import VenueAnalyzer


class TestVenueAnalyzer:
    """Test VenueAnalyzer functionality."""

    @pytest.fixture
    def analyzer(self):
        """Create analyzer instance."""
        return VenueAnalyzer()

    def test_initialization(self, analyzer):
        """Test analyzer initializes correctly."""
        assert analyzer is not None

    def test_calculate_stadium_advantage(self, analyzer):
        """Test stadium advantage calculation."""
        advantage = analyzer.calculate_stadium_advantage(
            team_id=33,
            venue_id=556,
            league_id=39,
            season=2024
        )
        assert isinstance(advantage, Decimal)
        assert 0.8 <= advantage <= 1.5

    @pytest.mark.parametrize("distance,expected_range", [
        (0, (0.98, 1.00)),
        (500, (0.90, 0.95)),
        (1000, (0.85, 0.90))
    ])
    def test_travel_impact(self, analyzer, distance, expected_range):
        """Test travel impact calculation."""
        impact = analyzer.calculate_travel_impact(distance)
        assert expected_range[0] <= impact <= expected_range[1]
```

**Integration Test Example:**

```python
def test_complete_prediction_pipeline():
    """Test complete prediction generation."""
    from src.prediction.prediction_engine import generate_prediction_with_reporting

    prediction = generate_prediction_with_reporting(
        home_team_id=33,
        away_team_id=40,
        league_id=39,
        season=2024
    )

    # Validate structure
    assert 'predictions' in prediction
    assert 'confidence_analysis' in prediction
    assert 'metadata' in prediction

    # Validate data types
    assert isinstance(prediction['predictions']['home_team']['score_probability'], float)
    assert 0 <= prediction['predictions']['home_team']['score_probability'] <= 1
```

### Running Tests

```bash
# Run all tests
python3 -m pytest tests/ -v

# Run specific test file
python3 -m pytest tests/test_venue_analyzer.py -v

# Run with coverage
python3 -m pytest tests/ --cov=src --cov-report=html

# Run specific test
python3 -m pytest tests/test_venue_analyzer.py::TestVenueAnalyzer::test_initialization

# Run integration tests only
python3 -m pytest tests/integration/ -v

# Run with debugging
python3 -m pytest tests/ -v --pdb
```

---

## Code Style

### Style Guide

Follow **PEP 8** with these specifics:

- **Line Length:** 100 characters max
- **Indentation:** 4 spaces (no tabs)
- **Imports:** Grouped and sorted
- **Docstrings:** Google style
- **Type Hints:** Required for public functions

### Example Code Style

```python
"""
Module docstring explaining purpose.

This module provides functionality for...
"""

import os
import logging
from typing import Dict, List, Optional
from decimal import Decimal
from datetime import datetime

from ..data.api_client import APIClient
from ..utils.constants import DEFAULT_VALUE

logger = logging.getLogger(__name__)


class MyAnalyzer:
    """
    Brief description of class.

    Longer description providing more details about the class purpose
    and usage patterns.

    Attributes:
        api_client: API client for external data
        cache: Internal cache dictionary
    """

    def __init__(self, config: Optional[Dict] = None):
        """
        Initialize analyzer.

        Args:
            config: Optional configuration dictionary
        """
        self.api_client = APIClient()
        self.cache = {}
        self._config = config or {}

    def analyze_data(self, team_id: int, league_id: int, season: int) -> Dict:
        """
        Analyze data for a team.

        Args:
            team_id: Team identifier
            league_id: League identifier
            season: Season year

        Returns:
            Dictionary containing analysis results with keys:
                - 'metric1': Description
                - 'metric2': Description

        Raises:
            ValueError: If team_id is invalid
            APIError: If external API fails

        Example:
            >>> analyzer = MyAnalyzer()
            >>> result = analyzer.analyze_data(33, 39, 2024)
            >>> print(result['metric1'])
            1.25
        """
        # Validate inputs
        if not isinstance(team_id, int) or team_id <= 0:
            raise ValueError(f"Invalid team_id: {team_id}")

        try:
            # Fetch data
            data = self._fetch_data(team_id, league_id, season)

            # Process data
            result = self._process_data(data)

            return result

        except Exception as e:
            logger.error(f"Error analyzing data for team {team_id}: {e}")
            return self._get_default_result()

    def _fetch_data(self, team_id: int, league_id: int, season: int) -> Dict:
        """
        Fetch required data (private method).

        Args:
            team_id: Team identifier
            league_id: League identifier
            season: Season year

        Returns:
            Raw data dictionary
        """
        # Implementation
        pass

    def _process_data(self, data: Dict) -> Dict:
        """Process raw data into analysis results."""
        # Implementation
        pass

    def _get_default_result(self) -> Dict:
        """Return default result when processing fails."""
        return {
            'metric1': Decimal('1.0'),
            'metric2': Decimal('0.5'),
            'data_quality': 'default'
        }
```

### Code Formatting

```bash
# Format code with black
black src/ tests/

# Check code with pylint
pylint src/

# Check type hints with mypy
mypy src/

# Sort imports
isort src/ tests/
```

---

## Contributing

### Contribution Workflow

1. **Fork the repository**
2. **Create a feature branch**
   ```bash
   git checkout -b feature/amazing-feature
   ```

3. **Make your changes**
   - Write code
   - Add tests
   - Update documentation

4. **Run tests**
   ```bash
   python3 -m pytest tests/ -v
   pylint src/
   black src/ tests/
   ```

5. **Commit changes**
   ```bash
   git commit -m "feat: add amazing feature"
   ```

6. **Push to branch**
   ```bash
   git push origin feature/amazing-feature
   ```

7. **Open Pull Request**

### Commit Message Format

Follow **Conventional Commits**:

```
<type>(<scope>): <subject>

<body>

<footer>
```

**Types:**
- `feat`: New feature
- `fix`: Bug fix
- `docs`: Documentation
- `style`: Code style changes
- `refactor`: Code refactoring
- `test`: Adding tests
- `chore`: Maintenance

**Examples:**
```
feat(manager-analyzer): add manager tactical profile analysis

- Implement manager profile extraction from API
- Add tactical flexibility calculation
- Integrate with tactical analyzer

Closes #123
```

---

## Common Tasks

### Add New API Endpoint

```python
# In src/data/api_client.py

def get_new_data(param1: int, param2: str, max_retries: int = 5) -> Optional[Dict]:
    """
    Get new data from API.

    Args:
        param1: Parameter 1 description
        param2: Parameter 2 description
        max_retries: Maximum retry attempts

    Returns:
        Data dictionary or None if failed
    """
    url = f"{API_FOOTBALL_BASE_URL}/new-endpoint"
    params = {
        "param1": str(param1),
        "param2": param2
    }

    data = _make_api_request(url, params, max_retries=max_retries)

    if not data or "response" not in data:
        return None

    return data["response"]


# Add to APIClient class
class APIClient:
    def get_new_data(self, param1, param2, max_retries=5):
        return get_new_data(param1, param2, max_retries)
```

### Add New Calculation

```python
# In src/parameters/team_calculator.py

def calculate_new_metric(team_data: pd.DataFrame) -> Decimal:
    """
    Calculate new metric from team data.

    Args:
        team_data: DataFrame with team match data

    Returns:
        Calculated metric as Decimal
    """
    if team_data.empty:
        return Decimal('1.0')

    # Calculate metric
    metric = team_data['column'].mean()

    return Decimal(str(metric))
```

### Add New Phase

1. **Create Phase Module**
   ```python
   # src/features/phase7_analyzer.py
   class Phase7Analyzer:
       def analyze(...):
           pass
   ```

2. **Update Version Manager**
   ```python
   # In src/infrastructure/version_manager.py
   CURRENT_VERSION = '7.0'
   VERSION_FEATURES['7.0'] = ['new_feature']
   ```

3. **Integrate with Calculator**
   ```python
   # In src/parameters/team_calculator.py
   from ..features.phase7_analyzer import Phase7Analyzer

   # Add to fit_team_params()
   phase7_analyzer = Phase7Analyzer()
   phase7_params = phase7_analyzer.analyze(...)
   params['phase7_params'] = phase7_params
   ```

4. **Add Tests**
   ```python
   # tests/test_phase7.py
   ```

5. **Update Documentation**

---

## Debugging

### Enable Debug Logging

```python
import logging

logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
```

### Use Debugger

```python
import pdb

def problematic_function():
    # Set breakpoint
    pdb.set_trace()

    # Continue debugging...
```

### Profile Performance

```python
import cProfile
import pstats

profiler = cProfile.Profile()
profiler.enable()

# Code to profile
generate_prediction(...)

profiler.disable()
stats = pstats.Stats(profiler)
stats.sort_stats('cumulative')
stats.print_stats(20)
```

---

**Happy Coding! 🚀**

**Last Updated:** October 4, 2025
**Version:** 6.0
