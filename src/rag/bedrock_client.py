"""Thin wrapper around the Bedrock runtime client.

Every boto3/Bedrock call in this project is isolated behind
:class:`BedrockClient` so the rest of the RAG layer (retrieval, agents,
orchestrator) can depend on the plain methods ``embed`` and ``generate``
instead of on boto3 directly, and can be fully unit tested without AWS
credentials or network access.

No AWS credentials or Bedrock access are available in this sandbox, so
nothing in this module is exercised by the test suite - tests inject a
fake object or a plain function in place of a ``BedrockClient`` wherever
one is needed (see ``src/rag/retrieval.py``'s ``embedding_fn`` and the
agents' ``generate_fn`` constructor arguments).

To go live in production:
    - Ensure the deployment role has ``bedrock:InvokeModel`` for the
      configured model IDs.
    - Instantiate ``BedrockClient()`` with no ``client=`` override so it
      builds a real ``boto3.client("bedrock-runtime", ...)``.
    - Pass that instance into ``RagQueryOrchestrator(bedrock_client=...)``
      - everything downstream already calls ``.embed`` / ``.generate``
      through the injected callable, so no other code changes.
"""

from __future__ import annotations

import json
from typing import Any, List, Optional

try:
    import boto3
except ImportError:  # boto3 is a runtime dependency, but keep import optional
    boto3 = None  # type: ignore[assignment]

# Titan embeddings and Claude Haiku via Bedrock are reasonable, low cost
# defaults for this project's ~$100 AUD budget. Override per environment.
DEFAULT_REGION = "ap-southeast-2"
DEFAULT_EMBEDDING_MODEL_ID = "amazon.titan-embed-text-v2:0"
DEFAULT_GENERATION_MODEL_ID = "anthropic.claude-3-haiku-20240307-v1:0"


class BedrockClient:
    """Wraps boto3's ``bedrock-runtime`` client for embeddings and generation."""

    def __init__(
        self,
        region_name: str = DEFAULT_REGION,
        embedding_model_id: str = DEFAULT_EMBEDDING_MODEL_ID,
        generation_model_id: str = DEFAULT_GENERATION_MODEL_ID,
        client: Optional[Any] = None,
    ) -> None:
        """Create a client.

        Pass ``client`` (e.g. a mock or a stub) in tests to avoid ever
        constructing a real boto3 client. When ``client`` is omitted this
        builds a real ``boto3.client("bedrock-runtime", ...)``, which
        requires boto3 to be installed and AWS credentials to be
        configured - neither is available in this sandbox.
        """
        self._embedding_model_id = embedding_model_id
        self._generation_model_id = generation_model_id
        if client is not None:
            self._client = client
        elif boto3 is not None:
            self._client = boto3.client("bedrock-runtime", region_name=region_name)
        else:
            self._client = None

    def embed(self, text: str) -> List[float]:
        """Return an embedding vector for ``text`` via Bedrock Titan embeddings."""
        client = self._require_client()
        body = json.dumps({"inputText": text})
        response = client.invoke_model(
            modelId=self._embedding_model_id,
            body=body,
            contentType="application/json",
            accept="application/json",
        )
        payload = json.loads(response["body"].read())
        return payload["embedding"]

    def generate(self, prompt: str, context: str) -> str:
        """Generate an answer to ``prompt`` grounded in ``context`` via Bedrock."""
        client = self._require_client()
        full_prompt = f"Context:\n{context}\n\nQuestion:\n{prompt}\n\nAnswer:"
        body = json.dumps(
            {
                "anthropic_version": "bedrock-2023-05-31",
                "max_tokens": 1024,
                "messages": [{"role": "user", "content": full_prompt}],
            }
        )
        response = client.invoke_model(
            modelId=self._generation_model_id,
            body=body,
            contentType="application/json",
            accept="application/json",
        )
        payload = json.loads(response["body"].read())
        return payload["content"][0]["text"]

    def _require_client(self) -> Any:
        if self._client is None:
            raise RuntimeError(
                "No bedrock-runtime client available. Install boto3 and "
                "configure AWS credentials, or pass client=... / inject a "
                "fake embed/generate function into the callers of this class."
            )
        return self._client
