# Interactive Brokers Web API

## Video Walkthrough

https://www.youtube.com/watch?v=CRsH9TKveLo

## Requirements

* Docker Desktop - https://www.docker.com/products/docker-desktop/

## Clone the source code
```
git clone https://github.com/hackingthemarkets/interactive-brokers-web-api.git
```

## Bring up the container
```
docker-compose up
```

## Getting a command line prompt

```
docker exec -it ibkr bash
```


## app2.py
app2.py is the MCP server. It was created by converting the flask app to fastapi app first then add the FastMCP.

added port 3100 in docker-compose.yml for the mcp server. 

both flask app and fastapi app can run together for testing and checking. 



