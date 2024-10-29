from dotenv import load_dotenv
load_dotenv()

import os

from openai import OpenAI

from typing import Any

OPENAI_EMBEDDING_MODEL = os.getenv('OPENAI_EMBEDDING_MODEL')

embed_model_dims = int(os.getenv('OPENAI_EMBEDDING_MODEL_DIMS')) # ref: https://platform.openai.com/docs/models/embeddings
print(f'{embed_model_dims=}')

client = OpenAI(api_key=os.getenv('OPENAI_EMBEDDING_API_KEY'))

def embed_filing_chunk(chunk: str) -> list[float]:
    response = _do_embedding_request(chunk)
    embedding = response.data[0].embedding
    return embedding

def embed_filing_chunks(chunks: list[str]) -> list[list[float]]:
    response = _do_embedding_request(chunks)
    embeddings = [obj.embedding for obj in response.data]
    return embeddings

def _do_embedding_request(input) -> Any:
    response = client.embeddings.create(input=input, model=OPENAI_EMBEDDING_MODEL, dimensions=embed_model_dims)
    return response

if __name__ == '__main__':
    chunk = 'Includes $3.6 billion of debt at face value related to the Activision Blizzard acquisition.'
    embedding = embed_filing_chunk(chunk)
    print(f'{len(embedding)=} {embedding}')
