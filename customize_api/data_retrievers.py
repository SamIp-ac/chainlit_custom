# uvicorn data_retrievers:app --reload --host 0.0.0.0 --port 8003
from fastapi import FastAPI, Query
from pydantic import BaseModel
from typing import List, Optional
import neo4j
import ast
from neo4j_graphrag.embeddings.ollama import OllamaEmbeddings
from neo4j_graphrag.retrievers import VectorRetriever
from fastapi_mcp import FastApiMCP

# === Configuration ===
NEO4J_URI = "neo4j://localhost:7687"
NEO4J_AUTH = ("neo4j", "neo4jneo4j")
NEO4J_DATABASE = "neo4j"
VECTOR_INDEX_NAME = "myVectorIndex"

# === FastAPI app ===
app = FastAPI(title="Vector Similarity Search API", description="Search similar content using Neo4j + Ollama embeddings", version="1.0")

# === Response Schema ===
class SearchResult(BaseModel):
    text: str

# === Initialize Neo4j driver and retriever ===
driver = neo4j.GraphDatabase.driver(NEO4J_URI, auth=NEO4J_AUTH)
retriever = VectorRetriever(
    driver=driver,
    index_name=VECTOR_INDEX_NAME,
    embedder=OllamaEmbeddings(model="bge-m3:latest"),
    neo4j_database=NEO4J_DATABASE
)

@app.get("/similarity_search", response_model=List[SearchResult])
async def similarity_search(
    query_text: str = Query(..., description="The input query to search similar content for."),
    top_k: int = Query(5, ge=1, le=20, description="Number of top results to retrieve, better use 6.")
):
    """
    Perform vector similarity search on the Neo4j vector index using Ollama embeddings (bge-m3).
    """
    results = retriever.search(query_text=query_text, top_k=top_k)

    response = []
    for item in results.items:
        try:
            content_dict = ast.literal_eval(item.content)
            response.append({"text": content_dict.get("text", "")})
        except Exception as e:
            response.append({"text": f"[Error parsing content]: {str(e)}"})

    return response


mcp = FastApiMCP(app)

# Mount the MCP server directly to your FastAPI app
mcp.mount()