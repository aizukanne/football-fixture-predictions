"""
segment_selector.py - Intelligent Segment Selection Module

Phase 1.5 implementation: Opponent Archetype Segmentation
Implements fallback logic for selecting appropriate segmented parameters
based on data availability and confidence thresholds.

Fallback hierarchy:
1. Archetype segment (if >= MIN_SEGMENT_SAMPLE_SIZE matches)
2. Table position segment (vs_top/vs_middle/vs_bottom)
3. Overall team parameters
"""

from typing import Dict, Tuple, Optional
from decimal import Decimal
import logging

from .opponent_classifier import OpponentClassifier
from .opponent_archetype_classifier import OpponentArchetypeClassifier

logger = logging.getLogger(__name__)


class SegmentSelector:
    """
    Intelligently selects the best available segmented parameters
    with confidence-based fallback logic.

    This class implements a three-tier fallback hierarchy:
    1. Archetype-based segmentation (e.g., vs_TACTICAL_SPECIALISTS)
    2. Position-based segmentation (e.g., vs_top, vs_middle, vs_bottom)
    3. Overall team parameters

    Attributes:
        MIN_SEGMENT_SAMPLE_SIZE: Minimum matches required for a segment to be valid
        MIN_CONFIDENCE_THRESHOLD: Minimum confidence for segment usage
    """

    MIN_SEGMENT_SAMPLE_SIZE = 3
    MIN_CONFIDENCE_THRESHOLD = Decimal('0.5')

    def __init__(self):
        """Initialize with position and archetype classifiers."""
        self.position_classifier = OpponentClassifier()
        self.archetype_classifier = OpponentArchetypeClassifier()
        self.logger = logging.getLogger(__name__)

    def select_best_segment(self,
                            team_params: Dict,
                            opponent_team_id: int,
                            league_id: int,
                            season: int,
                            prefer_archetype: bool = True) -> Tuple[Dict, Dict]:
        """
        Select the best available segmented parameters for a matchup.

        Implements three-tier fallback:
        1. Archetype segment (if sufficient data and prefer_archetype=True)
        2. Table position segment
        3. Overall team parameters

        Args:
            team_params: Complete team parameters with segmented_params
                        and archetype_segmented_params
            opponent_team_id: Opponent's team ID
            league_id: League ID
            season: Season year
            prefer_archetype: Whether to prefer archetype over position segmentation

        Returns:
            Tuple of (selected_params, metadata)
            - selected_params: The parameter dict to use for predictions
            - metadata: Information about selection including source and confidence
        """
        metadata = {
            'selection_source': None,
            'segment_key': None,
            'sample_size': 0,
            'confidence': Decimal('0.5'),
            'fallback_chain': [],
            'opponent_archetype': None,
            'opponent_tier': None
        }

        # Get opponent classifications
        try:
            opponent_archetype = self.archetype_classifier.get_opponent_archetype(
                opponent_team_id, league_id, season
            )
            metadata['opponent_archetype'] = opponent_archetype
        except Exception as e:
            self.logger.warning(f"Failed to get opponent archetype: {e}")
            opponent_archetype = None

        try:
            opponent_tier = self.position_classifier.get_team_tier(
                opponent_team_id, league_id, str(season)
            )
            metadata['opponent_tier'] = opponent_tier
        except Exception as e:
            self.logger.warning(f"Failed to get opponent tier: {e}")
            opponent_tier = None

        # Try archetype segment first (if preferred and available)
        if prefer_archetype and opponent_archetype:
            archetype_key = f'vs_{opponent_archetype}'
            archetype_params = team_params.get('archetype_segmented_params', {})

            if archetype_key in archetype_params:
                segment = archetype_params[archetype_key]
                sample_size = segment.get('segment_sample_size', 0)
                is_valid = segment.get('archetype_segment_valid', False)

                if sample_size >= self.MIN_SEGMENT_SAMPLE_SIZE and is_valid:
                    metadata['selection_source'] = 'archetype_segment'
                    metadata['segment_key'] = archetype_key
                    metadata['sample_size'] = sample_size
                    metadata['confidence'] = self._calculate_segment_confidence(segment)

                    # Merge with base params (base params provide fallback values)
                    selected = {**team_params, **segment}
                    # Remove nested segmented params to avoid confusion
                    selected.pop('segmented_params', None)
                    selected.pop('archetype_segmented_params', None)

                    self.logger.info(
                        f"Using archetype segment {archetype_key} "
                        f"(n={sample_size}, confidence={metadata['confidence']})"
                    )
                    return selected, metadata
                else:
                    metadata['fallback_chain'].append(
                        f'archetype:{archetype_key}:insufficient_data(n={sample_size})'
                    )
            else:
                metadata['fallback_chain'].append(
                    f'archetype:{archetype_key}:not_found'
                )

        # Try table position segment
        if opponent_tier:
            position_key = f'vs_{opponent_tier}'
            position_params = team_params.get('segmented_params', {})

            if position_key in position_params:
                segment = position_params[position_key]
                sample_size = segment.get('segment_sample_size', 0)

                if sample_size >= self.MIN_SEGMENT_SAMPLE_SIZE:
                    metadata['selection_source'] = 'position_segment'
                    metadata['segment_key'] = position_key
                    metadata['sample_size'] = sample_size
                    metadata['confidence'] = self._calculate_segment_confidence(segment)

                    # Merge with base params
                    selected = {**team_params, **segment}
                    selected.pop('segmented_params', None)
                    selected.pop('archetype_segmented_params', None)

                    self.logger.info(
                        f"Using position segment {position_key} "
                        f"(n={sample_size}, confidence={metadata['confidence']})"
                    )
                    return selected, metadata
                else:
                    metadata['fallback_chain'].append(
                        f'position:{position_key}:insufficient_data(n={sample_size})'
                    )
            else:
                metadata['fallback_chain'].append(
                    f'position:{position_key}:not_found'
                )

        # Fall back to overall parameters
        metadata['selection_source'] = 'overall'
        metadata['segment_key'] = None
        metadata['sample_size'] = team_params.get('sample_size', 0)
        metadata['confidence'] = Decimal('0.6')  # Base confidence for overall

        self.logger.info(
            f"Using overall parameters (fallback). "
            f"Chain: {' -> '.join(metadata['fallback_chain']) or 'direct'}"
        )
        return team_params, metadata

    def _calculate_segment_confidence(self, segment: Dict) -> Decimal:
        """
        Calculate confidence score for a segment based on sample size and validity.

        Confidence is based on:
        - Sample size (more matches = higher confidence, capped at 10)
        - Whether segment uses actual data vs fallback values

        Args:
            segment: The segment parameters dict

        Returns:
            Decimal: Confidence score between 0.3 and 1.0
        """
        sample_size = segment.get('segment_sample_size', 0)

        # Confidence scales with sample size (capped at 10 matches for full confidence)
        # Base: 0.3, Max from sample size: 0.3
        base_confidence = min(sample_size / 10.0, 1.0) * 0.3

        # Add bonus for using actual segment data vs fallback
        # If segment is using calculated home/away data, add confidence
        if segment.get('using_segment_home') and segment.get('using_segment_away'):
            base_confidence += 0.4
        elif segment.get('using_segment_home') or segment.get('using_segment_away'):
            base_confidence += 0.2

        # Ensure minimum confidence of 0.3
        final_confidence = max(0.3, base_confidence + 0.3)

        return Decimal(str(round(min(1.0, final_confidence), 3)))


# Module-level convenience functions

_selector_instance: Optional[SegmentSelector] = None


def get_selector() -> SegmentSelector:
    """Get or create the module-level selector instance."""
    global _selector_instance
    if _selector_instance is None:
        _selector_instance = SegmentSelector()
    return _selector_instance


def select_segmented_params(team_params: Dict,
                            opponent_team_id: int,
                            league_id: int,
                            season: int,
                            prefer_archetype: bool = True) -> Tuple[Dict, Dict]:
    """
    Convenience function for segment selection.

    Uses a module-level singleton instance for efficiency.

    Args:
        team_params: Complete team parameters dictionary
        opponent_team_id: Opponent's team ID
        league_id: League ID
        season: Season year
        prefer_archetype: Whether to prefer archetype segmentation

    Returns:
        Tuple of (selected_params, selection_metadata)
    """
    selector = get_selector()
    return selector.select_best_segment(
        team_params, opponent_team_id, league_id, season, prefer_archetype
    )
