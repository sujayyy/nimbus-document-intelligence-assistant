import numpy as np
from sentence_transformers import SentenceTransformer

from app.config import settings


class Embedder:

    def __init__(
        self,
        model_name: str = settings.embedding_model,
    ):
        self.model = SentenceTransformer(model_name)

    def embed_documents(
        self,
        texts: list[str],
    ) -> np.ndarray:

        embeddings = self.model.encode(
            texts,
            normalize_embeddings=True,
            convert_to_numpy=True,
            show_progress_bar=True,
        )

        return embeddings.astype("float32")

    def embed_query(
        self,
        text: str,
    ) -> np.ndarray:

        embedding = self.model.encode(
            [text],
            normalize_embeddings=True,
            convert_to_numpy=True,
            show_progress_bar=False,
        )

        return embedding.astype("float32")