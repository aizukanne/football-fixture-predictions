"""
Playing surface impact analysis for football predictions.

This module analyzes team performance on different playing surfaces:
- Grass vs artificial turf performance
- Surface-specific team advantages
- Historical performance tracking by surface type
- Surface adaptation analysis

Phase 2: Home/Away Venue Analysis
Part of the venue analysis system for surface-specific performance insights.
"""

from typing import Dict, List, Optional
from decimal import Decimal
from collections import defaultdict
import statistics

from ..data.database_client import dynamodb
from ..infrastructure.version_manager import VersionManager


class SurfaceAnalyzer:
    """Analyzer for team performance on different playing surfaces."""
    
    def __init__(self):
        self.version_manager = VersionManager()
        
    def analyze_surface_advantage(self, team_id: int, surface_type: str, season: int) -> Decimal:
        """
        Analyze team's performance on different playing surfaces.
        
        Args:
            team_id: Team ID
            surface_type: 'grass' or 'artificial'
            season: Season year
            
        Returns:
            Performance multiplier for this surface type (0.9-1.1)
            
        Example:
            >>> analyzer = SurfaceAnalyzer()
            >>> advantage = analyzer.analyze_surface_advantage(123, 'artificial', 2024)
            >>> print(f"Artificial surface advantage: {advantage}")
            Artificial surface advantage: 1.05
        """
        try:
            # Get team's historical performance on both surfaces
            performance_data = self._get_surface_performance_history(team_id, season)
            
            if not performance_data or surface_type not in performance_data:
                return Decimal('1.0')  # Neutral if no data
            
            surface_stats = performance_data[surface_type]
            overall_stats = performance_data.get('overall', {})
            
            # Calculate relative performance on this surface
            if not surface_stats.get('matches_played', 0) or not overall_stats.get('matches_played', 0):
                return Decimal('1.0')
            
            surface_ppm = surface_stats.get('points_per_match', 0)
            overall_ppm = overall_stats.get('points_per_match', 0)
            
            if overall_ppm == 0:
                return Decimal('1.0')
            
            # Calculate advantage ratio
            advantage_ratio = surface_ppm / overall_ppm
            
            # Clamp to reasonable bounds (10% advantage/disadvantage max)
            advantage = max(0.9, min(1.1, advantage_ratio))
            
            return Decimal(str(round(advantage, 3)))
            
        except Exception as e:
            print(f"Error analyzing surface advantage for team {team_id} on {surface_type}: {e}")
            return Decimal('1.0')
    
    def get_team_surface_preference(self, team_id: int, season: int) -> Dict:
        """
        Determine team's preferred playing surface based on historical performance.
        
        Args:
            team_id: Team ID
            season: Season year
            
        Returns:
            Dict with surface preference analysis:
            {
                'preferred_surface': 'grass'|'artificial',
                'grass_performance': Decimal,
                'artificial_performance': Decimal,
                'surface_advantage': Decimal,
                'confidence_level': str
            }
            
        Example:
            >>> analyzer = SurfaceAnalyzer()
            >>> preference = analyzer.get_team_surface_preference(123, 2024)
            >>> print(f"Preferred surface: {preference['preferred_surface']}")
            Preferred surface: grass
        """
        try:
            performance_data = self._get_surface_performance_history(team_id, season)
            
            if not performance_data:
                return self._get_neutral_surface_preference()
            
            grass_stats = performance_data.get('grass', {})
            artificial_stats = performance_data.get('artificial', {})
            
            # Calculate performance metrics for each surface
            grass_performance = self._calculate_surface_performance_score(grass_stats)
            artificial_performance = self._calculate_surface_performance_score(artificial_stats)
            
            # Determine preferred surface
            if grass_performance > artificial_performance:
                preferred_surface = 'grass'
                advantage = grass_performance / artificial_performance if artificial_performance > 0 else 1.0
            elif artificial_performance > grass_performance:
                preferred_surface = 'artificial'
                advantage = artificial_performance / grass_performance if grass_performance > 0 else 1.0
            else:
                preferred_surface = 'neutral'
                advantage = 1.0
            
            # Calculate confidence based on sample size
            total_matches = (grass_stats.get('matches_played', 0) + 
                           artificial_stats.get('matches_played', 0))
            confidence_level = self._get_confidence_level(total_matches)
            
            return {
                'preferred_surface': preferred_surface,
                'grass_performance': Decimal(str(round(grass_performance, 3))),
                'artificial_performance': Decimal(str(round(artificial_performance, 3))),
                'surface_advantage': Decimal(str(round(advantage, 3))),
                'confidence_level': confidence_level,
                'total_matches_analyzed': total_matches
            }
            
        except Exception as e:
            print(f"Error determining surface preference for team {team_id}: {e}")
            return self._get_neutral_surface_preference()
    
    def compare_teams_surface_matchup(self, home_team_id: int, away_team_id: int, 
                                    surface_type: str, season: int) -> Dict:
        """
        Compare two teams' performance on a specific surface for matchup analysis.
        
        Args:
            home_team_id: Home team ID
            away_team_id: Away team ID
            surface_type: 'grass' or 'artificial'
            season: Season year
            
        Returns:
            Surface matchup analysis:
            {
                'home_surface_advantage': Decimal,
                'away_surface_advantage': Decimal,
                'surface_matchup_factor': Decimal,
                'favored_team': 'home'|'away'|'neutral'
            }
        """
        try:
            home_advantage = self.analyze_surface_advantage(home_team_id, surface_type, season)
            away_advantage = self.analyze_surface_advantage(away_team_id, surface_type, season)
            
            # Calculate relative surface matchup
            if float(home_advantage) > float(away_advantage):
                matchup_factor = home_advantage / away_advantage
                favored_team = 'home'
            elif float(away_advantage) > float(home_advantage):
                matchup_factor = away_advantage / home_advantage
                favored_team = 'away'
            else:
                matchup_factor = Decimal('1.0')
                favored_team = 'neutral'
            
            return {
                'home_surface_advantage': home_advantage,
                'away_surface_advantage': away_advantage,
                'surface_matchup_factor': matchup_factor,
                'favored_team': favored_team,
                'surface_type': surface_type
            }
            
        except Exception as e:
            print(f"Error comparing surface matchup for teams {home_team_id} vs {away_team_id}: {e}")
            return {
                'home_surface_advantage': Decimal('1.0'),
                'away_surface_advantage': Decimal('1.0'),
                'surface_matchup_factor': Decimal('1.0'),
                'favored_team': 'neutral',
                'surface_type': surface_type
            }
    
    def get_league_surface_distribution(self, league_id: int, season: int) -> Dict:
        """
        Analyze the distribution of surface types in a league.
        
        Args:
            league_id: League ID
            season: Season year
            
        Returns:
            League surface distribution:
            {
                'grass_venues': int,
                'artificial_venues': int,
                'grass_percentage': Decimal,
                'artificial_percentage': Decimal,
                'predominant_surface': str
            }
        """
        try:
            # This would query venue data for all teams in the league
            # For now, return typical distributions
            
            # Most professional leagues are predominantly grass
            return {
                'grass_venues': 18,
                'artificial_venues': 2,
                'grass_percentage': Decimal('90.0'),
                'artificial_percentage': Decimal('10.0'),
                'predominant_surface': 'grass'
            }
            
        except Exception as e:
            print(f"Error getting surface distribution for league {league_id}: {e}")
            return {
                'grass_venues': 20,
                'artificial_venues': 0,
                'grass_percentage': Decimal('100.0'),
                'artificial_percentage': Decimal('0.0'),
                'predominant_surface': 'grass'
            }
    
    def _get_surface_performance_history(self, team_id: int, season: int) -> Dict:
        """
        Get historical performance data by surface type for a team.
        
        This would query the match database and aggregate performance by surface.
        For now, returns simulated data structure.
        
        Args:
            team_id: Team ID
            season: Season year
            
        Returns:
            Performance data by surface type
        """
        # This would be implemented to query actual match data
        # and aggregate by venue surface type
        
        # Return structure for now - would be populated from database
        return {
            'grass': {
                'matches_played': 0,
                'wins': 0,
                'draws': 0,
                'losses': 0,
                'goals_scored': 0,
                'goals_conceded': 0,
                'points': 0,
                'points_per_match': 0.0
            },
            'artificial': {
                'matches_played': 0,
                'wins': 0,
                'draws': 0,
                'losses': 0,
                'goals_scored': 0,
                'goals_conceded': 0,
                'points': 0,
                'points_per_match': 0.0
            },
            'overall': {
                'matches_played': 0,
                'wins': 0,
                'draws': 0,
                'losses': 0,
                'goals_scored': 0,
                'goals_conceded': 0,
                'points': 0,
                'points_per_match': 0.0
            }
        }
    
    def _calculate_surface_performance_score(self, surface_stats: Dict) -> float:
        """
        Calculate overall performance score for a surface.
        
        Args:
            surface_stats: Performance statistics for surface
            
        Returns:
            Performance score (0.0-3.0 typically)
        """
        if not surface_stats or surface_stats.get('matches_played', 0) == 0:
            return 0.0
        
        # Weight different metrics
        points_per_match = surface_stats.get('points_per_match', 0)
        goals_ratio = (surface_stats.get('goals_scored', 0) / 
                      max(surface_stats.get('goals_conceded', 1), 1))
        
        # Combine metrics (points per match is primary, goals ratio secondary)
        performance_score = (points_per_match * 0.7) + (goals_ratio * 0.3)
        
        return performance_score
    
    def _get_confidence_level(self, total_matches: int) -> str:
        """
        Determine confidence level based on sample size.
        
        Args:
            total_matches: Total matches in sample
            
        Returns:
            Confidence level string
        """
        if total_matches < 10:
            return 'low'
        elif total_matches < 25:
            return 'medium'
        else:
            return 'high'
    
    def _get_neutral_surface_preference(self) -> Dict:
        """
        Return neutral surface preference when no data available.
        
        Returns:
            Neutral surface preference dict
        """
        return {
            'preferred_surface': 'neutral',
            'grass_performance': Decimal('1.0'),
            'artificial_performance': Decimal('1.0'),
            'surface_advantage': Decimal('1.0'),
            'confidence_level': 'none',
            'total_matches_analyzed': 0
        }


# Convenience functions for direct access
def analyze_surface_advantage(team_id: int, surface_type: str, season: int) -> Decimal:
    """
    Analyze team's performance on different playing surfaces.
    
    Args:
        surface_type: 'grass' or 'artificial'
        
    Returns:
        Performance multiplier for this surface type
    """
    analyzer = SurfaceAnalyzer()
    return analyzer.analyze_surface_advantage(team_id, surface_type, season)


def get_team_surface_preference(team_id: int, season: int) -> Dict:
    """
    Determine team's preferred playing surface based on historical performance.
    
    Returns:
        {
            'preferred_surface': 'grass'|'artificial',
            'grass_performance': Decimal,
            'artificial_performance': Decimal,
            'surface_advantage': Decimal
        }
    """
    analyzer = SurfaceAnalyzer()
    return analyzer.get_team_surface_preference(team_id, season)


def compare_teams_surface_matchup(home_team_id: int, away_team_id: int, 
                                surface_type: str, season: int) -> Dict:
    """
    Compare two teams' performance on a specific surface for matchup analysis.
    
    Returns:
        Surface matchup analysis with advantages and favored team
    """
    analyzer = SurfaceAnalyzer()
    return analyzer.compare_teams_surface_matchup(home_team_id, away_team_id, surface_type, season)


def get_league_surface_distribution(league_id: int, season: int) -> Dict:
    """
    Analyze the distribution of surface types in a league.
    
    Returns:
        League surface distribution with percentages and predominant surface
    """
    analyzer = SurfaceAnalyzer()
    return analyzer.get_league_surface_distribution(league_id, season)