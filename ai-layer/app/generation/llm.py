from anthropic import Anthropic
from app.config import settings


class LLMClient:
    def __init__(self):
        self.client = Anthropic(api_key=settings.anthropic_api_key)
        self.model = settings.llm_model
        self.max_tokens = settings.llm_max_tokens

    def generate(self, system_prompt: str, user_prompt: str) -> str:
        response = self.client.messages.create(
            model=self.model,
            max_tokens=self.max_tokens,
            system=system_prompt,
            messages=[
                {
                    "role": "user",
                    "content": user_prompt,
                }
            ],
        )

        text_blocks = [
            block.text
            for block in response.content
            if block.type == "text"
        ]

        return "\n".join(text_blocks).strip()

    def generate_stream(self, system_prompt: str, user_prompt: str):
        with self.client.messages.stream(
            model=self.model,
            max_tokens=self.max_tokens,
            system=system_prompt,
            messages=[
                {
                    "role": "user",
                    "content": user_prompt,
                }
            ],
        ) as stream:

            for text in stream.text_stream:
                yield text