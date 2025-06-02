# uvicorn data_retrievers:app --reload --host 0.0.0.0 --port 8003
from fastapi import FastAPI, Query
from pydantic import BaseModel
from typing import List, Optional
import neo4j
import ast
import os

from fastapi_mcp import FastApiMCP
from neo4j_graphrag.embeddings.ollama import OllamaEmbeddings
from neo4j_graphrag.retrievers import VectorRetriever, VectorCypherRetriever
from neo4j_graphrag.llm import OpenAILLM
from neo4j_graphrag.generation import GraphRAG

# === Configuration ===
IP_ADDRESS = "localhost"
NEO4J_URI = f"neo4j://{IP_ADDRESS}:7687"
NEO4J_AUTH = ("neo4j", "neo4jneo4j")
NEO4J_DATABASE = "neo4j"
VECTOR_INDEX_NAME = "myVectorIndex"
RETRIEVAL_QUERY = "WITH node, score RETURN node.text AS text_content, node.id AS chunk_id, score"

# === Initialize FastAPI ===
app = FastAPI(
    title="Neo4j RAG + Similarity API",
    description="Combined API for vector similarity search and RAG-based answering using Neo4j and Ollama.",
    version="1.0"
)

# === Schemas ===
class SearchResult(BaseModel):
    text: str

class RAGResponse(BaseModel):
    question: str
    answer: str
    retrieved_contexts: List[str]

# === Neo4j and embedding initialization ===
driver = neo4j.GraphDatabase.driver(NEO4J_URI, auth=NEO4J_AUTH)
embedder = OllamaEmbeddings(model="bge-m3:latest")

# === Similarity search retriever ===
similarity_retriever = VectorRetriever(
    driver=driver,
    index_name=VECTOR_INDEX_NAME,
    embedder=embedder,
    neo4j_database=NEO4J_DATABASE
)

# === RAG retriever and LLM ===
rag_retriever = VectorCypherRetriever(
    driver,
    index_name=VECTOR_INDEX_NAME,
    retrieval_query=RETRIEVAL_QUERY,
    embedder=embedder,
    neo4j_database=NEO4J_DATABASE,
)

llm = OpenAILLM(
    model_name="gemma3:12b",
    api_key="ollama",
    base_url="http://localhost:11434/v1",
    model_params={
        "max_tokens": 4000,
        "temperature": 0,
    },
)

rag = GraphRAG(
    retriever=rag_retriever,
    llm=llm,
)

# === Endpoint: Vector Similarity Search ===
@app.get("/similarity_search", response_model=List[SearchResult])
async def similarity_search(
    query_text: str = Query(..., description="Input query for vector similarity search."),
    top_k: int = Query(5, ge=1, le=20, description="Number of top results to retrieve.")
):
    results = similarity_retriever.search(query_text=query_text, top_k=top_k)

    response = []
    for item in results.items:
        try:
            content_dict = ast.literal_eval(item.content)
            response.append({"text": content_dict.get("text", "")})
        except Exception as e:
            response.append({"text": f"[Error parsing content]: {str(e)}"})

    return response

# === Endpoint: RAG Answering with Chat History ===
@app.get("/rag_answer", response_model=RAGResponse)
async def rag_answer(
    question: str = Query(..., description="The question to answer using RAG."),
):
    try:
        print(f"Received question: {question}")
        history: List[dict[str, str]] = []

        result = rag.search(
            question,
            return_context=True,
            message_history=history,
        )

        print("RAG answer generated successfully.")

        contexts = [item.content for item in result.retriever_result.items]

        history.append({"role": "user", "content": question})
        history.append({"role": "assistant", "content": result.answer})

        return {
            "question": question,
            "answer": result.answer,
            "retrieved_contexts": contexts
        }

    except Exception as e:
        import traceback
        traceback.print_exc()
        return {
            "question": question,
            "answer": "[Error occurred during processing]",
            "retrieved_contexts": [str(e)]
        }


# === Mount MCP for tool usage ===
mcp = FastApiMCP(app)
mcp.mount()
