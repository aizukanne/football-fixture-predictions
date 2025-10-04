"""
tactical_matchups.py - Tactical matchup analysis between teams

Phase 4: Derived Tactical Style Features
Analyzes how team tactical styles interact and create advantages/disadvantages in specific matchups.
Provides sophisticated tactical intelligence for enhanced prediction accuracy.

This module provides:
- Style vs style effectiveness analysis
- Formation matchup compatibility assessment
- Historical tactical outcome analysis
- Tactical adjustment prediction
- Matchup-specific advantage identification
"""

import math
from typing import Dict, List, Optional, Tuple, Union
from decimal import Decimal
from datetime import datetime, timedelta
from collections import defaultdict, Counter
import logging

from ..infrastructure.version_manager import VersionManager
from ..data.database_client import DatabaseClient
from .tactical_analyzer import TacticalAnalyzer

logger = logging.getLogger(__name__)

class TacticalMatchupAnalyzer:
    """Analyzes tactical matchups between teams for prediction enhancement."""
    
    def __init__(self):
        self.db_client = DatabaseClient()
        self.version_manager = VersionManager()
        self.tactical_analyzer = TacticalAnalyzer()
    
    def analyze_tactical_compatibility(self, home_team_id: int, away_team_id: int, 
                                     league_id: int, season: int) -> Dict:
        """
        Analyze how team tactical styles interact and create advantages/disadvantages.
        
        Args:
            home_team_id: Home team identifier
            away_team_id: Away team identifier
            league_id: League identifier
            season: Season year
            
        Returns:
            {
                'style_matchup': {
                    'possession_advantage': str,     # 'home'|'away'|'neutral'
                    'pressing_effectiveness': str,   # Which team's press more effective
                    'counter_attack_threat': str,    # Which team has counter advantage
                    'set_piece_advantage': str       # Which team stronger at set pieces
                },
                'formation_compatibility': {
                    'width_advantage': str,          # Wide vs narrow formation matchup
                    'midfield_battle': str,          # Midfield number/quality advantage
                    'defensive_vulnerability': str    # Which defense more exposed
                },
                'tactical_adjustments': {
                    'expected_home_changes': List[str],  # Likely tactical adjustments
                    'expected_away_changes': List[str],  # Likely tactical responses
                    'key_battles': List[Dict]            # Critical tactical duels
                },
                'overall_tactical_advantage': str,   # 'home'|'away'|'balanced'
                'tactical_multipliers': {
                    'home_tactical_multiplier': Decimal,  # 0.85-1.15
                    'away_tactical_multiplier': Decimal   # 0.85-1.15
                }
            }
        """
        try:
            # Get tactical profiles for both teams
            home_tactical = self.tactical_analyzer.calculate_tactical_style_scores(
                home_team_id, league_id, season
            )
            away_tactical = self.tactical_analyzer.calculate_tactical_style_scores(
                away_team_id, league_id, season
            )
            
            home_formations = self.tactical_analyzer.analyze_team_formation_preferences(
                home_team_id, league_id, season
            )
            away_formations = self.tactical_analyzer.analyze_team_formation_preferences(
                away_team_id, league_id, season
            )
            
            # Analyze style matchups
            style_matchup = self._analyze_style_interactions(home_tactical, away_tactical)
            
            # Analyze formation compatibility
            formation_compatibility = self._analyze_formation_matchup(
                home_formations, away_formations
            )
            
            # Predict tactical adjustments
            tactical_adjustments = self._predict_tactical_adjustments(
                home_team_id, away_team_id, home_tactical, away_tactical,
                home_formations, away_formations
            )
            
            # Calculate overall tactical advantage
            overall_advantage = self._calculate_overall_tactical_advantage(
                style_matchup, formation_compatibility
            )
            
            # Calculate tactical multipliers
            multipliers = self._calculate_tactical_multipliers(
                home_tactical, away_tactical, style_matchup, overall_advantage
            )
            
            return {
                'style_matchup': style_matchup,
                'formation_compatibility': formation_compatibility,
                'tactical_adjustments': tactical_adjustments,
                'overall_tactical_advantage': overall_advantage,
                'tactical_multipliers': multipliers,
                'analysis_confidence': self._calculate_analysis_confidence(
                    home_tactical, away_tactical
                )
            }
            
        except Exception as e:
            logger.error(f"Error analyzing tactical compatibility: {e}")
            return self._get_default_tactical_analysis()
    
    def calculate_style_effectiveness(self, attacking_style: Dict, defensive_style: Dict) -> Decimal:
        """
        Calculate how effective one team's attacking style is against another's defensive style.
        
        Args:
            attacking_style: Attacking team's tactical characteristics
            defensive_style: Defending team's tactical characteristics
            
        Returns:
            Effectiveness multiplier (0.7-1.3 range)
        """
        try:
            effectiveness_factors = []
            
            # Possession vs pressing matchup
            att_possession = float(attacking_style.get('possession_style', 0.5))
            def_pressing = float(defensive_style.get('pressing_intensity', 0.5))
            
            # High possession vs high pressing = slightly favors defense
            # Low possession (direct) vs high pressing = favors attack
            possession_factor = 1.0 + (att_possession - def_pressing) * 0.1
            effectiveness_factors.append(possession_factor)
            
            # Attacking intensity vs defensive solidity
            att_intensity = float(attacking_style.get('attacking_intensity', 0.5))
            def_solidity = float(defensive_style.get('defensive_solidity', 0.5))
            
            intensity_factor = 1.0 + (att_intensity - def_solidity) * 0.15
            effectiveness_factors.append(intensity_factor)
            
            # Counter attack vs defensive line
            att_counter = float(attacking_style.get('counter_attack_threat', 0.5))
            # Assume high defensive solidity correlates with higher defensive line
            counter_factor = 1.0 + att_counter * def_solidity * 0.12
            effectiveness_factors.append(counter_factor)
            
            # Set piece strength vs defensive discipline
            att_setpiece = float(attacking_style.get('set_piece_strength', 0.5))
            def_discipline = float(defensive_style.get('tactical_discipline', 0.5))
            
            setpiece_factor = 1.0 + (att_setpiece - def_discipline) * 0.08
            effectiveness_factors.append(setpiece_factor)
            
            # Calculate weighted effectiveness
            base_effectiveness = sum(effectiveness_factors) / len(effectiveness_factors)
            
            # Clamp to reasonable range
            effectiveness = max(0.7, min(1.3, base_effectiveness))
            
            return Decimal(str(round(effectiveness, 3)))
            
        except Exception as e:
            logger.error(f"Error calculating style effectiveness: {e}")
            return Decimal('1.0')
    
    def get_historical_tactical_outcomes(self, home_team_id: int, away_team_id: int,
                                       league_id: int, years_back: int = 3) -> Dict:
        """
        Analyze historical outcomes when these tactical styles have met.
        
        Args:
            home_team_id: Home team identifier
            away_team_id: Away team identifier
            league_id: League identifier
            years_back: How many years of history to analyze
            
        Returns:
            {
                'similar_matchups': List[Dict],     # Games with similar tactical setups
                'avg_goals_when_home_dominates': Decimal,
                'avg_goals_when_away_dominates': Decimal,
                'tactical_trend': str               # Historical trend in this matchup
            }
        """
        try:
            # Get historical matches between these teams
            historical_matches = self._get_historical_matches(
                home_team_id, away_team_id, league_id, years_back
            )
            
            if len(historical_matches) < 3:
                return self._get_default_historical_analysis()
            
            # Analyze similar tactical matchups in the league
            similar_matchups = self._find_similar_tactical_matchups(
                home_team_id, away_team_id, league_id, years_back
            )
            
            # Calculate averages when each team dominates tactically
            home_dominant_goals = []
            away_dominant_goals = []
            
            for match in historical_matches:
                if match.get('tactical_dominance') == 'home':
                    home_dominant_goals.append(match.get('total_goals', 2.5))
                elif match.get('tactical_dominance') == 'away':
                    away_dominant_goals.append(match.get('total_goals', 2.5))
            
            avg_goals_home_dominance = Decimal(str(
                sum(home_dominant_goals) / len(home_dominant_goals) 
                if home_dominant_goals else 2.5
            ))
            
            avg_goals_away_dominance = Decimal(str(
                sum(away_dominant_goals) / len(away_dominant_goals) 
                if away_dominant_goals else 2.5
            ))
            
            # Determine tactical trend
            recent_matches = historical_matches[-5:]  # Last 5 meetings
            home_wins = sum(1 for match in recent_matches if match.get('result') == 'home_win')
            away_wins = sum(1 for match in recent_matches if match.get('result') == 'away_win')
            
            if home_wins > away_wins + 1:
                trend = 'home_tactical_advantage'
            elif away_wins > home_wins + 1:
                trend = 'away_tactical_advantage'
            else:
                trend = 'balanced_tactical_matchup'
            
            return {
                'similar_matchups': similar_matchups[:10],  # Top 10 most similar
                'avg_goals_when_home_dominates': avg_goals_home_dominance,
                'avg_goals_when_away_dominates': avg_goals_away_dominance,
                'tactical_trend': trend,
                'sample_size': len(historical_matches),
                'confidence': min(len(historical_matches) / 10, 1.0)
            }
            
        except Exception as e:
            logger.error(f"Error analyzing historical tactical outcomes: {e}")
            return self._get_default_historical_analysis()
    
    def predict_tactical_adjustments(self, home_team_id: int, away_team_id: int,
                                    league_id: int, season: int) -> Dict:
        """
        Predict likely tactical adjustments each team will make based on opponent.
        
        Args:
            home_team_id: Home team identifier
            away_team_id: Away team identifier
            league_id: League identifier
            season: Season year
            
        Returns:
            {
                'home_adjustments': {
                    'formation_change_probability': Decimal,
                    'likely_new_formation': str,
                    'attacking_changes': List[str],
                    'defensive_changes': List[str]
                },
                'away_adjustments': {
                    'formation_change_probability': Decimal,
                    'likely_new_formation': str,
                    'attacking_changes': List[str],
                    'defensive_changes': List[str]
                }
            }
        """
        try:
            # Get team tactical profiles
            home_tactical = self.tactical_analyzer.calculate_tactical_style_scores(
                home_team_id, league_id, season
            )
            away_tactical = self.tactical_analyzer.calculate_tactical_style_scores(
                away_team_id, league_id, season
            )
            
            home_formations = self.tactical_analyzer.analyze_team_formation_preferences(
                home_team_id, league_id, season
            )
            away_formations = self.tactical_analyzer.analyze_team_formation_preferences(
                away_team_id, league_id, season
            )
            
            # Predict home team adjustments
            home_adjustments = self._predict_team_adjustments(
                home_tactical, away_tactical, home_formations, is_home=True
            )
            
            # Predict away team adjustments
            away_adjustments = self._predict_team_adjustments(
                away_tactical, home_tactical, away_formations, is_home=False
            )
            
            return {
                'home_adjustments': home_adjustments,
                'away_adjustments': away_adjustments,
                'adjustment_confidence': self._calculate_adjustment_confidence(
                    home_tactical, away_tactical
                )
            }
            
        except Exception as e:
            logger.error(f"Error predicting tactical adjustments: {e}")
            return self._get_default_adjustment_predictions()
    
    # Private helper methods
    
    def _analyze_style_interactions(self, home_tactical: Dict, away_tactical: Dict) -> Dict:
        """Analyze how tactical styles interact."""
        try:
            # Possession advantage
            home_possession = float(home_tactical.get('possession_style', 0.5))
            away_possession = float(away_tactical.get('possession_style', 0.5))
            
            if home_possession > away_possession + 0.15:
                possession_advantage = 'home'
            elif away_possession > home_possession + 0.15:
                possession_advantage = 'away'
            else:
                possession_advantage = 'neutral'
            
            # Pressing effectiveness
            home_pressing = float(home_tactical.get('pressing_intensity', 0.5))
            away_pressing = float(away_tactical.get('pressing_intensity', 0.5))
            away_possession_vuln = 1 - away_possession  # Lower possession = more vulnerable to press
            
            home_press_effectiveness = home_pressing * away_possession_vuln
            away_press_effectiveness = away_pressing * (1 - home_possession)
            
            if home_press_effectiveness > away_press_effectiveness + 0.1:
                pressing_effectiveness = 'home'
            elif away_press_effectiveness > home_press_effectiveness + 0.1:
                pressing_effectiveness = 'away'
            else:
                pressing_effectiveness = 'neutral'
            
            # Counter attack threat
            home_counter = float(home_tactical.get('counter_attack_threat', 0.5))
            away_counter = float(away_tactical.get('counter_attack_threat', 0.5))
            
            # Counter attacks work better against teams that attack more
            home_att_intensity = float(home_tactical.get('attacking_intensity', 0.5))
            away_att_intensity = float(away_tactical.get('attacking_intensity', 0.5))
            
            home_counter_opportunity = home_counter * away_att_intensity
            away_counter_opportunity = away_counter * home_att_intensity
            
            if home_counter_opportunity > away_counter_opportunity + 0.1:
                counter_threat = 'home'
            elif away_counter_opportunity > home_counter_opportunity + 0.1:
                counter_threat = 'away'
            else:
                counter_threat = 'neutral'
            
            # Set piece advantage
            home_setpiece = float(home_tactical.get('set_piece_strength', 0.5))
            away_setpiece = float(away_tactical.get('set_piece_strength', 0.5))
            
            if home_setpiece > away_setpiece + 0.12:
                setpiece_advantage = 'home'
            elif away_setpiece > home_setpiece + 0.12:
                setpiece_advantage = 'away'
            else:
                setpiece_advantage = 'neutral'
            
            return {
                'possession_advantage': possession_advantage,
                'pressing_effectiveness': pressing_effectiveness,
                'counter_attack_threat': counter_threat,
                'set_piece_advantage': setpiece_advantage
            }
            
        except Exception as e:
            logger.error(f"Error analyzing style interactions: {e}")
            return {
                'possession_advantage': 'neutral',
                'pressing_effectiveness': 'neutral',
                'counter_attack_threat': 'neutral',
                'set_piece_advantage': 'neutral'
            }
    
    def _analyze_formation_matchup(self, home_formations: Dict, away_formations: Dict) -> Dict:
        """Analyze formation compatibility and advantages."""
        try:
            home_primary = home_formations.get('primary_formation', '4-4-2')
            away_primary = away_formations.get('primary_formation', '4-4-2')
            
            # Analyze width advantage
            home_width = self._get_formation_width(home_primary)
            away_width = self._get_formation_width(away_primary)
            
            if home_width > away_width + 0.5:
                width_advantage = 'home'
            elif away_width > home_width + 0.5:
                width_advantage = 'away'
            else:
                width_advantage = 'neutral'
            
            # Analyze midfield battle
            home_midfield = self._get_formation_midfield_strength(home_primary)
            away_midfield = self._get_formation_midfield_strength(away_primary)
            
            if home_midfield > away_midfield:
                midfield_battle = 'home'
            elif away_midfield > home_midfield:
                midfield_battle = 'away'
            else:
                midfield_battle = 'neutral'
            
            # Analyze defensive vulnerability
            home_def_vuln = self._get_formation_defensive_vulnerability(home_primary)
            away_def_vuln = self._get_formation_defensive_vulnerability(away_primary)
            
            if home_def_vuln > away_def_vuln + 0.1:
                defensive_vulnerability = 'home'
            elif away_def_vuln > home_def_vuln + 0.1:
                defensive_vulnerability = 'away'
            else:
                defensive_vulnerability = 'neutral'
            
            return {
                'width_advantage': width_advantage,
                'midfield_battle': midfield_battle,
                'defensive_vulnerability': defensive_vulnerability,
                'formation_matchup': f"{home_primary} vs {away_primary}"
            }
            
        except Exception as e:
            logger.error(f"Error analyzing formation matchup: {e}")
            return {
                'width_advantage': 'neutral',
                'midfield_battle': 'neutral',
                'defensive_vulnerability': 'neutral',
                'formation_matchup': '4-4-2 vs 4-4-2'
            }
    
    def _predict_tactical_adjustments(self, home_team_id: int, away_team_id: int,
                                     home_tactical: Dict, away_tactical: Dict,
                                     home_formations: Dict, away_formations: Dict) -> Dict:
        """Predict likely tactical adjustments based on matchup."""
        try:
            # Predict home team adjustments
            home_changes = []
            away_changes = []
            
            # Home team adjustments based on away team strengths
            away_pressing = float(away_tactical.get('pressing_intensity', 0.5))
            if away_pressing > 0.7:
                home_changes.append('longer_passing_to_bypass_press')
                home_changes.append('wider_play_to_stretch_defense')
            
            away_counter = float(away_tactical.get('counter_attack_threat', 0.5))
            if away_counter > 0.7:
                home_changes.append('more_cautious_buildup')
                home_changes.append('deeper_defensive_line')
            
            # Away team adjustments based on home team strengths
            home_possession = float(home_tactical.get('possession_style', 0.5))
            if home_possession > 0.7:
                away_changes.append('compact_defensive_shape')
                away_changes.append('counter_attacking_focus')
            
            home_setpiece = float(home_tactical.get('set_piece_strength', 0.5))
            if home_setpiece > 0.7:
                away_changes.append('man_marking_on_set_pieces')
                away_changes.append('zonal_defensive_setup')
            
            # Key tactical battles
            key_battles = []
            
            # Midfield battle
            key_battles.append({
                'area': 'midfield_control',
                'home_strength': float(home_tactical.get('possession_style', 0.5)),
                'away_strength': float(away_tactical.get('pressing_intensity', 0.5)),
                'importance': 'high'
            })
            
            # Wide areas
            key_battles.append({
                'area': 'wide_areas',
                'home_strength': self._get_formation_width(home_formations.get('primary_formation', '4-4-2')),
                'away_strength': self._get_formation_width(away_formations.get('primary_formation', '4-4-2')),
                'importance': 'medium'
            })
            
            # Set pieces
            key_battles.append({
                'area': 'set_pieces',
                'home_strength': float(home_tactical.get('set_piece_strength', 0.5)),
                'away_strength': float(away_tactical.get('set_piece_strength', 0.5)),
                'importance': 'medium'
            })
            
            return {
                'expected_home_changes': home_changes[:3],  # Top 3 most likely
                'expected_away_changes': away_changes[:3],
                'key_battles': key_battles
            }
            
        except Exception as e:
            logger.error(f"Error predicting tactical adjustments: {e}")
            return {
                'expected_home_changes': [],
                'expected_away_changes': [],
                'key_battles': []
            }
    
    def _calculate_overall_tactical_advantage(self, style_matchup: Dict, formation_compatibility: Dict) -> str:
        """Calculate overall tactical advantage."""
        try:
            home_advantages = 0
            away_advantages = 0
            
            # Count style advantages
            for advantage in style_matchup.values():
                if advantage == 'home':
                    home_advantages += 1
                elif advantage == 'away':
                    away_advantages += 1
            
            # Count formation advantages (weighted lower)
            for advantage in formation_compatibility.values():
                if advantage == 'home':
                    home_advantages += 0.5
                elif advantage == 'away':
                    away_advantages += 0.5
            
            if home_advantages > away_advantages + 0.5:
                return 'home'
            elif away_advantages > home_advantages + 0.5:
                return 'away'
            else:
                return 'balanced'
                
        except Exception as e:
            logger.error(f"Error calculating overall tactical advantage: {e}")
            return 'balanced'
    
    def _calculate_tactical_multipliers(self, home_tactical: Dict, away_tactical: Dict,
                                       style_matchup: Dict, overall_advantage: str) -> Dict:
        """Calculate tactical multipliers for lambda adjustments."""
        try:
            # Base multipliers
            home_multiplier = Decimal('1.0')
            away_multiplier = Decimal('1.0')
            
            # Apply style-based adjustments
            if style_matchup.get('possession_advantage') == 'home':
                home_multiplier += Decimal('0.05')
            elif style_matchup.get('possession_advantage') == 'away':
                away_multiplier += Decimal('0.05')
            
            if style_matchup.get('pressing_effectiveness') == 'home':
                home_multiplier += Decimal('0.04')
                away_multiplier -= Decimal('0.02')
            elif style_matchup.get('pressing_effectiveness') == 'away':
                away_multiplier += Decimal('0.04')
                home_multiplier -= Decimal('0.02')
            
            if style_matchup.get('counter_attack_threat') == 'home':
                home_multiplier += Decimal('0.06')
            elif style_matchup.get('counter_attack_threat') == 'away':
                away_multiplier += Decimal('0.06')
            
            if style_matchup.get('set_piece_advantage') == 'home':
                home_multiplier += Decimal('0.03')
            elif style_matchup.get('set_piece_advantage') == 'away':
                away_multiplier += Decimal('0.03')
            
            # Apply overall advantage bonus
            if overall_advantage == 'home':
                home_multiplier += Decimal('0.02')
            elif overall_advantage == 'away':
                away_multiplier += Decimal('0.02')
            
            # Clamp to reasonable ranges
            home_multiplier = max(Decimal('0.85'), min(home_multiplier, Decimal('1.15')))
            away_multiplier = max(Decimal('0.85'), min(away_multiplier, Decimal('1.15')))
            
            return {
                'home_tactical_multiplier': home_multiplier,
                'away_tactical_multiplier': away_multiplier
            }
            
        except Exception as e:
            logger.error(f"Error calculating tactical multipliers: {e}")
            return {
                'home_tactical_multiplier': Decimal('1.0'),
                'away_tactical_multiplier': Decimal('1.0')
            }
    
    def _get_formation_width(self, formation: str) -> float:
        """Get formation width score (0-10)."""
        width_scores = {
            '3-5-2': 8.0,
            '3-4-3': 9.0,
            '4-3-3': 7.5,
            '4-2-3-1': 6.5,
            '4-4-2': 6.0,
            '4-5-1': 7.0,
            '5-3-2': 5.5,
            '5-4-1': 5.0
        }
        return width_scores.get(formation, 6.0)
    
    def _get_formation_midfield_strength(self, formation: str) -> int:
        """Get midfield player count for formation."""
        midfield_counts = {
            '3-5-2': 5,
            '3-4-3': 4,
            '4-3-3': 3,
            '4-2-3-1': 3,  # 2 DM + 1 CAM
            '4-4-2': 4,
            '4-5-1': 5,
            '5-3-2': 3,
            '5-4-1': 4
        }
        return midfield_counts.get(formation, 4)
    
    def _get_formation_defensive_vulnerability(self, formation: str) -> float:
        """Get formation defensive vulnerability score (0-1, higher = more vulnerable)."""
        vulnerability_scores = {
            '3-5-2': 0.7,  # Only 3 at the back
            '3-4-3': 0.8,  # 3 at back, attacking formation
            '4-3-3': 0.5,  # Balanced
            '4-2-3-1': 0.4,  # Extra defensive midfielder
            '4-4-2': 0.5,  # Balanced
            '4-5-1': 0.3,  # Very defensive
            '5-3-2': 0.2,  # 5 at the back
            '5-4-1': 0.1   # Very defensive
        }
        return vulnerability_scores.get(formation, 0.5)
    
    # Helper methods for data retrieval and analysis
    
    def _get_historical_matches(self, home_team_id: int, away_team_id: int, 
                               league_id: int, years_back: int) -> List[Dict]:
        """Get historical matches between teams."""
        try:
            # This would integrate with database to get historical match data
            # For now, return placeholder structure
            return []
        except Exception as e:
            logger.error(f"Error fetching historical matches: {e}")
            return []
    
    def _find_similar_tactical_matchups(self, home_team_id: int, away_team_id: int,
                                       league_id: int, years_back: int) -> List[Dict]:
        """Find matches with similar tactical setups in the league."""
        try:
            # This would analyze league-wide matches for similar tactical profiles
            return []
        except Exception as e:
            logger.error(f"Error finding similar tactical matchups: {e}")
            return []
    
    def _predict_team_adjustments(self, team_tactical: Dict, opponent_tactical: Dict,
                                 team_formations: Dict, is_home: bool) -> Dict:
        """Predict tactical adjustments for a team."""
        try:
            flexibility = float(team_formations.get('tactical_consistency', 0.7))
            change_probability = max(0.1, 1.0 - flexibility)
            
            primary_formation = team_formations.get('primary_formation', '4-4-2')
            
            # Predict likely formation changes based on opponent
            if float(opponent_tactical.get('attacking_intensity', 0.5)) > 0.7:
                likely_new_formation = self._get_defensive_formation_alternative(primary_formation)
                attacking_changes = ['deeper_defensive_line', 'compact_midfield']
                defensive_changes = ['man_marking', 'defensive_pressing']
            else:
                likely_new_formation = self._get_attacking_formation_alternative(primary_formation)
                attacking_changes = ['higher_tempo', 'wider_play']
                defensive_changes = ['higher_line', 'aggressive_pressing']
            
            return {
                'formation_change_probability': Decimal(str(change_probability)),
                'likely_new_formation': likely_new_formation,
                'attacking_changes': attacking_changes,
                'defensive_changes': defensive_changes
            }
            
        except Exception as e:
            logger.error(f"Error predicting team adjustments: {e}")
            return {
                'formation_change_probability': Decimal('0.3'),
                'likely_new_formation': '4-4-2',
                'attacking_changes': [],
                'defensive_changes': []
            }
    
    def _get_defensive_formation_alternative(self, formation: str) -> str:
        """Get more defensive alternative to formation."""
        defensive_alternatives = {
            '4-3-3': '4-5-1',
            '4-4-2': '5-4-1',
            '3-5-2': '5-3-2',
            '4-2-3-1': '4-5-1'
        }
        return defensive_alternatives.get(formation, '5-4-1')
    
    def _get_attacking_formation_alternative(self, formation: str) -> str:
        """Get more attacking alternative to formation."""
        attacking_alternatives = {
            '5-4-1': '4-4-2',
            '4-5-1': '4-3-3',
            '5-3-2': '3-5-2',
            '4-4-2': '4-2-3-1'
        }
        return attacking_alternatives.get(formation, '4-3-3')
    
    def _calculate_analysis_confidence(self, home_tactical: Dict, away_tactical: Dict) -> Decimal:
        """Calculate confidence in tactical analysis."""
        try:
            # Higher confidence if both teams have clear tactical profiles
            home_clarity = self._calculate_tactical_profile_clarity(home_tactical)
            away_clarity = self._calculate_tactical_profile_clarity(away_tactical)
            
            confidence = (home_clarity + away_clarity) / 2
            return Decimal(str(round(confidence, 2)))
        except Exception as e:
            logger.error(f"Error calculating analysis confidence: {e}")
            return Decimal('0.5')
    
    def _calculate_tactical_profile_clarity(self, tactical: Dict) -> float:
        """Calculate how clear/distinct a team's tactical profile is."""
        try:
            # Clear profiles have values further from neutral (0.5)
            deviations = []
            for key, value in tactical.items():
                if isinstance(value, (int, float, Decimal)):
                    deviation = abs(float(value) - 0.5)
                    deviations.append(deviation)
            
            if deviations:
                avg_deviation = sum(deviations) / len(deviations)
                clarity = min(avg_deviation * 4, 1.0)  # Scale to 0-1
                return clarity
            return 0.5
        except Exception as e:
            logger.error(f"Error calculating profile clarity: {e}")
            return 0.5
    
    def _calculate_adjustment_confidence(self, home_tactical: Dict, away_tactical: Dict) -> Decimal:
        """Calculate confidence in adjustment predictions."""
        return self._calculate_analysis_confidence(home_tactical, away_tactical)
    
    # Default/fallback methods
    
    def _get_default_tactical_analysis(self) -> Dict:
        """Default tactical analysis when errors occur."""
        return {
            'style_matchup': {
                'possession_advantage': 'neutral',
                'pressing_effectiveness': 'neutral',
                'counter_attack_threat': 'neutral',
                'set_piece_advantage': 'neutral'
            },
            'formation_compatibility': {
                'width_advantage': 'neutral',
                'midfield_battle': 'neutral',
                'defensive_vulnerability': 'neutral'
            },
            'tactical_adjustments': {
                'expected_home_changes': [],
                'expected_away_changes': [],
                'key_battles': []
            },
            'overall_tactical_advantage': 'balanced',
            'tactical_multipliers': {
                'home_tactical_multiplier': Decimal('1.0'),
                'away_tactical_multiplier': Decimal('1.0')
            },
            'analysis_confidence': Decimal('0.3')
        }
    
    def _get_default_historical_analysis(self) -> Dict:
        """Default historical analysis when insufficient data."""
        return {
            'similar_matchups': [],
            'avg_goals_when_home_dominates': Decimal('2.5'),
            'avg_goals_when_away_dominates': Decimal('2.3'),
            'tactical_trend': 'balanced_tactical_matchup',
            'sample_size': 0,
            'confidence': 0.0
        }
    
    def _get_default_adjustment_predictions(self) -> Dict:
        """Default adjustment predictions when errors occur."""
        return {
            'home_adjustments': {
                'formation_change_probability': Decimal('0.3'),
                'likely_new_formation': '4-4-2',
                'attacking_changes': [],
                'defensive_changes': []
            },
            'away_adjustments': {
                'formation_change_probability': Decimal('0.3'),
                'likely_new_formation': '4-4-2',
                'attacking_changes': [],
                'defensive_changes': []
            },
            'adjustment_confidence': Decimal('0.3')
        }


# Convenience functions for easy integration

def analyze_tactical_compatibility(home_team_id: int, away_team_id: int, 
                                 league_id: int, season: int) -> Dict:
    """
    Analyze how team tactical styles interact and create advantages/disadvantages.
    
    Returns comprehensive tactical matchup analysis including style interactions,
    formation compatibility, predicted adjustments, and tactical multipliers.
    """
    analyzer = TacticalMatchupAnalyzer()
    return analyzer.analyze_tactical_compatibility(home_team_id, away_team_id, league_id, season)


def calculate_style_effectiveness(attacking_style: Dict, defensive_style: Dict) -> Decimal:
    """
    Calculate how effective one team's attacking style is against another's defensive style.
    
    Args:
        attacking_style: Attacking team's tactical characteristics
        defensive_style: Defending team's tactical characteristics
        
    Returns:
        Effectiveness multiplier (0.7-1.3 range)
    """
    analyzer = TacticalMatchupAnalyzer()
    return analyzer.calculate_style_effectiveness(attacking_style, defensive_style)


def get_historical_tactical_outcomes(home_team_id: int, away_team_id: int,
                                   league_id: int, years_back: int = 3) -> Dict:
    """
    Analyze historical outcomes when these tactical styles have met.
    
    Returns analysis of similar tactical matchups and their typical outcomes.
    """
    analyzer = TacticalMatchupAnalyzer()
    return analyzer.get_historical_tactical_outcomes(home_team_id, away_team_id, league_id, years_back)


def predict_tactical_adjustments(home_team_id: int, away_team_id: int,
                                league_id: int, season: int) -> Dict:
    """
    Predict likely tactical adjustments each team will make based on opponent.
    
    Returns predicted formation changes and tactical modifications for both teams.
    """
    analyzer = TacticalMatchupAnalyzer()
    return analyzer.predict_tactical_adjustments(home_team_id, away_team_id, league_id, season)