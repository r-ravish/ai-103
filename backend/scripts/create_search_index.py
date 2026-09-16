import os
from azure.core.credentials import AzureKeyCredential
from azure.search.documents.indexes import SearchIndexClient
from azure.search.documents.indexes.models import (
    SearchIndex,
    SimpleField,
    SearchableField,
    SearchField,
    SearchFieldDataType,
    VectorSearch,
    HnswAlgorithmConfiguration,
    VectorSearchProfile,
)

ENDPOINT = os.environ["AZURE_SEARCH_ENDPOINT"]
ADMIN_KEY = os.environ["AZURE_SEARCH_ADMIN_KEY"]
INDEX_NAME = "enterprise-knowledge-index"
EMBEDDING_DIMENSIONS = 1536  # text-embedding-3-small

def build_index() -> SearchIndex:
    fields = [
        SimpleField(name="id", type=SearchFieldDataType.String, key=True),
        SimpleField(name="document_id", type=SearchFieldDataType.String, filterable=True),
        SimpleField(name="chunk_index", type=SearchFieldDataType.Int32, filterable=True, sortable=True),
        SearchableField(name="title", type=SearchFieldDataType.String, retrievable=True),
        SearchableField(name="content", type=SearchFieldDataType.String, retrievable=True),
        SearchField(
            name="embedding",
            type=SearchFieldDataType.Collection(SearchFieldDataType.Single),
            searchable=True,
            hidden=True,  # non-retrievable — only used for vector search, never returned
            vector_search_dimensions=EMBEDDING_DIMENSIONS,
            vector_search_profile_name="default-vector-profile",
        ),
        SimpleField(name="source_file", type=SearchFieldDataType.String, filterable=True, retrievable=True),
        SimpleField(name="source_path", type=SearchFieldDataType.String, filterable=True, retrievable=True),
        SimpleField(name="document_type", type=SearchFieldDataType.String, filterable=True, facetable=True),
        SimpleField(
            name="permission_tags",
            type=SearchFieldDataType.Collection(SearchFieldDataType.String),
            filterable=True,
        ),
        SimpleField(
            name="ingested_at",
            type=SearchFieldDataType.DateTimeOffset,
            filterable=True,
            sortable=True,
        ),
    ]

    vector_search = VectorSearch(
        algorithms=[HnswAlgorithmConfiguration(name="hnsw-config")],
        profiles=[
            VectorSearchProfile(
                name="default-vector-profile",
                algorithm_configuration_name="hnsw-config",
            )
        ],
    )

    return SearchIndex(name=INDEX_NAME, fields=fields, vector_search=vector_search)


def main():
    client = SearchIndexClient(endpoint=ENDPOINT, credential=AzureKeyCredential(ADMIN_KEY))
    index = build_index()
    result = client.create_or_update_index(index)
    print(f"Index '{result.name}' created/updated with {len(result.fields)} fields.")


if __name__ == "__main__":
    main()