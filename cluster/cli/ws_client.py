import asyncio
import json
import websockets


async def send_message(uri: str, payload: dict):
    async with websockets.connect(uri) as websocket:
        await websocket.send(json.dumps(payload))
        async for message in websocket:
            print(message)


if __name__ == "__main__":
    import sys
    uri = sys.argv[1]
    payload = json.loads(sys.argv[2])
    asyncio.run(send_message(uri, payload))

