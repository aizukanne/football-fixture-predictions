"""
opponent_archetype_classifier.py - Opponent Archetype Classification Module

Phase 1.5 implementation: Opponent Archetype Segmentation
Extends Phase 1 opponent classification to include archetype-based segmentation.
Classifies opponents by their playing style for more nuanced performance analysis.

This module enables tracking team performance against different opponent playing styles
(archetypes) regardless of the opponent's table position.
"""

from typing import Dict, Optional
from decimal import Decimal
from datetime import datetime
import logging

from .team_classifier import classify_team_archetype

logger = logging.getLogger(__name__)


class OpponentArchetypeClassifier:
    """
    Handles opponent archetype classification for match-level analysis.

    Provides archetype classification with in-memory caching to minimize
    repeated classification calls within a session.

    Attributes:
        ARCHETYPES: List of valid archetype names
        MIN_ARCHETYPE_SEGMENT_MATCHES: Minimum matches required for valid segment
    """

    # All valid archetypes defined in Phase 5
    ARCHETYPES = [
        'ELITE_CONSISTENT',
        'TACTICAL_SPECIALISTS',
        'MOMENTUM_DEPENDENT',
        'HOME_FORTRESS',
        'BIG_GAME_SPECIALISTS',
        'UNPREDICTABLE_CHAOS'
    ]

    # Minimum sample size for archetype segment to be considered valid
    MIN_ARCHETYPE_SEGMENT_MATCHES = 3

    # Default archetype when classification fails
    DEFAULT_ARCHETYPE = 'UNPREDICTABLE_CHAOS'

    def __init__(self):
        """Initialize the classifier with an empty cache."""
        self.logger = logging.getLogger(__name__)
        self._archetype_cache: Dict[str, str] = {}  # In-memory cache for session

    def get_opponent_archetype(self,
                               opponent_id: int,
                               league_id: int,
                               season: int,
                               match_date: Optional[datetime] = None) -> str:
        """
        Get opponent's archetype classification.

        Uses in-memory cache when available, otherwise computes and caches.

        Args:
            opponent_id: Opponent team ID
            league_id: League ID
            season: Season year
            match_date: Optional date for historical point-in-time classification
                       (not currently used but allows for future enhancement)

        Returns:
            str: Archetype name (e.g., 'ELITE_CONSISTENT')
        """
        # Build cache key
        cache_key = f"{opponent_id}_{league_id}_{season}"

        # Try cache first
        if cache_key in self._archetype_cache:
            return self._archetype_cache[cache_key]

        # Compute classification
        try:
            classification = classify_team_archetype(opponent_id, league_id, season)
            archetype = classification.get('primary_archetype', self.DEFAULT_ARCHETYPE)

            # Validate archetype is in known list
            if archetype not in self.ARCHETYPES:
                self.logger.warning(
                    f"Unknown archetype '{archetype}' for team {opponent_id}, "
                    f"using default: {self.DEFAULT_ARCHETYPE}"
                )
                archetype = self.DEFAULT_ARCHETYPE

            # Cache result
            self._archetype_cache[cache_key] = archetype

            self.logger.debug(
                f"Classified opponent {opponent_id} as {archetype} "
                f"(confidence: {classification.get('archetype_confidence', 'N/A')})"
            )

            return archetype

        except Exception as e:
            self.logger.warning(
                f"Failed to classify opponent {opponent_id} archetype: {e}. "
                f"Using default: {self.DEFAULT_ARCHETYPE}"
            )
            # Cache the default to avoid repeated failed lookups
            self._archetype_cache[cache_key] = self.DEFAULT_ARCHETYPE
            return self.DEFAULT_ARCHETYPE

    def get_opponent_archetype_from_match(self,
                                          home_team_id: int,
                                          away_team_id: int,
                                          league_id: int,
                                          season: int,
                                          perspective_team_id: int,
                                          match_date: Optional[datetime] = None) -> str:
        """
        Get opponent archetype from a match, from a specific team's perspective.

        Args:
            home_team_id: Home team ID
            away_team_id: Away team ID
            league_id: League ID
            season: Season year
            perspective_team_id: The team whose perspective we're analyzing
            match_date: Optional match date for historical analysis

        Returns:
            str: Opponent's archetype
        """
        # Determine who the opponent is from our perspective
        if perspective_team_id == home_team_id:
            opponent_id = away_team_id
        elif perspective_team_id == away_team_id:
            opponent_id = home_team_id
        else:
            self.logger.warning(
                f"Team {perspective_team_id} not found in match "
                f"(home={home_team_id}, away={away_team_id}). "
                f"Using default archetype: {self.DEFAULT_ARCHETYPE}"
            )
            return self.DEFAULT_ARCHETYPE

        return self.get_opponent_archetype(opponent_id, league_id, season, match_date)

    def clear_cache(self):
        """Clear the in-memory archetype cache."""
        self._archetype_cache.clear()
        self.logger.info("Archetype cache cleared")

    def get_cache_stats(self) -> Dict:
        """Get statistics about the cache."""
        return {
            'cached_teams': len(self._archetype_cache),
            'cache_keys': list(self._archetype_cache.keys())[:10]  # First 10 for brevity
        }


# Module-level singleton instance for convenience
_classifier_instance: Optional[OpponentArchetypeClassifier] = None


def get_classifier() -> OpponentArchetypeClassifier:
    """Get or create the module-level classifier instance."""
    global _classifier_instance
    if _classifier_instance is None:
        _classifier_instance = OpponentArchetypeClassifier()
    return _classifier_instance


def get_opponent_archetype_from_match(home_team_id: int,
                                      away_team_id: int,
                                      league_id: int,
                                      season: int,
                                      perspective_team_id: int,
                                      match_date: Optional[datetime] = None) -> str:
    """
    Convenience wrapper for OpponentArchetypeClassifier.get_opponent_archetype_from_match().

    Uses a module-level singleton instance for efficiency.

    Args:
        home_team_id: Home team ID
        away_team_id: Away team ID
        league_id: League ID
        season: Season year
        perspective_team_id: The team whose perspective we're analyzing
        match_date: Optional match date for historical analysis

    Returns:
        str: Opponent's archetype
    """
    classifier = get_classifier()
    return classifier.get_opponent_archetype_from_match(
        home_team_id, away_team_id, league_id, season, perspective_team_id, match_date
    )


def get_opponent_archetype(opponent_id: int,
                           league_id: int,
                           season: int,
                           match_date: Optional[datetime] = None) -> str:
    """
    Convenience wrapper for OpponentArchetypeClassifier.get_opponent_archetype().

    Uses a module-level singleton instance for efficiency.

    Args:
        opponent_id: Opponent team ID
        league_id: League ID
        season: Season year
        match_date: Optional match date

    Returns:
        str: Opponent's archetype
    """
    classifier = get_classifier()
    return classifier.get_opponent_archetype(opponent_id, league_id, season, match_date)
