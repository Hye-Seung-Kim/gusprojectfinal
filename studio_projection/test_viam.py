import asyncio
from viam_client import connect_robot

async def test():
    try:
        robot = await asyncio.wait_for(connect_robot(), timeout=15)
        print("Connected:", robot)
    except Exception as e:
        print("Error:", e)

asyncio.run(test())
