import uvicorn
import os
import asyncio
# PORT = 5700

if __name__ == "__main__":
    PORT = int(os.environ.get("PORT", 5705))
    #asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
    uvicorn.run("crafter:app", host="localhost", port=int(PORT), reload=True, workers=1) # debug=True,