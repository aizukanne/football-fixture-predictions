# Six-Phase Architecture Enhancement: Outputs & Testing

## Phase 1: Opponent Strength Stratification

### Expected Output
**Data Changes:**
- Each team has 3 sets of performance metrics (vs strong/average/weak opponents)
- Predictions use opponent-appropriate parameters instead of overall averages
- All new predictions tagged with `architecture_version='2.0'`
- Multipliers reset to 1.0 (neutral baseline during learning period)

**Performance Impact:**
- 10-15% reduction in prediction error for teams with large performance gaps by opponent tier
- Improved accuracy for mid-table teams (who show most variance by opponent)
- Top/bottom teams may show minimal change (they're always favorites/underdogs)

### Individual Testing Strategy

**Test 1: Segmentation Calculation Validation**
```python
def test_phase1_segmentation():
    """Verify segmented parameters are calculated correctly."""
    
    # Select a team known to perform very differently by opponent
    # Example: Mid-table team that beats weak teams but loses to strong ones
    test_team_id = 33  # Manchester United or similar
    test_league_id = 39  # Premier League
    
    # Get their match history
    matches = get_team_matches(test_team_id, test_league_id, season='2024')
    
    # Manually segment matches by opponent strength
    strong_opponent_matches = [m for m in matches if opponent_position(m) <= 6]
    weak_opponent_matches = [m for m in matches if opponent_position(m) >= 15]
    
    # Calculate mu manually for each segment
    mu_vs_strong_manual = mean([goals_scored(m) for m in strong_opponent_matches])
    mu_vs_weak_manual = mean([goals_scored(m) for m in weak_opponent_matches])
    
    # Get system's calculated values
    team_params = fit_team_params(matches, test_team_id, test_league_id, standings)
    mu_vs_strong_system = team_params['segmented_params']['home']['strong']['mu']
    mu_vs_weak_system = team_params['segmented_params']['home']['weak']['mu']
    
    # Verify they match
    assert abs(mu_vs_strong_manual - mu_vs_strong_system) < 0.01
    assert abs(mu_vs_weak_manual - mu_vs_weak_system) < 0.01
    
    # Verify there's meaningful difference (for teams that should show it)
    assert abs(mu_vs_weak_system - mu_vs_strong_system) > 0.3
    
    print(f"✓ Segmentation working: vs Strong={mu_vs_strong_system:.2f}, "
          f"vs Weak={mu_vs_weak_system:.2f}")
```

**Test 2: Prediction Improvement Validation**
```python
def test_phase1_prediction_improvement():
    """Compare prediction accuracy with and without segmentation."""
    
    # Get completed matches from a recent season
    historical_matches = get_completed_matches(league_id=39, season='2023')
    
    errors_without_segmentation = []
    errors_with_segmentation = []
    
    for match in historical_matches:
        home_id = match['home_team_id']
        away_id = match['away_team_id']
        actual_home_goals = match['home_goals']
        
        # Predict WITHOUT segmentation (use overall averages)
        home_params_overall = get_overall_params(home_id)
        pred_without = predict_match(match, home_params_overall, use_segmentation=False)
        errors_without_segmentation.append(abs(pred_without - actual_home_goals))
        
        # Predict WITH segmentation
        home_params_segmented = get_segmented_params(home_id, opponent_tier='weak')
        pred_with = predict_match(match, home_params_segmented, use_segmentation=True)
        errors_with_segmentation.append(abs(pred_with - actual_home_goals))
    
    mae_without = mean(errors_without_segmentation)
    mae_with = mean(errors_with_segmentation)
    improvement = ((mae_without - mae_with) / mae_without) * 100
    
    print(f"MAE without segmentation: {mae_without:.3f}")
    print(f"MAE with segmentation: {mae_with:.3f}")
    print(f"Improvement: {improvement:.1f}%")
    
    # Expect at least 5% improvement
    assert mae_with < mae_without * 0.95
```

**Test 3: Version Tracking Validation**
```python
def test_phase1_version_tracking():
    """Ensure all new data is properly versioned."""
    
    # Get recent team parameters
    team_params = get_team_params_from_db('39-33')
    assert team_params['architecture_version'] == '2.0'
    assert team_params['architecture_features']['segmentation'] == True
    
    # Get recent prediction
    recent_fixture = get_recent_fixture()
    assert recent_fixture['prediction_metadata']['architecture_version'] == '2.0'
    
    # Verify multipliers are neutral during learning period
    assert abs(float(team_params['home_multiplier']) - 1.0) < 0.01
    assert abs(float(team_params['away_multiplier']) - 1.0) < 0.01
    
    print("✓ Version tracking working correctly")
```

**Acceptance Criteria:**
- ✅ At least 70% of teams show different mu values across opponent tiers
- ✅ Predictions for same team vary by at least 0.2 goals depending on opponent tier
- ✅ MAE reduction of 5-15% on historical validation set
- ✅ 100% of new predictions have version='2.0' tag
- ✅ All multipliers = 1.0 for first 21 days post-deployment

---

## Phase 2: Enhanced Prediction Error Tracking

### Expected Output
**Data Changes:**
- Each team has detailed error profile with venue-specific metrics
- Teams classified into 4 categories: well_modeled, inherently_chaotic, model_inadequacy, needs_more_data
- Automatic fallback strategy activated for ~10-20% of teams (model_inadequacy cases)
- Error tracking segmented by opponent tier and time window

**Performance Impact:**
- 20-40% reduction in worst prediction errors (eliminating catastrophic misses)
- Smaller improvement in average error (5-10%) but much better worst-case
- More honest confidence intervals for chaotic teams
- Fewer predictions with >3 goal error

### Individual Testing Strategy

**Test 1: Error Profile Calculation**
```python
def test_phase2_error_profiling():
    """Verify error profiles correctly identify problematic teams."""
    
    # Use Penybont (team_id=2191) - known high std_dev case
    fixtures = get_historical_fixtures(team_id=2191, days_back=180)
    
    error_profile = calculate_error_profile(
        fixtures,
        team_id=2191,
        variance_home=1.4,
        variance_away=1.4
    )
    
    # Should detect high away std_dev
    assert error_profile['away']['std_dev_overall'] > 4.0
    
    # Should calculate inadequacy score correctly
    expected_inadequacy = error_profile['away']['std_dev_overall'] / sqrt(1.4)
    actual_inadequacy = error_profile['away']['inadequacy_score']
    assert abs(expected_inadequacy - actual_inadequacy) < 0.1
    
    # Should classify as model_inadequacy
    assert error_profile['classification']['category'] == 'model_inadequacy'
    
    print(f"✓ Correctly identified model inadequacy: "
          f"std_dev={error_profile['away']['std_dev_overall']:.2f}, "
          f"inadequacy={actual_inadequacy:.2f}")
```

**Test 2: Fallback Strategy Effectiveness**
```python
def test_phase2_fallback_improvement():
    """Verify fallback strategy reduces errors for problematic teams."""
    
    # Identify teams with model_inadequacy classification
    problem_teams = [
        t for t in get_all_teams()
        if t['error_profile']['classification']['category'] == 'model_inadequacy'
    ]
    
    print(f"Testing fallback on {len(problem_teams)} problem teams")
    
    improvements = []
    for team in problem_teams:
        matches = get_team_historical_matches(team['team_id'])
        
        # Calculate errors with standard method
        standard_errors = []
        for match in matches:
            pred = predict_standard(match, team['params'])
            error = abs(pred - match['actual_goals'])
            standard_errors.append(error)
        
        # Calculate errors with fallback method
        fallback_errors = []
        for match in matches:
            pred = predict_with_fallback(match, team['params'])
            error = abs(pred - match['actual_goals'])
            fallback_errors.append(error)
        
        mae_standard = mean(standard_errors)
        mae_fallback = mean(fallback_errors)
        improvement_pct = ((mae_standard - mae_fallback) / mae_standard) * 100
        
        improvements.append(improvement_pct)
        
        if improvement_pct < 0:
            print(f"⚠️  Team {team['team_id']}: fallback WORSE by {abs(improvement_pct):.1f}%")
    
    avg_improvement = mean(improvements)
    print(f"Average improvement for problem teams: {avg_improvement:.1f}%")
    
    # Fallback should improve predictions for majority of problem teams
    assert avg_improvement > 10  # At least 10% average improvement
    assert sum(1 for i in improvements if i > 0) / len(improvements) > 0.7  # 70%+ improved
```

**Test 3: Classification Accuracy**
```python
def test_phase2_classification_accuracy():
    """Verify team classification matches expected patterns."""
    
    # Get classification distribution
    all_teams = get_all_team_params()
    
    classifications = {
        'well_modeled': [],
        'inherently_chaotic': [],
        'model_inadequacy': [],
        'needs_more_data': []
    }
    
    for team in all_teams:
        category = team['error_profile']['classification']['category']
        classifications[category].append(team)
    
    total = len(all_teams)
    print("\nClassification Distribution:")
    for category, teams in classifications.items():
        pct = (len(teams) / total) * 100
        print(f"  {category}: {len(teams)} ({pct:.1f}%)")
    
    # Expected distribution (approximate)
    assert 0.40 <= len(classifications['well_modeled']) / total <= 0.65  # 40-65%
    assert 0.05 <= len(classifications['inherently_chaotic']) / total <= 0.20  # 5-20%
    assert 0.05 <= len(classifications['model_inadequacy']) / total <= 0.25  # 5-25%
    
    # Verify well_modeled teams actually have low errors
    for team in classifications['well_modeled']:
        avg_std = (team['error_profile']['home']['std_dev_overall'] + 
                   team['error_profile']['away']['std_dev_overall']) / 2
        assert avg_std < 2.5  # Should be low
```

**Acceptance Criteria:**
- ✅ Error profiles calculated for 95%+ of teams with sufficient data
- ✅ 10-25% of teams classified as model_inadequacy
- ✅ Fallback strategy reduces errors by 15%+ for model_inadequacy teams
- ✅ Maximum single prediction error reduced by 30%+ across all predictions
- ✅ Classification stable over time (same team doesn't flip categories weekly)

---

## Phase 3: Multi-Timescale Form Integration

### Expected Output
**Data Changes:**
- Each prediction includes form analysis (hot_streak, slump, or baseline)
- Form adjustments applied to ~20-30% of predictions
- Personnel correlation tracking for key player injuries/returns
- Temporal error trends showing if model improving/degrading per team

**Performance Impact:**
- 8-15% improvement in prediction accuracy during team form changes
- Better handling of tactical/personnel transitions
- Reduced lag in adapting to new team capabilities
- Fewer errors on teams in clear hot streaks or slumps

### Individual Testing Strategy

**Test 1: Form Detection Accuracy**
```python
def test_phase3_form_detection():
    """Verify form patterns are detected correctly."""
    
    # Create synthetic hot streak scenario
    hot_streak_matches = [
        {'date': '2024-10-01', 'is_home': True, 'home_goals': 3},
        {'date': '2024-09-24', 'is_home': True, 'home_goals': 2},
        {'date': '2024-09-17', 'is_home': True, 'home_goals': 3},
        {'date': '2024-09-10', 'is_home': True, 'home_goals': 2},
        {'date': '2024-09-03', 'is_home': True, 'home_goals': 3},
        {'date': '2024-08-27', 'is_home': True, 'home_goals': 4},
    ]
    
    baseline_lambda = 1.5  # Season average
    
    form = detect_form_pattern(hot_streak_matches, 'home', baseline_lambda)
    
    assert form['pattern'] == 'hot_streak'
    assert form['adjustment_factor'] > 0.5  # Should suggest upward adjustment
    assert form['confidence'] > 0.7
    
    print(f"✓ Hot streak detected: adjustment={form['adjustment_factor']:.2f}")
    
    # Test baseline (no pattern) scenario
    baseline_matches = [
        {'date': '2024-10-01', 'is_home': True, 'home_goals': 2},
        {'date': '2024-09-24', 'is_home': True, 'home_goals': 1},
        {'date': '2024-09-17', 'is_home': True, 'home_goals': 2},
        {'date': '2024-09-10', 'is_home': True, 'home_goals': 1},
        {'date': '2024-09-03', 'is_home': True, 'home_goals': 2},
    ]
    
    form_baseline = detect_form_pattern(baseline_matches, 'home', baseline_lambda)
    
    assert form_baseline['pattern'] == 'baseline'
    assert abs(form_baseline['adjustment_factor']) < 0.2
    
    print(f"✓ Baseline correctly identified")
```

**Test 2: Form Adjustment Impact**
```python
def test_phase3_form_adjustment_impact():
    """Verify form adjustments improve predictions during transitions."""
    
    # Find teams that went through clear form changes
    teams_with_form_changes = identify_form_change_teams(
        min_change_magnitude=1.0,  # At least 1 goal/game shift
        min_consistency=6  # Lasted 6+ matches
    )
    
    print(f"Testing on {len(teams_with_form_changes)} teams with form changes")
    
    improvements = []
    for team_data in teams_with_form_changes:
        form_period_matches = team_data['matches_during_form_change']
        
        # Predict WITHOUT form adjustment
        errors_without_form = []
        for match in form_period_matches:
            pred = predict_without_form(match, team_data['baseline_params'])
            errors_without_form.append(abs(pred - match['actual_goals']))
        
        # Predict WITH form adjustment
        errors_with_form = []
        for match in form_period_matches:
            pred = predict_with_form(match, team_data['baseline_params'])
            errors_with_form.append(abs(pred - match['actual_goals']))
        
        mae_without = mean(errors_without_form)
        mae_with = mean(errors_with_form)
        improvement_pct = ((mae_without - mae_with) / mae_without) * 100
        
        improvements.append(improvement_pct)
    
    avg_improvement = mean(improvements)
    print(f"Average improvement during form changes: {avg_improvement:.1f}%")
    
    # Expect meaningful improvement
    assert avg_improvement > 8  # At least 8% improvement
```

**Test 3: Personnel Correlation**
```python
def test_phase3_personnel_correlation():
    """Verify injury events correlate with form changes."""
    
    # Find teams with documented key player injuries
    teams_with_injuries = get_teams_with_key_injuries(
        impact_score_threshold=7.0,  # High impact players only
        season='2024'
    )
    
    correlations_found = 0
    total_injuries = 0
    
    for team in teams_with_injuries:
        injury_events = team['injury_events']
        form_changes = team['form_change_dates']
        
        for injury in injury_events:
            total_injuries += 1
            injury_date = injury['date']
            
            # Check if form changed within 2 weeks
            for form_change in form_changes:
                days_diff = abs((form_change['date'] - injury_date).days)
                if days_diff <= 14:
                    correlations_found += 1
                    print(f"✓ Correlation: {injury['player_name']} injury on {injury_date} "
                          f"→ form {form_change['pattern']} {days_diff} days later")
                    break
    
    correlation_rate = correlations_found / total_injuries
    print(f"\nCorrelation rate: {correlation_rate*100:.1f}% "
          f"({correlations_found}/{total_injuries})")
    
    # Expect significant correlation for high-impact players
    assert correlation_rate > 0.4  # At least 40% correlation
```

**Acceptance Criteria:**
- ✅ Form patterns detected in 25-35% of recent match windows
- ✅ Hot streak detection has 70%+ precision (detected streaks are real)
- ✅ Form adjustments improve accuracy by 10%+ during transition periods
- ✅ 40%+ correlation between key injuries and form changes
- ✅ Form adjustment magnitude scales appropriately (0.2-0.8 goals typical)

---

## Phase 4: Derived Tactical Style Features

### Expected Output
**Data Changes:**
- Each team has tactical profile with 4 normalized scores (0-10 scale)
- Tactical matchup adjustments applied to ~30-40% of predictions
- League-wide tactical context for normalization
- Tactical style stability tracking over time

**Performance Impact:**
- 5-10% improvement in predictions for stylistic mismatches
- Better handling of high/low scoring games (both teams attacking vs both defending)
- Improved accuracy for counter-attacking vs possession teams
- More accurate derby/rivalry predictions

### Individual Testing Strategy

**Test 1: Tactical Profile Calculation**
```python
def test_phase4_tactical_profiles():
    """Verify tactical profiles characterize teams correctly."""
    
    # Test on known defensive team (e.g., Atletico Madrid)
    defensive_team_id = 530
    defensive_matches = get_team_matches(defensive_team_id)
    
    profile = calculate_tactical_profile(defensive_matches, league_context)
    
    # Should show high defensive solidity
    assert profile['defensive_solidity'] > 7.0
    assert profile['attacking_intensity'] < 6.0
    
    print(f"✓ Defensive team profile: defensive_solidity={profile['defensive_solidity']:.1f}")
    
    # Test on known attacking team (e.g., Manchester City)
    attacking_team_id = 50
    attacking_matches = get_team_matches(attacking_team_id)
    
    profile_attacking = calculate_tactical_profile(attacking_matches, league_context)
    
    # Should show high attacking intensity
    assert profile_attacking['attacking_intensity'] > 7.0
    
    print(f"✓ Attacking team profile: attacking_intensity={profile_attacking['attacking_intensity']:.1f}")
    
    # Verify normalization (scores should be distributed 0-10)
    all_profiles = get_all_tactical_profiles(league_id=39)
    attacking_scores = [p['attacking_intensity'] for p in all_profiles]
    
    assert min(attacking_scores) >= 0
    assert max(attacking_scores) <= 10
    assert 4.0 < mean(attacking_scores) < 6.0  # Should be centered around 5
```

**Test 2: Tactical Matchup Adjustments**
```python
def test_phase4_tactical_matchup_logic():
    """Verify tactical adjustments apply correctly."""
    
    # Scenario 1: Counter-attacking home vs attacking away
    home_tactical = {
        'counter_efficiency': 8.0,
        'attacking_intensity': 5.0,
        'defensive_solidity': 7.0,
        'possession_style': 4.0
    }
    
    away_tactical = {
        'counter_efficiency': 4.0,
        'attacking_intensity': 8.5,
        'defensive_solidity': 4.0,
        'possession_style': 8.0
    }
    
    home_adj, away_adj, metadata = apply_tactical_matchup_adjustment(
        home_lambda=1.5,
        away_lambda=1.2,
        home_tactical=home_tactical,
        away_tactical=away_tactical
    )
    
    # Home should get boost (counter vs attack)
    assert home_adj > 1.5
    assert 'counter_vs_attack' in [r['rule'] for r in metadata['rules_triggered']]
    
    print(f"✓ Counter vs attack: home boosted from 1.5 to {home_adj:.2f}")
    
    # Scenario 2: Both teams defensive
    both_defensive_home = {'defensive_solidity': 8.0, 'attacking_intensity': 4.0, 
                          'counter_efficiency': 5.0, 'possession_style': 5.0}
    both_defensive_away = {'defensive_solidity': 8.5, 'attacking_intensity': 3.5,
                          'counter_efficiency': 4.5, 'possession_style': 4.0}
    
    home_adj2, away_adj2, metadata2 = apply_tactical_matchup_adjustment(
        home_lambda=1.5,
        away_lambda=1.2,
        home_tactical=both_defensive_home,
        away_tactical=both_defensive_away
    )
    
    # Both should be reduced (defensive stalemate)
    assert home_adj2 < 1.5
    assert away_adj2 < 1.2
    
    print(f"✓ Defensive stalemate: reduced to {home_adj2:.2f} and {away_adj2:.2f}")
```

**Test 3: Tactical Impact on Accuracy**
```python
def test_phase4_tactical_improvement():
    """Verify tactical features improve predictions for style mismatches."""
    
    # Find matches with clear tactical mismatches
    mismatched_fixtures = find_tactical_mismatch_fixtures(
        min_style_gap=4.0,  # At least 4 points difference in tactical scores
        match_types=['counter_vs_possession', 'defensive_clash', 'offensive_clash']
    )
    
    print(f"Testing on {len(mismatched_fixtures)} tactical mismatch fixtures")
    
    improvements_by_type = {}
    
    for fixture in mismatched_fixtures:
        mismatch_type = fixture['mismatch_type']
        
        # Predict without tactical adjustment
        pred_without = predict_without_tactical(fixture)
        error_without = abs(pred_without - fixture['actual_total_goals'])
        
        # Predict with tactical adjustment
        pred_with = predict_with_tactical(fixture)
        error_with = abs(pred_with - fixture['actual_total_goals'])
        
        if mismatch_type not in improvements_by_type:
            improvements_by_type[mismatch_type] = []
        
        improvement = error_without - error_with
        improvements_by_type[mismatch_type].append(improvement)
    
    for match_type, improvements in improvements_by_type.items():
        avg_improvement = mean(improvements)
        improved_pct = sum(1 for i in improvements if i > 0) / len(improvements)
        
        print(f"{match_type}: avg improvement={avg_improvement:.2f} goals, "
              f"{improved_pct*100:.1f}% improved")
        
        # Expect positive improvement for mismatch scenarios
        assert avg_improvement > 0.1  # At least 0.1 goal improvement
```

**Acceptance Criteria:**
- ✅ 80%+ of teams have tactical profiles calculated
- ✅ Profiles stable over 5+ match window (same team doesn't flip drastically)
- ✅ Known defensive teams score 7+ on defensive_solidity
- ✅ Known attacking teams score 7+ on attacking_intensity
- ✅ Tactical adjustments improve accuracy by 5%+ on style mismatch fixtures
- ✅ Adjustments applied to 30-40% of predictions

---

## Phase 5: Team Classification & Adaptive Strategy

### Expected Output
**Data Changes:**
- Every team classified into predictability category
- Strategy selection metadata on every prediction
- Strategy performance tracking per team
- Confidence interval adjustments based on classification

**Performance Impact:**
- Overall MAE reduction of 10-15% through optimized strategy selection
- 30-50% reduction in extreme errors (>3 goals off)
- Better calibrated confidence intervals
- Improved prediction stability for chaotic teams

### Individual Testing Strategy

**Test 1: Classification Distribution**
```python
def test_phase5_classification_distribution():
    """Verify team classifications are reasonable."""
    
    all_teams = get_all_team_params()
    
    classification_counts = {
        'well_modeled': 0,
        'inherently_chaotic': 0,
        'model_inadequacy': 0,
        'needs_more_data': 0,
        'insufficient_data': 0
    }
    
    for team in all_teams:
        category = team['error_profile']['classification']['category']
        classification_counts[category] += 1
    
    total = len(all_teams)
    
    print("\nClassification Distribution:")
    for category, count in classification_counts.items():
        pct = (count / total) * 100
        print(f"  {category}: {count} ({pct:.1f}%)")
    
    # Sanity checks
    assert classification_counts['well_modeled'] > total * 0.30  # At least 30% well-modeled
    assert classification_counts['model_inadequacy'] < total * 0.30  # Less than 30% inadequacy
    assert classification_counts['insufficient_data'] < total * 0.20  # Less than 20% insufficient
    
    print("✓ Classification distribution looks reasonable")
```

**Test 2: Strategy Selection Logic**
```python
def test_phase5_strategy_selection():
    """Verify correct strategies selected for each classification."""
    
    # Test well_modeled → standard_full
    well_modeled_classification = {
        'category': 'well_modeled',
        'confidence': 0.8,
        'metrics': {'variance': 1.5, 'std_dev': 1.2}
    }
    
    strategy = select_prediction_strategy(well_modeled_classification, 'home')
    
    assert strategy['method'] == 'standard_full'
    assert strategy['use_segmentation'] == True
    assert strategy['use_form_adjustment'] == True
    assert strategy['use_tactical_adjustment'] == True
    assert strategy['confidence_interval_multiplier'] == 1.0
    
    print("✓ Well-modeled → standard_full strategy")
    
    # Test model_inadequacy → fallback
    inadequacy_classification = {
        'category': 'model_inadequacy',
        'confidence': 0.85,
        'metrics': {'variance': 1.4, 'std_dev': 6.2}
    }
    
    strategy2 = select_prediction_strategy(inadequacy_classification, 'away')
    
    assert strategy2['method'] == 'fallback'
    assert strategy2['use_segmentation'] == False
    assert strategy2['confidence_interval_multiplier'] >= 1.2
    
    print("✓ Model inadequacy → fallback strategy")
    
    # Test inherently_chaotic → standard_wide_intervals
    chaotic_classification = {
        'category': 'inherently_chaotic',
        'confidence': 0.7,
        'metrics': {'variance': 5.5, 'std_dev': 3.2}
    }
    
    strategy3 = select_prediction_strategy(chaotic_classification, 'home')
    
    assert strategy3['method'] == 'standard_wide_intervals'
    assert strategy3['confidence_interval_multiplier'] == 1.5
    
    print("✓ Inherently chaotic → wide intervals strategy")
```

**Test 3: Strategy Performance Comparison**
```python
def test_phase5_strategy_performance():
    """Verify adaptive strategies outperform one-size-fits-all."""
    
    # Get predictions from last 30 days
    recent_completed_matches = get_completed_matches(days_back=30)
    
    # Compare adaptive vs always-standard
    errors_adaptive = []
    errors_always_standard = []
    
    for match in recent_completed_matches:
        actual_goals = match['actual_home_goals']
        
        # Get what was actually predicted (with adaptive strategy)
        adaptive_pred = match['predicted_home_goals']
        errors_adaptive.append(abs(adaptive_pred - actual_goals))
        
        # Simulate what would have been predicted with always-standard
        standard_pred = predict_with_standard_strategy(match)
        errors_always_standard.append(abs(standard_pred - actual_goals))
    
    mae_adaptive = mean(errors_adaptive)
    mae_always_standard = mean(errors_always_standard)
    improvement = ((mae_always_standard - mae_adaptive) / mae_always_standard) * 100
    
    print(f"MAE with adaptive strategies: {mae_adaptive:.3f}")
    print(f"MAE with always-standard: {mae_always_standard:.3f}")
    print(f"Improvement: {improvement:.1f}%")
    
    # Adaptive should be better
    assert mae_adaptive < mae_always_standard
    
    # Check extreme error reduction
    extreme_errors_adaptive = sum(1 for e in errors_adaptive if e > 3.0)
    extreme_errors_standard = sum(1 for e in errors_always_standard if e > 3.0)
    
    print(f"Extreme errors (>3 goals): adaptive={extreme_errors_adaptive}, "
          f"standard={extreme_errors_standard}")
    
    # Adaptive should reduce extreme errors
    assert extreme_errors_adaptive < extreme_errors_standard
```

**Acceptance Criteria:**
- ✅ 95%+ of teams have valid classification
- ✅ Well-modeled teams get standard_full strategy
- ✅ Model_inadequacy teams get fallback strategy
- ✅ Adaptive approach reduces overall MAE by 10%+
- ✅ Extreme errors (>3 goals) reduced by 30%+
- ✅ Strategy selection stable (team doesn't flip strategies match-to-match)

---

## Phase 6: Confidence Calibration & Reporting

### Expected Output
**Data Changes:**
- Calibration metrics calculated weekly by team category
- Automated confidence adjustments based on calibration errors
- Anomaly detection flagging unusual prediction patterns
- CloudWatch dashboard with real-time monitoring

**Performance Impact:**
- Well-calibrated probabilities (stated 30% occurs ~30% of time)
- Improved confidence intervals match actual outcome distribution
- Early detection of model degradation
- Better informed betting recommendations

### Individual Testing Strategy

**Test 1: Calibration Calculation**
```python
def test_phase6_calibration_accuracy():
    """Verify calibration metrics calculated correctly."""
    
    # Get completed matches with probabilities
    matches = get_completed_matches_with_probabilities(days_back=60)
    
    # Bin predictions by probability
    bins = {
        '0-10%': [],
        '10-20%': [],
        '20-30%': [],
        '30-40%': [],
        '40-50%': [],
        '50-60%': [],
        '60-70%': [],
        '70-80%': [],
        '80-90%': [],
        '90-100%': []
    }
    
    for match in matches:
        home_win_prob = match['probabilities']['home_win']
        actual_home_win = match['outcome'] == 'home_win'
        
        # Bin the prediction
        bin_key = f"{int(home_win_prob//10)*10}-{int(home_win_prob//10)*10+10}%"
        bins[bin_key].append(1 if actual_home_win else 0)
    
    # Calculate actual frequencies
    print("\nCalibration Analysis:")
    calibration_errors = []
    
    for bin_key, outcomes in bins.items():
        if len(outcomes) > 0:
            stated_prob = (int(bin_key.split('-')[0]) + int(bin_key.split('-')[1].rstrip('%'))) / 2 / 100
            actual_freq = mean(outcomes)
            error = abs(stated_prob - actual_freq)
            calibration_errors.append(error)
            
            print(f"  {bin_key}: stated={stated_prob:.1%}, actual={actual_freq:.1%}, "
                  f"error={error:.1%}")
    
    avg_calibration_error = mean(calibration_errors)
    print(f"\nAverage calibration error: {avg_calibration_error:.1%}")
    
    # Well-calibrated system should have <10% average error
    assert avg_calibration_error < 0.10
```

**Test 2: Confidence Adjustment Impact**
```python
def test_phase6_confidence_adjustments():
    """Verify automated adjustments improve calibration."""
    
    # Get calibration before adjustments
    pre_adjustment_calibration = calculate_calibration_metrics(
        start_date='2025-01-01',
        end_date='2025-01-31'
    )
    
    # Apply automated adjustments for overconfident category
    if pre_adjustment_calibration['home_win_category']['bias'] == 'overconfident':
        apply_confidence_adjustment(
            category='home_win',
            adjustment_factor=1.1  # Reduce confidence by 10%
        )
    
    # Wait for new predictions (or simulate)
    time.sleep(30 * 86400)  # 30 days in simulation
    
    # Get calibration after adjustments
    post_adjustment_calibration = calculate_calibration_metrics(
        start_date='2025-02-01',
        end_date='2025-02-28'
    )
    
    # Calibration should improve
    pre_error = pre_adjustment_calibration['home_win_category']['calibration_error']
    post_error = post_adjustment_calibration['home_win_category']['calibration_error']
    
    print(f"Calibration error: before={pre_error:.3f}, after={post_error:.3f}")
    
    assert post_error < pre_error * 0.9  # At least 10% improvement
```

**Test 3: Anomaly Detection**
```python
def test_phase6_anomaly_detection():
    """Verify anomalies are detected correctly."""
    
    # Create synthetic anomaly: team suddenly performing very differently
    anomalous_team_id = 999
    
    # Simulate 5 consecutive massive prediction errors
    for i in range(5):
        create_fixture_result(
            team_id=anomalous_team_id,
            predicted_goals=1.0,
            actual_goals=4.0,  # Consistent 3-goal error
            days_ago=5-i
        )
    
    # Run anomaly detection
    anomalies = detect_prediction_anomalies()
    
    # Should flag this team
    flagged_teams = [a['team_id'] for a in anomalies]
    assert anomalous_team_id in flagged_teams
    
    anomaly = next(a for a in anomalies if a['team_id'] == anomalous_team_id)
    
    assert anomaly['reason'] == 'consecutive_large_errors'
    assert anomaly['consecutive_count'] >= 5
    assert anomaly['priority'] == 'high'
    
    print(f"✓ Anomaly detected: {anomaly['description']}")
```

**Test 4: Dashboard Metrics**
```python
def test_phase6_cloudwatch_metrics():
    """Verify metrics are being logged to CloudWatch."""
    
    cloudwatch = boto3.client('cloudwatch')
    
    # Check if metrics exist
    response = cloudwatch.list_metrics(
        Namespace='PredictionModel',
        MetricName='CalibrationError'
    )
    
    assert len(response['Metrics']) > 0
    
    # Get recent values
    end_time = datetime.now()
    start_time = end_time - timedelta(days=7)
    
    stats = cloudwatch.get_metric_statistics(
        Namespace='PredictionModel',
        MetricName='CalibrationError',
        StartTime=start_time,
        EndTime=end_time,
        Period=86400,
        Statistics=['Average']
    )
    
    assert len(stats['Datapoints']) > 0
    
    recent_calibration = stats['Datapoints'][-1]['Average']
    print(f"Recent calibration error: {recent_calibration:.3f}")
    
    # Should be reasonable
    assert recent_calibration < 0.15
```

**Acceptance Criteria:**
- ✅ Calibration error < 10% on average across all probability bins
- ✅ No systematic bias (not consistently over or under-confident)
- ✅ Confidence adjustments reduce calibration error by 10%+ over 30 days
- ✅ Anomalies detected within 24 hours of occurrence
- ✅ CloudWatch dashboard operational with all metrics
- ✅ Automated alerts trigger for calibration drift > 15%

---

## Summary: Testing Progression

### Week-by-Week Validation Schedule

**Week 1-2 (Phase 1):**
- Run segmentation validation daily
- Compare predictions with/without segmentation
- Monitor version tracking integrity
- Target: 5-15% MAE improvement on validation set

**Week 3-4 (Phase 2):**
- Validate error profiles for all teams
- Test fallback on 20-30 known problem teams
- Monitor classification stability
- Target: 20-40% reduction in worst errors

**Week 5-6 (Phase 3):**
- Test form detection on historical transitions
- Validate personnel correlations
- Monitor form adjustment impact
- Target: 10-15% improvement during form changes

**Week 7-9 (Phase 4):**
- Validate tactical profiles against expert assessment
- Test matchup adjustments on known mismatches
- Monitor tactical feature stability
- Target: 5-10% improvement on style mismatch fixtures

**Week 10-11 (Phase 5):**
- Validate classification distribution
- Test strategy routing logic
- Compare adaptive vs fixed strategies
- Target: 10-15% overall MAE improvement, 30%+ extreme error reduction

**Week 12 (Phase 6):**
- Calculate calibration metrics
- Verify automated adjustments
- Test anomaly detection
- Target: Calibration error < 10%

### Cumulative Impact Targets

By end of full deployment:
- **Overall MAE:** 25-35% reduction vs original architecture
- **Extreme Errors:** 50%+ reduction in predictions >3 goals off
- **Calibration:** <10% average error across all probability bins
- **Coverage:** 95%+ of teams with appropriate strategy
- **Reliability:** 99.9%+ prediction success rate (no crashes/failures)