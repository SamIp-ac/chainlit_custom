## SETUP
MUST use the llm that include function call and tools calling function
Ask Sam for .env file

terminal 1:
```shell
conda create -n mcp_client python=3.12
conda activate mcp_client
pip install chainlit
pip install -r requirements.txt
chainlit run demo.py -w
# open IP and port for others
chainlit run demo.py -w --host 0.0.0.0 --port 8000
# BIG REMARK!!!!!!! OPEN localhost:8000 instead of 0.0.0.0:8000

```
## demo_iter_mcp.py is simulate more iteration on mcp calling, u may run it if u want

## REMOVE watermark:
add: ```custom_css = "/public/custom_styles.css"``` under "[UI]" in file: ".chainlit/config.toml"

## In different terminal:
```shell
# add and multipler calculator
cd customize_api
uvicorn calculator_api:app --reload --host 0.0.0.0 --port 8001
# check flight ticket
cd customize_api
uvicorn flight_api:app --reload --host 0.0.0.0 --port 8002
# data retriever, data on Sam's mac
cd customize_api
uvicorn data_retrievers:app --reload --host 0.0.0.0 --port 8003
# Find attractions
cd customize_api
uvicorn attractions_api:app --reload --host 0.0.0.0 --port 8004
# Find hotel
cd customize_api
uvicorn hotel_api:app --reload --host 0.0.0.0 --port 8005
# Find restaurant
cd customize_api
uvicorn restaurant_api:app --reload --host 0.0.0.0 --port 8006
```

On localhost:8000 Register your api by http://[HOST]:[PORT]/mcp


## Change markdown content on:
/Users/hoyinip/Documents/dev/chainlit_custom/backend/chainlit/markdown.py

## some idea
- maybe try to add re-try/reasoning whenever the answer is not good enough in self-evaluation
