from abc import ABC, abstractmethod
from datetime import datetime

from common.schema import AgentDescriptor, EvalScore, Signal


class CloudAdapter(ABC):
    """
    Abstract Base Class that every cloud adapter must implement.
    standardizes agent retrieval, signal pulling, and evaluation metrics ingestion.
    """

    @abstractmethod
    def list_agents(self) -> list[AgentDescriptor]:
        """Returns descriptors for all agents managed by this cloud provider."""
        pass

    @abstractmethod
    def pull_signals(self, since: datetime) -> list[Signal]:
        """Pulls and normalizes all recent signals from this cloud since the target time."""
        pass

    @abstractmethod
    def pull_eval_scores(self, since: datetime) -> list[EvalScore]:
        """Pulls and normalizes recent evaluation scores since the target time."""
        pass
