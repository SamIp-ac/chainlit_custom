# uvicorn calculator_api:app --reload --host 0.0.0.0 --port 8001
import uvicorn
from fastapi import FastAPI, Query
from fastapi.responses import RedirectResponse
from fastapi_mcp import FastApiMCP

# 1. 初始化 FastAPI 应用，并添加标题和描述
app = FastAPI(
    title="简单计算器 API",
    description="这是一个提供两个数字加法和乘法运算的 API。所有操作都在此单一文档页面上可用。",
    version="1.0.0",
)

# 2. 定义 API 端点

@app.get("/add", summary="两数相加", tags=["数学运算"])
async def add_numbers(
    num1: float = Query(..., description="第一个加数。"),
    num2: float = Query(..., description="第二个加数。")
):
    """
    接收两个数字 **num1** 和 **num2** 作为查询参数，并返回它们的和。

    - **num1**: 浮点数，必需。
    - **num2**: 浮点数，必需。

    示例请求: `/add?num1=5.5&num2=4.5`
    """
    result = num1 + num2
    return {
        "operation": "addition",
        "num1": num1,
        "num2": num2,
        "sum": result
    }

@app.get("/multiply", summary="两数相乘", tags=["数学运算"])
async def multiply_numbers(
    num1: float = Query(..., description="第一个乘数。"),
    num2: float = Query(..., description="第二个乘数。")
):
    """
    接收两个数字 **num1** 和 **num2** 作为查询参数，并返回它们的积。

    - **num1**: 浮点数，必需。
    - **num2**: 浮点数，必需。

    示例请求: `/multiply?num1=3&num2=7`
    """
    result = num1 * num2
    return {
        "operation": "multiplication",
        "num1": num1,
        "num2": num2,
        "product": result
    }

# 3. (可选) 添加一个根路径重定向到文档页面
@app.get("/", include_in_schema=False) # include_in_schema=False 表示不在 API 文档中显示此端点
async def root_redirect_to_docs():
    return RedirectResponse(url="/docs")

mcp = FastApiMCP(app)

# Mount the MCP server directly to your FastAPI app
mcp.mount()
# 4. 运行 FastAPI 应用 (如果你直接运行此脚本)
if __name__ == "__main__":
    # 运行命令: uvicorn calculator_api.py:app --reload --port 8001
    # 例如，如果你的文件名是 main.py, 则运行: uvicorn main:app --reload --port 8001
    # 然后在浏览器中打开 http://127.0.0.1:8080/docs 查看 API 文档
    uvicorn.run(app, host="0.0.0.0", port=8001)