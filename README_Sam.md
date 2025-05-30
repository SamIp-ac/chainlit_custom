## SETUP
MUST use the llm that include function call and tools calling function
```shell
conda create -n mcp_client python=3.12
conda activate mcp_client
pip install chainlit
chainlit run demo.py -w
```
## Change markdown content on:
/Users/hoyinip/Documents/dev/chainlit_custom/backend/chainlit/markdown.py


- maybe try to add re-try/reasoning whenever the answer is not good enough in self-evaluation
