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
# OPEN localhost:8000 not 0.0.0.0:8000
```


terminal n:
```shell
cd customize_api
# add and multipler calculator
uvicorn calculator_api:app --reload --host 0.0.0.0 --port 8001
# check flight ticket
uvicorn flight_api:app --reload --host 0.0.0.0 --port 8002
# data retriever, data on Sam's mac
uvicorn data_retrievers:app --reload --host 0.0.0.0 --port 8003

uvicorn kkday_api:app --reload --host 0.0.0.0 --port 8004
```

On localhost:8000 Register your api by http://[HOST]:[PORT]/mcp


## Change markdown content on:
/Users/hoyinip/Documents/dev/chainlit_custom/backend/chainlit/markdown.py

## some idea
- maybe try to add re-try/reasoning whenever the answer is not good enough in self-evaluation
