import os

from openai import AzureOpenAI
from azure.core.credentials import AzureKeyCredential
from azure.search.documents import SearchClient
from azure.search.documents.models import VectorizedQuery

# --- Config ---
SEARCH_ENDPOINT = os.environ["AZURE_SEARCH_ENDPOINT"]
SEARCH_ADMIN_KEY = os.environ["AZURE_SEARCH_ADMIN_KEY"]
INDEX_NAME = "enterprise-knowledge-index"

AOAI_ENDPOINT = os.environ["AZURE_OPENAI_ENDPOINT"]
AOAI_API_KEY = os.environ["AZURE_OPENAI_API_KEY"]
AOAI_API_VERSION = os.environ.get("AZURE_OPENAI_API_VERSION", "2024-10-21")
AOAI_EMBEDDING_DEPLOYMENT = os.environ["AZURE_OPENAI_EMBEDDING_DEPLOYMENT"]

TOP_K = 3

# Swap these for questions drawn from Aditya's eval set once it lands
TEST_QUESTIONS = [
    "How many days of paid leave do I get per year?",
    "Can I expense a laptop bag under the reimbursement policy?",
    "What are the rules for working from home?",
    "What VPN requirements does IT security policy specify?",
]


def embed_query(client: AzureOpenAI, query: str):
    response = client.embeddings.create(
        model=AOAI_EMBEDDING_DEPLOYMENT,
        input=[query],
    )
    return response.data[0].embedding


def run_search(search_client: SearchClient, query_vector: list, top_k: int = TOP_K):
    vector_query = VectorizedQuery(
        vector=query_vector,
        k_nearest_neighbors=top_k,
        fields="embedding",
    )
    results = search_client.search(
        search_text=None,
        vector_queries=[vector_query],
        select=["title", "content", "source_file", "document_id", "chunk_index", "document_type"],
        top=top_k,
    )
    return list(results)


def print_results(question: str, results: list):
    print(f"\nQ: {question}")
    if not results:
        print("  No results.")
        return
    for r in results:
        score = r["@search.score"]
        preview = r["content"].replace("\n", " ")[:150]
        print(f"  [{score:.4f}] {r['document_id']} / {r['source_file']} (chunk {r['chunk_index']}) — {r['title']}")
        print(f"    {preview}...")


def main():
    aoai_client = AzureOpenAI(
        azure_endpoint=AOAI_ENDPOINT,
        api_key=AOAI_API_KEY,
        api_version=AOAI_API_VERSION,
    )
    search_client = SearchClient(
        endpoint=SEARCH_ENDPOINT,
        index_name=INDEX_NAME,
        credential=AzureKeyCredential(SEARCH_ADMIN_KEY),
    )

    for question in TEST_QUESTIONS:
        query_vector = embed_query(aoai_client, question)
        results = run_search(search_client, query_vector)
        print_results(question, results)


if __name__ == "__main__":
    main()