from __future__ import annotations

from app import mock_llm


class RecordingClient:
    def __init__(self) -> None:
        self.generations: list[dict] = []

    def update_current_generation(self, **kwargs) -> None:
        self.generations.append(kwargs)


def test_generation_records_model_usage_and_estimated_cost_without_raw_prompt(monkeypatch) -> None:
    client = RecordingClient()
    monkeypatch.setattr(mock_llm, "tracing_enabled", lambda: True)
    monkeypatch.setattr(mock_llm, "get_langfuse_client", lambda: client)

    response = mock_llm.FakeLLM.generate.__wrapped__(
        mock_llm.FakeLLM(), "Question=private test text"
    )

    observation = client.generations[0]
    assert observation["model"] == response.model
    assert observation["usage_details"] == {
        "input": response.usage.input_tokens,
        "output": response.usage.output_tokens,
    }
    assert observation["cost_details"]["input"] >= 0
    assert observation["cost_details"]["output"] >= 0
    assert "private test text" not in str(observation)
