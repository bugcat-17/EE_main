import socketio
from database import SessionLocal
import models

def register_socket_events(sio):
    # 접속 중인 사용자 관리 (sid -> nickname)
    connected_users = {}

    @sio.event
    async def connect(sid, environ):
        # 초기 접속 시 임시 이름 부여
        connected_users[sid] = f"User_{sid[:4]}"
        print(f"✅ 새 접속 (SID: {sid})")

    @sio.on('identify')
    async def handle_identify(sid, data):
        # 클라이언트 기기에 저장된 닉네임으로 서버 정보 업데이트
        nickname = data.get('nickname')
        if nickname:
            connected_users[sid] = nickname
            print(f"📢 사용자 식별 완료: {nickname} (SID: {sid})")

    @sio.on('set_nickname')
    async def handle_set_nickname(sid, new_nickname):
        # 닉네임 변경 요청 처리
        old_name = connected_users.get(sid)
        connected_users[sid] = new_nickname
        print(f"📢 닉네임 변경: {old_name} -> {new_nickname}")

    @sio.on('send_message')
    async def handle_send_message(sid, data):
        # 메시지 전송 시 현재 등록된 닉네임 사용 [cite: 4]
        nickname = connected_users.get(sid, "Unknown")
        message = data.get('message')

        if not message:
            return

        # 1. DB에 저장 [cite: 4]
        db = SessionLocal()
        new_log = models.ChatLog(nickname=nickname, message=message)
        db.add(new_log)
        db.commit()
        db.close()

        # 2. 모든 접속자에게 브로드캐스트 [cite: 5]
        await sio.emit('receive_message', {
            'nickname': nickname,
            'message': message
        })