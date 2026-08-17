import json
import logging
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, List
from pydantic import BaseModel
from services.api.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


class LLMResponse(BaseModel):
    content: str
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    model_name: str
    raw_response: Optional[Dict[str, Any]] = None


class BaseLLMGateway(ABC):
    @abstractmethod
    async def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.1,
        max_tokens: int = 2000,
    ) -> LLMResponse:
        pass


class MockComplianceLLM(BaseLLMGateway):
    """
    Deterministic Mock LLM for high-speed testing, evaluations, and CI/CD pipelines.
    Generates structured compliance interpretations, gap analysis, and policy amendments.
    """

    async def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.1,
        max_tokens: int = 2000,
    ) -> LLMResponse:
        prompt_lower = prompt.lower()
        
        # Policy Gap Identification
        if "identify gaps" in prompt_lower or "gap analysis" in prompt_lower:
            mock_output = json.dumps([
                {
                    "policy_code": "POL-INF-001",
                    "policy_title": "Information Security & API Management Policy",
                    "clause_number": "Clause 4.2",
                    "gap_description": "Current policy requires API key rotation every 180 days; new circular mandates 90 days rotation and automated revocation.",
                    "severity": "HIGH",
                    "impacted_controls": ["CTL-SEC-09"],
                },
                {
                    "policy_code": "POL-AML-001",
                    "policy_title": "Anti-Money Laundering & KYC Policy",
                    "clause_number": "Clause 3.1",
                    "gap_description": "Lacks explicit mandate for video-based customer identification process (V-CIP) automated geo-tagging.",
                    "severity": "MEDIUM",
                    "impacted_controls": ["CTL-AML-02"],
                }
            ], indent=2)

        # Policy Drafting
        elif "draft policy amendment" in prompt_lower or "propose changes" in prompt_lower:
            mock_output = json.dumps([
                {
                    "policy_code": "POL-INF-001",
                    "clause_number": "Clause 4.2.1",
                    "change_type": "AMENDMENT",
                    "original_text": "All internal and partner API keys and security credentials shall be rotated at least every 180 calendar days.",
                    "proposed_text": "All banking, partner, and customer-facing API keys, secret tokens, and cryptographic credentials shall be systematically rotated at least every 90 calendar days. Automated revocation and audit alerts must trigger immediately upon detection of credential exposure or inactivity exceeding 30 days.",
                    "justification": "Direct compliance alignment with Circular Section 4.1 requiring 90-day cryptographic credential lifecycle and real-time invalidation.",
                    "citations": [
                        {
                            "doc": "RBI/2026-27/04",
                            "section": "Section 4.1",
                            "quote": "Regulated entities shall ensure cryptographic keys and API tokens are rotated at intervals not exceeding 90 days."
                        }
                    ]
                }
            ], indent=2)

        # Requirement Classification
        elif "classify" in prompt_lower:
            mock_output = json.dumps({
                "classification": "REGULATORY_CIRCULAR",
                "jurisdiction": "IN",
                "risk_domain": "Cybersecurity & IT Infrastructure",
                "actionability": "IMMEDIATE_ACTION_REQUIRED",
                "effective_days_remaining": 60
            }, indent=2)

        # Default fallback
        else:
            mock_output = json.dumps({
                "summary": "Processed regulatory context successfully with full citation traceability.",
                "status": "VALIDATED"
            })

        return LLMResponse(
            content=mock_output,
            prompt_tokens=len(prompt.split()),
            completion_tokens=len(mock_output.split()),
            total_tokens=len(prompt.split()) + len(mock_output.split()),
            model_name="mock-compliance-v1",
        )


class BedrockLLMGateway(BaseLLMGateway):
    """AWS Bedrock Claude 3.5 Sonnet / Haiku integration."""

    def __init__(self, model_id: str = "anthropic.claude-3-5-sonnet-20240620-v1:0"):
        self.model_id = model_id
        self.region = settings.BEDROCK_REGION

    async def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.1,
        max_tokens: int = 2000,
    ) -> LLMResponse:
        try:
            import boto3
            client = boto3.client("bedrock-runtime", region_name=self.region)
            body = {
                "anthropic_version": "bedrock-2023-05-31",
                "max_tokens": max_tokens,
                "temperature": temperature,
                "messages": [{"role": "user", "content": prompt}],
            }
            if system_prompt:
                body["system"] = system_prompt

            response = client.invoke_model(
                modelId=self.model_id,
                body=json.dumps(body),
            )
            response_body = json.loads(response["body"].read())
            content = response_body["content"][0]["text"]
            usage = response_body.get("usage", {})

            return LLMResponse(
                content=content,
                prompt_tokens=usage.get("input_tokens", 0),
                completion_tokens=usage.get("output_tokens", 0),
                total_tokens=usage.get("input_tokens", 0) + usage.get("output_tokens", 0),
                model_name=self.model_id,
                raw_response=response_body,
            )
        except Exception as e:
            logger.warning(f"Bedrock invocation failed: {e}. Falling back to mock engine.")
            mock = MockComplianceLLM()
            return await mock.generate(prompt, system_prompt, temperature, max_tokens)


def get_llm_gateway(provider: Optional[str] = None) -> BaseLLMGateway:
    selected_provider = provider or settings.DEFAULT_LLM_PROVIDER
    if selected_provider == "bedrock":
        return BedrockLLMGateway()
    return MockComplianceLLM()


# Re-exports from ai.models.embeddings
from ai.models.embeddings import (
    BaseEmbeddingGateway,
    BedrockCohereEmbeddingGateway,
    MockEmbeddingGateway,
    BaseRerankerGateway,
    BedrockCohereRerankerGateway,
    MockRerankerGateway,
    get_embedding_gateway,
    get_reranker_gateway,
)

