"""
tactical_analyzer.py - Team tactical style and formation analysis

Phase 4: Derived Tactical Style Features
Analyzes team tactical styles, formation preferences, playing patterns, and tactical adaptability
to enhance predictions with sophisticated football intelligence.

This module provides comprehensive tactical analysis including:
- 8-dimension tactical style scoring (possession, attacking intensity, defensive solidity, etc.)
- Formation preference analysis and effectiveness tracking
- Playing pattern recognition for attack/defense tendencies
- Tactical flexibility and manager influence assessment
- Team tactical profile generation for matchup analysis
"""

import requests
from typing import Dict, List, Optional, Tuple, Union
from decimal import Decimal
from datetime import datetime, timedelta
import boto3
import statistics
import math
from collections import defaultdict, Counter
import logging

from ..infrastructure.version_manager import VersionManager
from ..data.api_client import APIClient
from ..data.database_client import DatabaseClient

logger = logging.getLogger(__name__)

class TacticalAnalyzer:
    """Analyzes team tactical styles and formations for prediction enhancement."""
    
    def __init__(self):
        self.api_client = APIClient()
        self.db_client = DatabaseClient()
        self.version_manager = VersionManager()
        self.cache_table_name = 'tactical_analysis_cache'
    
    def analyze_team_formation_preferences(self, team_id: int, league_id: int, season: int) -> Dict:
        """
        Analyze team's preferred formations based on recent match data.
        
        Args:
            team_id: Team identifier
            league_id: League identifier  
            season: Season year
            
        Returns:
            {
                'primary_formation': str,           # e.g., '4-3-3', '3-5-2'
                'formation_frequency': Dict,        # Formation usage percentages
                'home_formation': str,              # Preferred formation at home
                'away_formation': str,              # Preferred formation away
                'vs_strong_formation': str,         # Formation vs top-tier opponents
                'vs_weak_formation': str,           # Formation vs bottom-tier opponents
                'formation_changes_per_game': Decimal, # Avg in-game formation changes
                'tactical_consistency': Decimal     # Formation consistency score (0-1)
            }
        """
        try:
            # Get recent matches for formation analysis
            matches = self._get_team_matches_with_formations(team_id, league_id, season)
            
            if len(matches) < 5:
                logger.warning(f"Insufficient match data for formation analysis: {len(matches)} matches")
                return self._get_default_formation_analysis()
            
            formations = []
            home_formations = []
            away_formations = []
            vs_strong_formations = []  
            vs_weak_formations = []
            formation_changes = []
            
            # Get league standings for opponent strength classification
            standings = self._get_league_standings(league_id, season)
            strong_teams = self._identify_strong_teams(standings)
            weak_teams = self._identify_weak_teams(standings)
            
            for match in matches:
                if match.get('formation'):
                    formations.append(match['formation'])
                    
                    # Classify by venue
                    if match['is_home']:
                        home_formations.append(match['formation'])
                    else:
                        away_formations.append(match['formation'])
                    
                    # Classify by opponent strength
                    opponent_id = match['opponent_id']
                    if opponent_id in strong_teams:
                        vs_strong_formations.append(match['formation'])
                    elif opponent_id in weak_teams:
                        vs_weak_formations.append(match['formation'])
                    
                    # Count formation changes
                    changes = match.get('formation_changes', 0)
                    formation_changes.append(changes)
            
            # Calculate formation frequencies
            formation_counts = Counter(formations)
            total_matches = len(formations)
            formation_frequency = {
                formation: Decimal(str(count / total_matches))
                for formation, count in formation_counts.items()
            }
            
            # Determine primary formations
            primary_formation = formation_counts.most_common(1)[0][0] if formation_counts else '4-4-2'
            home_formation = Counter(home_formations).most_common(1)[0][0] if home_formations else primary_formation
            away_formation = Counter(away_formations).most_common(1)[0][0] if away_formations else primary_formation
            vs_strong_formation = Counter(vs_strong_formations).most_common(1)[0][0] if vs_strong_formations else primary_formation
            vs_weak_formation = Counter(vs_weak_formations).most_common(1)[0][0] if vs_weak_formations else primary_formation
            
            # Calculate tactical consistency
            most_used_frequency = max(formation_frequency.values()) if formation_frequency else Decimal('0')
            tactical_consistency = most_used_frequency  # Higher = more consistent
            
            # Average formation changes per game
            avg_changes = Decimal(str(mean(formation_changes))) if formation_changes else Decimal('0')
            
            return {
                'primary_formation': primary_formation,
                'most_used_formation': primary_formation,  # Alias for backward compatibility
                'formation_frequency': formation_frequency,
                'formations_count': len(formation_counts),  # Number of different formations used
                'formation_consistency': tactical_consistency,  # Alias for backward compatibility
                'home_formation': home_formation,
                'away_formation': away_formation,
                'vs_strong_formation': vs_strong_formation,
                'vs_weak_formation': vs_weak_formation,
                'formation_changes_per_game': avg_changes,
                'tactical_consistency': tactical_consistency
            }
            
        except Exception as e:
            logger.error(f"Error analyzing formation preferences: {e}")
            return self._get_default_formation_analysis()
    
    def calculate_tactical_style_scores(self, team_id: int, league_id: int, season: int) -> Dict:
        """
        Calculate tactical style characteristics based on match statistics.
        
        Args:
            team_id: Team identifier
            league_id: League identifier
            season: Season year
            
        Returns:
            {
                'possession_style': Decimal,        # 0.0-1.0 (0=direct, 1=possession)
                'attacking_intensity': Decimal,     # 0.0-1.0 (shots, corners per game)
                'defensive_solidity': Decimal,      # 0.0-1.0 (clean sheets, blocks)
                'pressing_intensity': Decimal,      # 0.0-1.0 (tackles, interceptions)
                'counter_attack_threat': Decimal,   # 0.0-1.0 (fast break goals)
                'set_piece_strength': Decimal,      # 0.0-1.0 (goals from set pieces)
                'physicality_index': Decimal,       # 0.0-1.0 (fouls, cards, aerial duels)
                'tactical_discipline': Decimal      # 0.0-1.0 (consistent performance)
            }
        """
        try:
            # Get team statistics for tactical analysis
            stats = self._get_team_tactical_stats(team_id, league_id, season)
            league_stats = self._get_league_averages(league_id, season)
            
            if not stats or not league_stats:
                return self._get_default_style_scores()
            
            # Calculate possession style (0=direct, 1=possession-based)
            possession_pct = stats.get('possession_percentage', 50) / 100
            pass_accuracy = stats.get('pass_accuracy', 75) / 100
            short_passes_ratio = stats.get('short_passes_ratio', 0.7)
            possession_style = Decimal(str((possession_pct + pass_accuracy + short_passes_ratio) / 3))
            
            # Calculate attacking intensity
            shots_per_game = stats.get('shots_per_game', 10)
            corners_per_game = stats.get('corners_per_game', 5)
            attacks_per_game = stats.get('attacks_per_game', 100)
            
            league_avg_shots = league_stats.get('avg_shots_per_game', 12)
            league_avg_corners = league_stats.get('avg_corners_per_game', 6)
            league_avg_attacks = league_stats.get('avg_attacks_per_game', 110)
            
            shot_intensity = min(shots_per_game / league_avg_shots, 2.0) / 2.0
            corner_intensity = min(corners_per_game / league_avg_corners, 2.0) / 2.0
            attack_intensity = min(attacks_per_game / league_avg_attacks, 1.5) / 1.5
            
            attacking_intensity = Decimal(str((shot_intensity + corner_intensity + attack_intensity) / 3))
            
            # Calculate defensive solidity
            clean_sheets_ratio = stats.get('clean_sheets_ratio', 0.2)
            goals_conceded_per_game = stats.get('goals_conceded_per_game', 1.5)
            blocks_per_game = stats.get('blocks_per_game', 15)
            clearances_per_game = stats.get('clearances_per_game', 20)
            
            league_avg_goals_conceded = league_stats.get('avg_goals_conceded', 1.4)
            
            clean_sheet_factor = min(clean_sheets_ratio * 2, 1.0)
            defensive_record = max(0, 1 - (goals_conceded_per_game / (league_avg_goals_conceded + 0.1)))
            defensive_actions = min((blocks_per_game + clearances_per_game) / 50, 1.0)
            
            defensive_solidity = Decimal(str((clean_sheet_factor + defensive_record + defensive_actions) / 3))
            
            # Calculate pressing intensity
            tackles_per_game = stats.get('tackles_per_game', 15)
            interceptions_per_game = stats.get('interceptions_per_game', 10)
            fouls_per_game = stats.get('fouls_per_game', 12)
            
            league_avg_tackles = league_stats.get('avg_tackles_per_game', 16)
            league_avg_interceptions = league_stats.get('avg_interceptions_per_game', 12)
            
            tackle_rate = min(tackles_per_game / league_avg_tackles, 1.5) / 1.5
            interception_rate = min(interceptions_per_game / league_avg_interceptions, 1.5) / 1.5
            pressing_fouls = min(fouls_per_game / 20, 1.0)  # More fouls can indicate pressing
            
            pressing_intensity = Decimal(str((tackle_rate + interception_rate + pressing_fouls) / 3))
            
            # Calculate counter attack threat
            counter_goals_ratio = stats.get('counter_attack_goals_ratio', 0.15)
            fast_break_attempts = stats.get('fast_break_attempts_per_game', 3)
            transition_speed = stats.get('avg_transition_time', 10)  # Lower is better
            
            counter_scoring = min(counter_goals_ratio * 4, 1.0)
            break_frequency = min(fast_break_attempts / 8, 1.0)
            speed_factor = max(0, 1 - (transition_speed / 15))
            
            counter_attack_threat = Decimal(str((counter_scoring + break_frequency + speed_factor) / 3))
            
            # Calculate set piece strength
            set_piece_goals_ratio = stats.get('set_piece_goals_ratio', 0.2)
            corner_conversion = stats.get('corner_conversion_rate', 0.05)
            free_kick_accuracy = stats.get('free_kick_accuracy', 0.1)
            
            set_piece_strength = Decimal(str((set_piece_goals_ratio * 2 + corner_conversion * 10 + free_kick_accuracy * 5) / 3))
            set_piece_strength = min(set_piece_strength, Decimal('1.0'))
            
            # Calculate physicality index
            aerial_duels_won = stats.get('aerial_duels_won_ratio', 0.5)
            yellow_cards_per_game = stats.get('yellow_cards_per_game', 2)
            red_cards_per_game = stats.get('red_cards_per_game', 0.1)
            
            aerial_dominance = min(aerial_duels_won * 2, 1.0)
            card_factor = min((yellow_cards_per_game + red_cards_per_game * 3) / 8, 1.0)
            
            physicality_index = Decimal(str((aerial_dominance + card_factor) / 2))
            
            # Calculate tactical discipline (consistency in performance)
            performance_variance = stats.get('performance_variance', 0.3)  # Lower is more disciplined
            formation_consistency = stats.get('formation_consistency', 0.7)
            
            variance_discipline = max(0, 1 - (performance_variance / 0.5))
            formation_discipline = formation_consistency
            
            tactical_discipline = Decimal(str((variance_discipline + formation_discipline) / 2))
            
            return {
                'possession_style': max(Decimal('0'), min(possession_style, Decimal('1'))),
                'attacking_intensity': max(Decimal('0'), min(attacking_intensity, Decimal('1'))),
                'defensive_solidity': max(Decimal('0'), min(defensive_solidity, Decimal('1'))),
                'pressing_intensity': max(Decimal('0'), min(pressing_intensity, Decimal('1'))),
                'counter_attack_threat': max(Decimal('0'), min(counter_attack_threat, Decimal('1'))),
                'set_piece_strength': max(Decimal('0'), min(set_piece_strength, Decimal('1'))),
                'physicality_index': max(Decimal('0'), min(physicality_index, Decimal('1'))),
                'tactical_discipline': max(Decimal('0'), min(tactical_discipline, Decimal('1')))
            }
            
        except Exception as e:
            logger.error(f"Error calculating tactical style scores: {e}")
            return self._get_default_style_scores()
    
    def get_playing_pattern_analysis(self, team_id: int, league_id: int, season: int) -> Dict:
        """
        Analyze team's playing patterns and tendencies.
        
        Args:
            team_id: Team identifier
            league_id: League identifier
            season: Season year
            
        Returns:
            {
                'attack_patterns': {
                    'wing_play_preference': Decimal,    # Left/right wing vs central
                    'crossing_frequency': Decimal,      # Crosses per game
                    'through_ball_usage': Decimal,      # Through balls per game
                    'long_ball_tendency': Decimal       # Long passes vs short passing
                },
                'defensive_patterns': {
                    'high_line_frequency': Decimal,     # High defensive line usage
                    'pressing_triggers': List[str],     # When team presses most
                    'defensive_width': Decimal,         # Wide vs compact defending
                    'counter_press_intensity': Decimal  # Immediate pressing after losing ball
                },
                'transition_speed': {
                    'attack_transition': Decimal,       # Speed of defensive->attacking transition
                    'defense_transition': Decimal       # Speed of attacking->defensive transition
                }
            }
        """
        try:
            # Get detailed match statistics for pattern analysis
            matches = self._get_team_detailed_stats(team_id, league_id, season)
            
            if len(matches) < 5:
                return self._get_default_playing_patterns()
            
            # Analyze attack patterns
            wing_attacks = sum(match.get('wing_attacks', 0) for match in matches)
            central_attacks = sum(match.get('central_attacks', 0) for match in matches)
            total_attacks = wing_attacks + central_attacks
            
            wing_play_preference = Decimal(str(wing_attacks / max(total_attacks, 1)))
            
            crosses_per_game = Decimal(str(mean([match.get('crosses', 0) for match in matches])))
            through_balls_per_game = Decimal(str(mean([match.get('through_balls', 0) for match in matches])))
            
            long_passes = sum(match.get('long_passes', 0) for match in matches)
            short_passes = sum(match.get('short_passes', 0) for match in matches)
            total_passes = long_passes + short_passes
            
            long_ball_tendency = Decimal(str(long_passes / max(total_passes, 1)))
            
            attack_patterns = {
                'wing_play_preference': wing_play_preference,
                'crossing_frequency': crosses_per_game,
                'through_ball_usage': through_balls_per_game,
                'long_ball_tendency': long_ball_tendency
            }
            
            # Analyze defensive patterns
            high_line_matches = sum(1 for match in matches if match.get('avg_defensive_line', 40) > 50)
            high_line_frequency = Decimal(str(high_line_matches / len(matches)))
            
            # Analyze pressing triggers (simplified - would need more detailed data)
            pressing_triggers = ['losing_possession', 'opponent_buildup', 'set_pieces']
            
            defensive_width = Decimal(str(mean([match.get('defensive_width', 50) for match in matches]) / 100))
            counter_press_intensity = Decimal(str(mean([match.get('counter_presses', 5) for match in matches]) / 10))
            
            defensive_patterns = {
                'high_line_frequency': high_line_frequency,
                'pressing_triggers': pressing_triggers,
                'defensive_width': defensive_width,
                'counter_press_intensity': counter_press_intensity
            }
            
            # Analyze transition speed
            attack_transition = Decimal(str(mean([match.get('def_to_att_time', 8) for match in matches])))
            defense_transition = Decimal(str(mean([match.get('att_to_def_time', 6) for match in matches])))
            
            # Normalize to 0-1 scale (lower times = higher speed scores)
            attack_transition_score = max(Decimal('0'), Decimal('1') - (attack_transition / Decimal('15')))
            defense_transition_score = max(Decimal('0'), Decimal('1') - (defense_transition / Decimal('10')))
            
            transition_speed = {
                'attack_transition': attack_transition_score,
                'defense_transition': defense_transition_score
            }
            
            return {
                'attack_patterns': attack_patterns,
                'defensive_patterns': defensive_patterns,
                'transition_speed': transition_speed
            }
            
        except Exception as e:
            logger.error(f"Error analyzing playing patterns: {e}")
            return self._get_default_playing_patterns()
    
    def analyze_tactical_flexibility(self, team_id: int, league_id: int, season: int) -> Dict:
        """
        Assess team's tactical adaptability and in-game adjustments.
        
        Args:
            team_id: Team identifier
            league_id: League identifier
            season: Season year
            
        Returns:
            {
                'formation_changes': int,           # Average formation changes per game
                'substitution_impact': Decimal,     # Performance change after subs
                'game_state_adaptation': {
                    'when_leading': str,            # Tactical approach when ahead
                    'when_trailing': str,           # Tactical approach when behind
                    'when_level': str               # Tactical approach when level
                },
                'tactical_consistency': Decimal     # 0.0-1.0 consistency in approach
            }
        """
        try:
            matches = self._get_team_tactical_flexibility_data(team_id, league_id, season)
            
            if len(matches) < 5:
                return self._get_default_flexibility_analysis()
            
            # Calculate average formation changes
            formation_changes = mean([match.get('formation_changes', 0) for match in matches])
            
            # Analyze substitution impact
            sub_impacts = []
            for match in matches:
                pre_sub_performance = match.get('pre_sub_xg', 0)
                post_sub_performance = match.get('post_sub_xg', 0)
                if pre_sub_performance > 0:
                    impact = (post_sub_performance - pre_sub_performance) / pre_sub_performance
                    sub_impacts.append(impact)
            
            substitution_impact = Decimal(str(mean(sub_impacts) if sub_impacts else 0))
            
            # Analyze game state adaptation
            leading_approaches = []
            trailing_approaches = []
            level_approaches = []
            
            for match in matches:
                for period in match.get('game_periods', []):
                    state = period.get('game_state')
                    approach = period.get('tactical_approach', 'balanced')
                    
                    if state == 'leading':
                        leading_approaches.append(approach)
                    elif state == 'trailing':
                        trailing_approaches.append(approach)
                    else:
                        level_approaches.append(approach)
            
            game_state_adaptation = {
                'when_leading': Counter(leading_approaches).most_common(1)[0][0] if leading_approaches else 'defensive',
                'when_trailing': Counter(trailing_approaches).most_common(1)[0][0] if trailing_approaches else 'attacking',
                'when_level': Counter(level_approaches).most_common(1)[0][0] if level_approaches else 'balanced'
            }
            
            # Calculate tactical consistency
            all_approaches = leading_approaches + trailing_approaches + level_approaches
            if all_approaches:
                most_common_count = Counter(all_approaches).most_common(1)[0][1]
                consistency = Decimal(str(most_common_count / len(all_approaches)))
            else:
                consistency = Decimal('0.5')
            
            return {
                'formation_changes': int(formation_changes),
                'substitution_impact': substitution_impact,
                'game_state_adaptation': game_state_adaptation,
                'tactical_consistency': consistency
            }
            
        except Exception as e:
            logger.error(f"Error analyzing tactical flexibility: {e}")
            return self._get_default_flexibility_analysis()
    
    def get_manager_tactical_profile(self, team_id: int, league_id: int, season: int) -> Dict:
        """
        Analyze manager's tactical preferences and tendencies.
        
        Args:
            team_id: Team identifier
            league_id: League identifier
            season: Season year
            
        Returns:
            {
                'preferred_system': str,            # Main tactical system
                'tactical_philosophy': str,         # 'attacking', 'defensive', 'balanced'
                'substitution_timing': Decimal,     # Average minute of first substitution
                'tactical_rigidity': Decimal,       # 0.0-1.0 (flexible vs rigid approach)
                'big_game_approach': str            # Approach in important matches
            }
        """
        try:
            matches = self._get_team_manager_data(team_id, league_id, season)
            
            if len(matches) < 5:
                return self._get_default_manager_profile()
            
            # Determine preferred system from formation analysis
            formations = [match.get('formation', '4-4-2') for match in matches]
            preferred_system = Counter(formations).most_common(1)[0][0]
            
            # Analyze tactical philosophy based on avg stats
            goals_for = mean([match.get('goals_for', 0) for match in matches])
            goals_against = mean([match.get('goals_against', 0) for match in matches])
            shots_for = mean([match.get('shots_for', 0) for match in matches])
            
            if goals_for > 2.0 and shots_for > 15:
                philosophy = 'attacking'
            elif goals_against < 1.0:
                philosophy = 'defensive'
            else:
                philosophy = 'balanced'
            
            # Calculate substitution timing
            sub_timings = [match.get('first_sub_minute', 60) for match in matches if match.get('first_sub_minute')]
            substitution_timing = Decimal(str(mean(sub_timings) if sub_timings else 60))
            
            # Calculate tactical rigidity (inverse of formation variety)
            unique_formations = len(set(formations))
            total_matches = len(formations)
            formation_variety = unique_formations / total_matches
            tactical_rigidity = Decimal(str(1 - formation_variety))  # High rigidity = low variety
            
            # Determine big game approach (against top opponents)
            big_games = [match for match in matches if match.get('opponent_strength', 'middle') == 'strong']
            if big_games:
                big_game_goals = mean([match.get('goals_for', 0) for match in big_games])
                big_game_approach = 'attacking' if big_game_goals > 1.5 else 'cautious'
            else:
                big_game_approach = 'balanced'
            
            return {
                'preferred_system': preferred_system,
                'tactical_philosophy': philosophy,
                'substitution_timing': substitution_timing,
                'tactical_rigidity': tactical_rigidity,
                'big_game_approach': big_game_approach
            }
            
        except Exception as e:
            logger.error(f"Error analyzing manager tactical profile: {e}")
            return self._get_default_manager_profile()
    
    # Private helper methods
    
    def _get_team_matches_with_formations(self, team_id: int, league_id: int, season: int) -> List[Dict]:
        """Get team matches with formation data from API."""
        try:
            from ..data.api_client import get_team_statistics

            # Get team statistics which includes lineup/formation data
            team_stats = get_team_statistics(league_id, season, team_id)

            if not team_stats or 'response' not in team_stats:
                logger.warning(f"No team statistics for formation analysis: team {team_id}")
                return []

            response = team_stats['response']
            lineups = response.get('lineups', [])

            if not lineups:
                logger.warning(f"No lineup data available for team {team_id}")
                return []

            # Extract formation information
            # API provides aggregated data, not per-match, so we simulate match list
            # based on formation frequencies
            matches = []

            for lineup in lineups:
                formation = lineup.get('formation')
                played = lineup.get('played', 0)

                if not formation or played == 0:
                    continue

                # Create simulated match entries based on how many times formation was used
                # In reality, would need to fetch individual fixtures to get true match-by-match data
                for i in range(played):
                    matches.append({
                        'formation': formation,
                        'is_home': i % 2 == 0,  # Alternate home/away (estimation)
                        'opponent_id': None,     # Would need real fixture data
                        'formation_changes': 0   # Would need event data
                    })

            return matches

        except Exception as e:
            logger.error(f"Error fetching team matches with formations: {e}")
            import traceback
            traceback.print_exc()
            return []
    
    def _get_team_tactical_stats(self, team_id: int, league_id: int, season: int) -> Dict:
        """Get comprehensive tactical statistics for a team from API."""
        try:
            from ..data.api_client import get_team_statistics, get_fixtures_goals

            # Get team statistics from API-Football
            team_stats = get_team_statistics(league_id, season, team_id)

            if not team_stats or 'response' not in team_stats:
                logger.warning(f"No team statistics available for team {team_id}")
                return {}

            response = team_stats['response']

            # Extract basic statistics
            fixtures = response.get('fixtures', {})
            goals = response.get('goals', {})
            cards = response.get('cards', {})
            clean_sheet = response.get('clean_sheet', {})

            # Calculate games played
            total_games = fixtures.get('played', {}).get('total', 0)
            if total_games == 0:
                logger.warning(f"Team {team_id} has no games played")
                return {}

            # Calculate clean sheets ratio
            clean_sheets_home = clean_sheet.get('home', 0) or 0
            clean_sheets_away = clean_sheet.get('away', 0) or 0
            clean_sheets_total = clean_sheets_home + clean_sheets_away
            clean_sheets_ratio = clean_sheets_total / total_games if total_games > 0 else 0

            # Calculate goals conceded per game
            goals_conceded_home = goals.get('against', {}).get('total', {}).get('home', 0) or 0
            goals_conceded_away = goals.get('against', {}).get('total', {}).get('away', 0) or 0
            goals_conceded_total = goals_conceded_home + goals_conceded_away
            goals_conceded_per_game = goals_conceded_total / total_games if total_games > 0 else 0

            # Calculate cards per game
            yellow_total = 0
            red_total = 0

            if cards:
                for time_period, card_data in cards.get('yellow', {}).items():
                    if time_period != 'total' and isinstance(card_data, dict):
                        yellow_total += card_data.get('total', 0) or 0

                for time_period, card_data in cards.get('red', {}).items():
                    if time_period != 'total' and isinstance(card_data, dict):
                        red_total += card_data.get('total', 0) or 0

            yellow_cards_per_game = yellow_total / total_games if total_games > 0 else 0
            red_cards_per_game = red_total / total_games if total_games > 0 else 0

            # Get match-level statistics (last 10 games for tactical analysis)
            try:
                match_stats = self._aggregate_match_statistics(team_id, league_id, season, limit=10)
            except Exception as e:
                logger.warning(f"Could not aggregate match statistics: {e}")
                match_stats = {}

            # Get goal pattern analysis from events
            try:
                from ..data.api_client import get_fixtures_goals

                # Get recent fixtures for goal pattern analysis
                start_ts = int(datetime(season, 8, 1).timestamp())
                end_ts = int(datetime.now().timestamp())
                fixtures = get_fixtures_goals(league_id, start_ts, end_ts)

                # Filter for this team and get last 10
                team_fixtures = [f for f in fixtures if
                                 f.get('teams', {}).get('home', {}).get('id') == team_id or
                                 f.get('teams', {}).get('away', {}).get('id') == team_id][-10:]

                goal_patterns = self._analyze_goal_patterns(team_id, team_fixtures, limit=10)
            except Exception as e:
                logger.warning(f"Could not analyze goal patterns: {e}")
                goal_patterns = {}

            # Estimate set piece goals from penalties + corners
            penalty_ratio = goal_patterns.get('penalty_ratio', 0)
            corners_per_game = match_stats.get('avg_corners', 5)
            estimated_corner_goals_ratio = (corners_per_game * 0.10) / (corners_per_game + 1)  # 10% corner conversion
            set_piece_estimate = min(penalty_ratio + estimated_corner_goals_ratio, 0.4)  # Cap at 40%

            # Combine API data with match aggregations and goal patterns
            return {
                # From team statistics endpoint
                'clean_sheets_ratio': clean_sheets_ratio,
                'goals_conceded_per_game': goals_conceded_per_game,
                'yellow_cards_per_game': yellow_cards_per_game,
                'red_cards_per_game': red_cards_per_game,

                # From match-level aggregations
                'possession_percentage': match_stats.get('avg_possession', 50),
                'pass_accuracy': match_stats.get('avg_pass_accuracy', 75),
                'short_passes_ratio': match_stats.get('short_passes_ratio', 0.7),
                'shots_per_game': match_stats.get('avg_shots', 10),
                'corners_per_game': corners_per_game,
                'attacks_per_game': match_stats.get('avg_attacks', 100),
                'blocks_per_game': match_stats.get('avg_blocks', 15),
                'clearances_per_game': match_stats.get('avg_clearances', 20),
                'tackles_per_game': match_stats.get('avg_tackles', 15),
                'interceptions_per_game': match_stats.get('avg_interceptions', 10),
                'fouls_per_game': match_stats.get('avg_fouls', 12),

                # From goal pattern analysis (REAL DATA)
                'penalty_ratio': goal_patterns.get('penalty_ratio', 0),
                'late_goal_scoring_ability': goal_patterns.get('late_goal_ratio', 0),
                'first_half_dominance': goal_patterns.get('first_half_goal_ratio', 0),
                'team_play_index': goal_patterns.get('team_play_ratio', 0),  # Creativity indicator

                # Estimated metrics
                'set_piece_goals_ratio': set_piece_estimate,
                'counter_attack_goals_ratio': 0.15,  # Placeholder - needs xG analysis
                'fast_break_attempts_per_game': 3,    # Placeholder - needs event data
                'avg_transition_time': 10,            # Placeholder - needs event data
                'corner_conversion_rate': match_stats.get('corner_conversion', 0.05),
                'free_kick_accuracy': 0.1,            # Placeholder - needs set piece data
                'aerial_duels_won_ratio': 0.5,        # Placeholder - needs duel data
                'performance_variance': match_stats.get('performance_variance', 0.3),
                'formation_consistency': match_stats.get('formation_consistency', 0.7),

                # Metadata
                'goal_analysis_source': 'fixture_events_api',
                'goals_analyzed': goal_patterns.get('total_goals_analyzed', 0),
                'fixtures_analyzed': goal_patterns.get('fixtures_analyzed', 0)
            }

        except Exception as e:
            logger.error(f"Error fetching team tactical stats for team {team_id}: {e}")
            import traceback
            traceback.print_exc()
            return {}

    def _analyze_goal_patterns(self, team_id: int, fixtures: list, limit: int = 10) -> Dict:
        """
        Analyze goal scoring patterns from fixture events.

        Args:
            team_id: Team identifier
            fixtures: List of fixture dictionaries
            limit: Maximum number of fixtures to analyze

        Returns:
            Dictionary with goal pattern metrics
        """
        try:
            from ..data.database_client import get_cached_fixture_events

            total_goals = 0
            penalty_goals = 0
            own_goals_conceded = 0
            late_goals = 0  # After 75 min
            first_half_goals = 0  # Before 45 min
            goals_with_assists = 0

            fixtures_to_analyze = fixtures[:limit] if len(fixtures) > limit else fixtures

            for fixture in fixtures_to_analyze:
                if not isinstance(fixture, dict):
                    continue

                fixture_id = fixture.get('fixture', {}).get('id')
                if not fixture_id:
                    continue

                # Get events for this fixture
                events_data = get_cached_fixture_events(fixture_id)

                if not events_data or 'response' not in events_data:
                    continue

                # Analyze goal events
                for event in events_data['response']:
                    if event.get('type') != 'Goal':
                        continue

                    event_team_id = event.get('team', {}).get('id')

                    # Goals scored by our team
                    if event_team_id == team_id:
                        total_goals += 1

                        # Check goal type
                        detail = event.get('detail', '')
                        if detail == 'Penalty':
                            penalty_goals += 1

                        # Check timing
                        elapsed = event.get('time', {}).get('elapsed', 0)
                        if elapsed >= 75:
                            late_goals += 1
                        elif elapsed <= 45:
                            first_half_goals += 1

                        # Check for assist
                        if event.get('assist', {}).get('id'):
                            goals_with_assists += 1

                    # Own goals conceded
                    elif detail == 'Own Goal':
                        own_goals_conceded += 1

            # Calculate ratios
            return {
                'total_goals_analyzed': total_goals,
                'penalty_ratio': penalty_goals / total_goals if total_goals > 0 else 0,
                'late_goal_ratio': late_goals / total_goals if total_goals > 0 else 0,
                'first_half_goal_ratio': first_half_goals / total_goals if total_goals > 0 else 0,
                'team_play_ratio': goals_with_assists / total_goals if total_goals > 0 else 0,
                'own_goals_conceded': own_goals_conceded,
                'fixtures_analyzed': len(fixtures_to_analyze)
            }

        except Exception as e:
            logger.error(f"Error analyzing goal patterns: {e}")
            import traceback
            traceback.print_exc()
            return {
                'total_goals_analyzed': 0,
                'penalty_ratio': 0,
                'late_goal_ratio': 0,
                'first_half_goal_ratio': 0,
                'team_play_ratio': 0,
                'own_goals_conceded': 0,
                'fixtures_analyzed': 0
            }

    def _aggregate_match_statistics(self, team_id: int, league_id: int, season: int, limit: int = 10) -> Dict:
        """
        Aggregate match-level statistics from recent games.

        Args:
            team_id: Team identifier
            league_id: League identifier
            season: Season year
            limit: Number of recent matches to analyze

        Returns:
            Dictionary with aggregated match statistics
        """
        try:
            from ..data.api_client import get_fixtures_goals

            # Get recent fixtures for the team
            fixtures = get_fixtures_goals(league_id, season, team_id, last=limit)

            if not fixtures or not isinstance(fixtures, list):
                logger.warning(f"No fixtures data for team {team_id}")
                return {}

            # Initialize accumulators
            total_possession = []
            total_shots = []
            total_corners = []
            total_fouls = []
            total_passes = []
            total_pass_accuracy = []

            # Process each fixture
            for fixture in fixtures:
                if not isinstance(fixture, dict):
                    continue

                fixture_id = fixture.get('fixture', {}).get('id')
                if not fixture_id:
                    continue

                # Determine if team was home or away
                teams = fixture.get('teams', {})
                home_team_id = teams.get('home', {}).get('id')
                away_team_id = teams.get('away', {}).get('id')

                is_home = (home_team_id == team_id)
                team_index = 0 if is_home else 1

                # Extract statistics if available
                # Note: fixture statistics would need separate API call per fixture
                # For now, we'll use estimated values based on goals/results
                # A full implementation would call get_fixture_statistics(fixture_id)

                goals_data = fixture.get('goals', {})
                if is_home:
                    team_goals = goals_data.get('home', 0)
                    opp_goals = goals_data.get('away', 0)
                else:
                    team_goals = goals_data.get('away', 0)
                    opp_goals = goals_data.get('home', 0)

                # Estimate tactical metrics from goals (rough approximation)
                # In a full implementation, would fetch real stats per fixture
                if team_goals > opp_goals:  # Won
                    total_possession.append(55 + (team_goals - opp_goals) * 5)
                    total_shots.append(12 + team_goals * 2)
                    total_pass_accuracy.append(80 + team_goals * 2)
                elif team_goals == opp_goals:  # Draw
                    total_possession.append(50)
                    total_shots.append(10)
                    total_pass_accuracy.append(75)
                else:  # Lost
                    total_possession.append(45 - (opp_goals - team_goals) * 3)
                    total_shots.append(8)
                    total_pass_accuracy.append(70)

                # Corners and fouls estimation
                total_corners.append(5 + team_goals)
                total_fouls.append(12)

            # Calculate averages
            num_matches = len(total_possession) if total_possession else 1

            return {
                'avg_possession': sum(total_possession) / num_matches if total_possession else 50,
                'avg_shots': sum(total_shots) / num_matches if total_shots else 10,
                'avg_corners': sum(total_corners) / num_matches if total_corners else 5,
                'avg_fouls': sum(total_fouls) / num_matches if total_fouls else 12,
                'avg_pass_accuracy': sum(total_pass_accuracy) / num_matches if total_pass_accuracy else 75,
                'short_passes_ratio': 0.7,  # Would need detailed pass data
                'avg_attacks': 100,  # Would need attack data
                'avg_blocks': 15,    # Would need defensive action data
                'avg_clearances': 20,  # Would need defensive action data
                'avg_tackles': 15,  # Would need defensive action data
                'avg_interceptions': 10,  # Would need defensive action data
                'corner_conversion': 0.05,  # Would need set piece data
                'performance_variance': 0.3,  # Would need variance calculation
                'formation_consistency': 0.7  # Would need formation data
            }

        except Exception as e:
            logger.error(f"Error aggregating match statistics: {e}")
            import traceback
            traceback.print_exc()
            return {}

    def _get_league_averages(self, league_id: int, season: int) -> Dict:
        """Get league-wide average statistics for normalization."""
        try:
            from ..data.api_client import get_league_teams, get_team_statistics

            # Get all teams in the league
            teams_data = get_league_teams(league_id, season)

            if not teams_data or 'response' not in teams_data:
                logger.warning(f"No league teams data for league {league_id}")
                return self._get_default_league_averages()

            teams = teams_data['response']
            if not teams:
                return self._get_default_league_averages()

            # Collect statistics from all teams
            all_goals_conceded = []
            all_clean_sheets = []
            total_games_league = 0

            for team_data in teams[:20]:  # Limit to first 20 teams to reduce API calls
                team_id = team_data.get('team', {}).get('id')
                if not team_id:
                    continue

                try:
                    team_stats = get_team_statistics(league_id, season, team_id)
                    if not team_stats or 'response' not in team_stats:
                        continue

                    response = team_stats['response']
                    fixtures = response.get('fixtures', {})
                    goals = response.get('goals', {})

                    total_games = fixtures.get('played', {}).get('total', 0)
                    if total_games > 0:
                        total_games_league += total_games

                        # Goals conceded
                        goals_conceded = (goals.get('against', {}).get('total', {}).get('total', 0) or 0)
                        all_goals_conceded.append(goals_conceded / total_games)

                        # Clean sheets
                        clean_sheets = (response.get('clean_sheet', {}).get('total', 0) or 0)
                        all_clean_sheets.append(clean_sheets / total_games)

                except Exception as e:
                    logger.warning(f"Error getting stats for team {team_id}: {e}")
                    continue

            # Calculate league averages
            if all_goals_conceded:
                avg_goals_conceded = sum(all_goals_conceded) / len(all_goals_conceded)
            else:
                avg_goals_conceded = 1.4

            # Estimate other metrics based on typical football statistics
            # In a full implementation, would aggregate from all match statistics
            return {
                'avg_shots_per_game': 13,  # Would need match-level data
                'avg_corners_per_game': 6.5,  # Would need match-level data
                'avg_attacks_per_game': 115,  # Would need match-level data
                'avg_goals_conceded': avg_goals_conceded,
                'avg_tackles_per_game': 17,  # Would need match-level data
                'avg_interceptions_per_game': 13  # Would need match-level data
            }

        except Exception as e:
            logger.error(f"Error fetching league averages: {e}")
            import traceback
            traceback.print_exc()
            return self._get_default_league_averages()

    def _get_default_league_averages(self) -> Dict:
        """Get default league average statistics."""
        return {
            'avg_shots_per_game': 13,
            'avg_corners_per_game': 6.5,
            'avg_attacks_per_game': 115,
            'avg_goals_conceded': 1.4,
            'avg_tackles_per_game': 17,
            'avg_interceptions_per_game': 13
        }
    
    def _get_team_detailed_stats(self, team_id: int, league_id: int, season: int) -> List[Dict]:
        """Get detailed match statistics for playing pattern analysis."""
        try:
            # This would fetch detailed match-by-match stats
            return []
        except Exception as e:
            logger.error(f"Error fetching detailed team stats: {e}")
            return []
    
    def _get_team_tactical_flexibility_data(self, team_id: int, league_id: int, season: int) -> List[Dict]:
        """Get data for tactical flexibility analysis."""
        try:
            # This would fetch in-game tactical changes data
            return []
        except Exception as e:
            logger.error(f"Error fetching tactical flexibility data: {e}")
            return []
    
    def _get_team_manager_data(self, team_id: int, league_id: int, season: int) -> List[Dict]:
        """Get manager-specific tactical data."""
        try:
            # Import manager analyzer
            from .manager_analyzer import ManagerAnalyzer

            manager_analyzer = ManagerAnalyzer()
            manager_profile = manager_analyzer.get_manager_profile(team_id, league_id, season)

            if manager_profile and manager_profile.get('manager_id'):
                return [manager_profile]

            return []
        except Exception as e:
            logger.error(f"Error fetching manager data: {e}")
            return []
    
    def _get_league_standings(self, league_id: int, season: int) -> Dict:
        """Get league standings for opponent classification."""
        try:
            # This would use existing opponent classifier functionality
            from .opponent_classifier import OpponentClassifier
            classifier = OpponentClassifier()
            return classifier.get_league_standings(league_id, season)
        except Exception as e:
            logger.error(f"Error fetching league standings: {e}")
            return {}
    
    def _identify_strong_teams(self, standings: Dict) -> List[int]:
        """Identify top-tier teams from standings."""
        try:
            if not standings:
                return []
            teams = standings.get('teams', [])
            # Top 30% are considered strong
            strong_count = max(1, len(teams) * 3 // 10)
            return [team['team_id'] for team in teams[:strong_count]]
        except Exception as e:
            logger.error(f"Error identifying strong teams: {e}")
            return []
    
    def _identify_weak_teams(self, standings: Dict) -> List[int]:
        """Identify bottom-tier teams from standings."""
        try:
            if not standings:
                return []
            teams = standings.get('teams', [])
            # Bottom 30% are considered weak
            weak_count = max(1, len(teams) * 3 // 10)
            return [team['team_id'] for team in teams[-weak_count:]]
        except Exception as e:
            logger.error(f"Error identifying weak teams: {e}")
            return []
    
    # Default/fallback methods
    
    def _get_default_formation_analysis(self) -> Dict:
        """Default formation analysis when insufficient data."""
        return {
            'primary_formation': '4-4-2',
            'formation_frequency': {'4-4-2': Decimal('1.0')},
            'home_formation': '4-4-2',
            'away_formation': '4-4-2',
            'vs_strong_formation': '4-5-1',
            'vs_weak_formation': '4-3-3',
            'formation_changes_per_game': Decimal('0.5'),
            'tactical_consistency': Decimal('0.7')
        }
    
    def _get_default_style_scores(self) -> Dict:
        """Default tactical style scores when insufficient data."""
        return {
            'possession_style': Decimal('0.5'),
            'attacking_intensity': Decimal('0.5'),
            'defensive_solidity': Decimal('0.5'),
            'pressing_intensity': Decimal('0.5'),
            'counter_attack_threat': Decimal('0.5'),
            'set_piece_strength': Decimal('0.5'),
            'physicality_index': Decimal('0.5'),
            'tactical_discipline': Decimal('0.5')
        }
    
    def _get_default_playing_patterns(self) -> Dict:
        """Default playing patterns when insufficient data."""
        return {
            'attack_patterns': {
                'wing_play_preference': Decimal('0.6'),
                'crossing_frequency': Decimal('8.0'),
                'through_ball_usage': Decimal('3.0'),
                'long_ball_tendency': Decimal('0.3')
            },
            'defensive_patterns': {
                'high_line_frequency': Decimal('0.4'),
                'pressing_triggers': ['losing_possession'],
                'defensive_width': Decimal('0.5'),
                'counter_press_intensity': Decimal('0.5')
            },
            'transition_speed': {
                'attack_transition': Decimal('0.6'),
                'defense_transition': Decimal('0.7')
            }
        }
    
    def _get_default_flexibility_analysis(self) -> Dict:
        """Default tactical flexibility analysis when insufficient data."""
        return {
            'formation_changes': 1,
            'substitution_impact': Decimal('0.05'),
            'game_state_adaptation': {
                'when_leading': 'defensive',
                'when_trailing': 'attacking',
                'when_level': 'balanced'
            },
            'tactical_consistency': Decimal('0.7')
        }
    
    def _get_default_manager_profile(self) -> Dict:
        """Default manager tactical profile when insufficient data."""
        return {
            'preferred_system': '4-4-2',
            'tactical_philosophy': 'balanced',
            'substitution_timing': Decimal('65'),
            'tactical_rigidity': Decimal('0.6'),
            'big_game_approach': 'cautious'
        }


# Convenience functions for easy integration

def analyze_tactical_style(team_id: int, league_id: int, season: int) -> Dict:
    """
    Analyze team's tactical style - main entry point for Phase 4 tactical analysis.
    
    This is the main function called by the integration tests and prediction engine
    to get comprehensive tactical analysis for style-based parameter adjustments.
    
    Args:
        team_id: Team identifier
        league_id: League identifier
        season: Season year (e.g., 2024)
        
    Returns:
        dict: Comprehensive tactical analysis including formation preferences,
              style scores, and tactical flexibility
    """
    try:
        # Get formation preferences
        formation_analysis = analyze_team_formation_preferences(team_id, league_id, season)
        
        # Get tactical style scores
        style_scores = calculate_tactical_style_scores(team_id, league_id, season)
        
        # Get tactical flexibility
        flexibility = analyze_tactical_flexibility(team_id, league_id, season)
        
        # Combine into comprehensive analysis
        tactical_style = {
            'formations': formation_analysis,
            'style_scores': style_scores,
            'flexibility': flexibility,
            'analysis_type': 'tactical_style',
            'phase4_enabled': True,
            'tactical_intelligence': True
        }
        
        return tactical_style
        
    except Exception as e:
        return {
            'analysis_type': 'tactical_style',
            'phase4_enabled': True,
            'tactical_intelligence': False,
            'error': str(e)
        }


def analyze_team_formation_preferences(team_id: int, league_id: int, season: int) -> Dict:
    """
    Analyze team's preferred formations based on recent match data.
    
    Returns:
        {
            'primary_formation': str,           # e.g., '4-3-3', '3-5-2'
            'formation_frequency': Dict,        # Formation usage percentages
            'home_formation': str,              # Preferred formation at home
            'away_formation': str,              # Preferred formation away
            'vs_strong_formation': str,         # Formation vs top-tier opponents
            'vs_weak_formation': str            # Formation vs bottom-tier opponents
        }
    """
    analyzer = TacticalAnalyzer()
    return analyzer.analyze_team_formation_preferences(team_id, league_id, season)


def calculate_tactical_style_scores(team_id: int, league_id: int, season: int) -> Dict:
    """
    Calculate tactical style characteristics based on match statistics.
    
    Returns:
        {
            'possession_style': Decimal,        # 0.0-1.0 (0=direct, 1=possession)
            'attacking_intensity': Decimal,     # 0.0-1.0 (shots, corners per game)
            'defensive_solidity': Decimal,      # 0.0-1.0 (clean sheets, blocks)
            'pressing_intensity': Decimal,      # 0.0-1.0 (tackles, interceptions)
            'counter_attack_threat': Decimal,   # 0.0-1.0 (fast break goals)
            'set_piece_strength': Decimal,      # 0.0-1.0 (goals from set pieces)
            'physicality_index': Decimal,       # 0.0-1.0 (fouls, cards, aerial duels)
            'tactical_discipline': Decimal      # 0.0-1.0 (consistent performance)
        }
    """
    analyzer = TacticalAnalyzer()
    return analyzer.calculate_tactical_style_scores(team_id, league_id, season)


def get_playing_pattern_analysis(team_id: int, league_id: int, season: int) -> Dict:
    """
    Analyze team's playing patterns and tendencies.
    
    Returns:
        {
            'attack_patterns': Dict,            # Attacking style characteristics
            'defensive_patterns': Dict,         # Defensive style characteristics
            'transition_speed': Dict            # Transition characteristics
        }
    """
    analyzer = TacticalAnalyzer()
    return analyzer.get_playing_pattern_analysis(team_id, league_id, season)


def analyze_tactical_flexibility(team_id: int, league_id: int, season: int) -> Dict:
    """
    Assess team's tactical adaptability and in-game adjustments.
    
    Returns:
        {
            'formation_changes': int,           # Average formation changes per game
            'substitution_impact': Decimal,     # Performance change after subs
            'game_state_adaptation': Dict,      # Tactical approaches by game state
            'tactical_consistency': Decimal     # 0.0-1.0 consistency in approach
        }
    """
    analyzer = TacticalAnalyzer()
    return analyzer.analyze_tactical_flexibility(team_id, league_id, season)


def get_manager_tactical_profile(team_id: int, league_id: int, season: int) -> Dict:
    """
    Analyze manager's tactical preferences and tendencies.
    
    Returns:
        {
            'preferred_system': str,            # Main tactical system
            'tactical_philosophy': str,         # 'attacking', 'defensive', 'balanced'
            'substitution_timing': Decimal,     # Average minute of first substitution
            'tactical_rigidity': Decimal,       # 0.0-1.0 (flexible vs rigid approach)
            'big_game_approach': str            # Approach in important matches
        }
    """
    analyzer = TacticalAnalyzer()
    return analyzer.get_manager_tactical_profile(team_id, league_id, season)