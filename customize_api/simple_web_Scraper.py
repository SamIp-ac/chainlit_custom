# uvicorn simple_web_scraper:app --reload --host 0.0.0.0 --port 8005
from fastapi import FastAPI, Query
from pydantic import BaseModel
from typing import List
from fastapi_mcp import FastApiMCP
from duckduckgo_search import DDGS
import httpx
from bs4 import BeautifulSoup

app = FastAPI(
    title="DuckDuckGo Web Search Extractor",
    description="Performs a DuckDuckGo search and extracts text content from the top result pages.",
    version="1.0",
    docs_url="/docs"
)

# === Output schema ===
class SearchResponse(BaseModel):
    url: str
    title: str
    content: str

@app.get(
    "/web_search",
    response_model=List[SearchResponse],
    summary="Search web and extract content",
    description="Search DuckDuckGo for the input query, fetch the top web pages, and extract their text content (from first 10 paragraphs)."
)
async def web_search(
    query: str = Query(..., description="The search keywords or natural language question."),
    max_results: int = Query(10, ge=8, le=15, description="Number of top URLs to extract content from, suggest using 8.")
):
    """
    Performs a DuckDuckGo search and extracts text from the top N result pages.
    This can be used as an external tool in RAG or agent workflows.
    """
    # Step 1: DuckDuckGo search
    urls = []
    with DDGS() as ddgs:
        for r in ddgs.text(query, max_results=max_results):
            if "href" in r and r["href"].startswith("http"):
                urls.append((r["href"], r.get("title", "Untitled")))
            if len(urls) >= max_results:
                break

    # Step 2: Extract content from each result
    results = []
    async with httpx.AsyncClient(follow_redirects=True, timeout=10.0) as client:
        for url, title in urls:
            try:
                resp = await client.get(url)
                soup = BeautifulSoup(resp.text, "html.parser")
                paragraphs = soup.find_all("p")
                content = "\n".join(p.get_text(strip=True) for p in paragraphs[:10])
                results.append(SearchResponse(url=url, title=title, content=content))
            except Exception as e:
                results.append(SearchResponse(url=url, title="Error", content=str(e)))

    return results

# === Mount FastAPI MCP ===
mcp = FastApiMCP(app)
mcp.mount()

# Optional manual launch
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8005)
