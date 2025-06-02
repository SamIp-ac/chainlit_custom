# uvicorn calculator_api:app --reload --host 0.0.0.0 --port 8001

import uvicorn
import ast
import operator as op
from fastapi import FastAPI, Query, HTTPException
from fastapi.responses import RedirectResponse
from fastapi_mcp import FastApiMCP

# 安全支持的運算符對應表
operators = {
    ast.Add: op.add,
    ast.Sub: op.sub,
    ast.Mult: op.mul,
    ast.Div: op.truediv,
    ast.USub: op.neg,
    ast.Pow: op.pow,
    ast.Mod: op.mod,
    # 可按需增加
}

def safe_eval(expr: str):
    """
    使用 AST 安全地解析並計算數學表達式
    """
    def _eval(node):
        if isinstance(node, ast.Num):  # 數字
            return node.n
        elif isinstance(node, ast.BinOp):  # 二元運算
            return operators[type(node.op)](_eval(node.left), _eval(node.right))
        elif isinstance(node, ast.UnaryOp):  # 單目運算（如 -1）
            return operators[type(node.op)](_eval(node.operand))
        else:
            raise ValueError("不支持的表達式類型")

    try:
        tree = ast.parse(expr, mode='eval')
        return _eval(tree.body)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"表達式無效: {str(e)}")

# 初始化 FastAPI 應用
app = FastAPI(
    title="進階計算器 API",
    description="支援四則運算與複雜表達式解析的計算器，適用於 FastAPI-MCP。",
    version="2.0.0",
)

@app.get("/calculate", summary="執行數學運算", tags=["數學計算"])
async def calculate(
    expression: str = Query(..., description="數學表達式，如 '1 + 2 * (3 + 4)'")
):
    """
    計算指定的數學表達式。

    - **expression**: 輸入的表達式，如：
      - `1 + 2`
      - `3 * (4 + 5)`
      - `10 / (2 + 3)`

    🚫 不允許任意 Python 代碼，只允許四則運算。
    """
    result = safe_eval(expression)
    return {
        "expression": expression,
        "result": result
    }

@app.get("/", include_in_schema=False)
async def root_redirect_to_docs():
    return RedirectResponse(url="/docs")

# 啟用 MCP
mcp = FastApiMCP(app)
mcp.mount()

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8001)
