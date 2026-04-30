import socketio
from database import SessionLocal
import models

def register_socket_events(sio):
    # 접속 중인 사용자 관리 (sid -> nickname)
    connected_users = {}

    @sio.event
    async def connect(sid, environ):
        # 접속 시 임시 닉네임 부여 (예: User_a1b2)
        temp_nickname = f"User_{sid[:4]}"
        connected_users[sid] = temp_nickname
        
        # 이전 채팅 기록 30개 불러와서 전송 (선택 사항)
        db = SessionLocal()
        prev_messages = db.query(models.ChatLog).order_by(models.ChatLog.id.desc()).limit(30).all()
        db.close()
        
        # 과거 메시지를 역순으로 보내줌
        for msg in reversed(prev_messages):
            await sio.emit('receive_message', {
                'nickname': msg.nickname,
                'message': msg.message
            }, to=sid)

        print(f"✅ {temp_nickname} 접속 (SID: {sid})")

    @sio.on('set_nickname')
    async def handle_set_nickname(sid, new_nickname):
        old_name = connected_users.get(sid)
        connected_users[sid] = new_nickname
        print(f"📢 닉네임 변경: {old_name} -> {new_nickname}")

    @sio.on('send_message')
    async def handle_send_message(sid, data):
        nickname = connected_users.get(sid, "Unknown")
        message = data.get('message')

        # 1. DB에 저장
        db = SessionLocal()
        new_log = models.ChatLog(nickname=nickname, message=message)
        db.add(new_log)
        db.commit()
        db.close()

        # 2. 모든 접속자에게 브로드캐스트
        await sio.emit('receive_message', {
            'nickname': nickname,
            'message': message
        })