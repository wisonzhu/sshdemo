from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from pydantic import BaseModel
import paramiko
import asyncio
import logging

# 配置日志
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

app = FastAPI()


class SSHConnectionParams(BaseModel):
    host: str
    port: int = 22
    username: str
    password: str


async def handle_ssh_stream(websocket: WebSocket, ssh_client: paramiko.SSHClient, channel: paramiko.Channel):
    try:
        while True:
            if channel.recv_ready():
                data = channel.recv(4096).decode('utf-8')
                logger.debug(f"Received from SSH: {data}")
                await websocket.send_text(data)

            try:
                data = await asyncio.wait_for(websocket.receive_text(), timeout=0.1)
                logger.debug(f"Received from WebSocket: {data}")
                channel.send(data)
            except asyncio.TimeoutError:
                pass
    except Exception as e:
        logger.error(f"Error in handle_ssh_stream: {str(e)}")
        await websocket.send_text(f"Error: {str(e)}\r\n")
    finally:
        channel.close()
        ssh_client.close()


@app.websocket("/ssh")
async def ssh_websocket(websocket: WebSocket):
    await websocket.accept()

    try:
        # 直接从 websocket.query_params 获取参数
        params = SSHConnectionParams(
            host=websocket.query_params.get("host", ""),
            port=int(websocket.query_params.get("port", "22")),
            username=websocket.query_params.get("username", ""),
            password=websocket.query_params.get("password", "")
        )

        if not all([params.host, params.username, params.password]):
            await websocket.send_text("Missing connection parameters\r\n")
            await websocket.close()
            return

        ssh_client = paramiko.SSHClient()
        ssh_client.set_missing_host_key_policy(paramiko.AutoAddPolicy())

        logger.debug(f"Attempting SSH connection to {params.host}:{params.port} with {params.username}")
        ssh_client.connect(
            hostname=params.host,
            port=params.port,
            username=params.username,
            password=params.password,
            timeout=10
        )
        await websocket.send_text("Connected to SSH server\r\n")
        logger.debug("SSH connection established")

        channel = ssh_client.invoke_shell()
        await handle_ssh_stream(websocket, ssh_client, channel)

    except WebSocketDisconnect:
        logger.info("WebSocket connection closed by client")
    except paramiko.AuthenticationException as e:
        logger.error(f"SSH authentication failed: {str(e)}")
        await websocket.send_text(f"SSH authentication failed: {str(e)}\r\n")
    except paramiko.SSHException as e:
        logger.error(f"SSH error: {str(e)}")
        await websocket.send_text(f"SSH error: {str(e)}\r\n")
    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}")
        await websocket.send_text(f"Unexpected error: {str(e)}\r\n")
    finally:
        if 'ssh_client' in locals():
            ssh_client.close()
        await websocket.close()


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
