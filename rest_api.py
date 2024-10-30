from dotenv import load_dotenv
load_dotenv()

import os
import requests
import uvicorn

from fastapi import FastAPI
from threading import Thread

app = FastAPI()
REST_API_PORT = os.getenv('REST_API_PORT', uvicorn.Config(app).port)

@app.get('/heartbeat')
def heartbeat():
    return 'OK'

def _run_rest_api():
    uvicorn.run(app, host='0.0.0.0', port=REST_API_PORT)

api_thread = Thread(target=_run_rest_api)
api_thread.daemon = True
api_thread.start()

def send_heartbeat():
    try:
        response = requests.get(f'http://localhost:{REST_API_PORT}/heartbeat')
        print(f'heartbeat {response.text}')
    except Exception as e:
        print(f'Error: heartbeat -> {e}')

if __name__ == '__main__':
    # test usage
    send_heartbeat()