from enum import Enum
from ai.models.gateway import BaseLLMGateway, get_llm_gateway


class TaskComplexity(str, Enum):
    SMALL = "small"      # Classification, metadata extraction, router
    MEDIUM = "medium"    # Requirement extraction, clause segmentation
    STRONG = "strong"    # Policy drafting, complex gap reasoning


class ModelRouter:
    """
    Intelligent Model Router to minimize token cost while maximizing reasoning quality:
    - Small LLM: Classification & Metadata Extraction
    - Medium LLM: Requirement Extraction & Parsing
    - Strong LLM: Cross-Policy Impact & Policy Drafting
    """

    def __init__(self):
        self.gateways = {
            TaskComplexity.SMALL: get_llm_gateway(),
            TaskComplexity.MEDIUM: get_llm_gateway(),
            TaskComplexity.STRONG: get_llm_gateway(),
        }

    def route_task(self, complexity: TaskComplexity) -> BaseLLMGateway:
        return self.gateways.get(complexity, self.gateways[TaskComplexity.STRONG])


_router = None


def get_model_router() -> ModelRouter:
    global _router
    if _router is None:
        _router = ModelRouter()
    return _router
