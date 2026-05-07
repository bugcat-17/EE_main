import socketio
from database import SessionLocal
import models

# 1. @sio.on 대신 함수 내부에서 정의하도록 변경
def register_socket_events(sio):
    # 접속 중인 사용자 관리
    connected_users = {}

    @sio.event
    async def connect(sid, environ):
        connected_users[sid] = f"User_{sid[:4]}"
        print(f"✅ 접속 (SID: {sid})")

    # 2. @sio.on 대신 sio.on() 메서드를 사용하거나 
    # 함수 안에 데코레이터를 넣습니다.
    @sio.on('identify')
    async def handle_identify(sid, data):
        nickname = data.get('nickname', f"User_{sid[:4]}")
        connected_users[sid] = nickname
        
        db = SessionLocal()
        prev_messages = db.query(models.ChatLog).order_by(models.ChatLog.id.desc()).limit(30).all()
        db.close()

        for msg in reversed(prev_messages):
            await sio.emit('receive_message', {
                'nickname': msg.nickname,
                'message': msg.message
            }, to=sid)

    @sio.on('send_message')
    async def handle_send_message(sid, data):
        nickname = connected_users.get(sid, "Unknown")
        message = data.get('message')
        if not message: return

        db = SessionLocal()
        new_log = models.ChatLog(nickname=nickname, message=message)
        db.add(new_log)
        db.commit()
        db.close()

        await sio.emit('receive_message', {'nickname': nickname, 'message': message})

    @sio.on('set_nickname')
    async def handle_set_nickname(sid, new_nickname):
        connected_users[sid] = new_nickname