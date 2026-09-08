from langchain_huggingface import HuggingFaceEmbeddings


def get_embedder(model_path: str):
    """Build a local (offline) embedding model.

    Loads from a local directory so runtime never touches the network.
    CPU-only; embeddings are L2-normalized.
    """
    return HuggingFaceEmbeddings(
        model_name=model_path,
        model_kwargs={"device": "cpu"},
        encode_kwargs={"normalize_embeddings": True},
    )
