import asyncio
import threading

from dotenv import load_dotenv
from app import create_app

load_dotenv()

app = create_app()

from app.middleware import eureka_middleware

def start_eureka_thread():
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(eureka_middleware.register())

threading.Thread(target=start_eureka_thread, daemon=True).start()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5006, debug=True, use_reloader=False)
    
