from abc import ABC, abstractmethod

from common.schema import AgentDescriptor, AgentRequest, AgentResponse


class Agent(ABC):
    descriptor: AgentDescriptor

    @abstractmethod
    def handle(self, req: AgentRequest) -> AgentResponse:
        """
        Processes an incoming AgentRequest and returns a valid AgentResponse.
        This must support both MOCK and real platform execution paths.
        """
        pass
