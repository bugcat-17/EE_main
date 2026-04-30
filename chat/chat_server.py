# v2/chat/socket_events.py
import socketio
import re
from typing import Any

ROOM_PATTERN = re.compile(r"^[a-zA-Z0-9:_\-]{1,128}$")

def _valid_room(room_id: str) -> bool:
    return bool(room_id and ROOM_PATTERN.match(room_id))

def register_socket_events(sio: socketio.AsyncServer):
    @sio.event
    async def connect(sid, environ, auth):
        print(f"클라이언트 연결됨: {sid}")
        return True

    @sio.event
    async def identify(sid, data):
        user_id = str(data.get("user_id") or "").strip()
        role = str(data.get("role") or "").strip()
        await sio.save_session(sid, {"user_id": user_id, "role": role})
        await sio.emit("identified", {"user_id": user_id, "role": role}, to=sid)

    @sio.event
    async def join_room(sid, data):
        room_id = str(data.get("room_id") or "")
        if _valid_room(room_id):
            await sio.enter_room(sid, room_id)
            await sio.emit("joined", {"room_id": room_id}, to=sid)

    @sio.event
    async def chat_message(sid, data):
        room_id = str(data.get("room_id") or "")
        text = str(data.get("text") or "").strip()
        session = await sio.get_session(sid)
        
        await sio.emit("chat_message", {
            "room_id": room_id,
            "text": text,
            "sender_id": session.get("user_id"),
            "role": session.get("role")
        }, room=room_id, skip_sid=sid)
        
        await sio.emit("chat_message", {
            "room_id": room_id, "text": text, "me": True
        }, to=sid)