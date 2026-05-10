"""
chat_server.py - Socket.IO 이벤트 핸들러 (수정된 버전)

주요 수정 사항:
1. ✅ send_message에서 broadcast 추가 (모든 클라이언트에게 전송)
2. ✅ set_nickname에서 async/await 처리 개선
3. ✅ 에러 처리 추가
4. ✅ DB 연결 안정성 개선
"""

import socketio
from database import SessionLocal
import models
from sqlalchemy.exc import SQLAlchemyError

def register_socket_events(sio):
    """Socket.IO 이벤트 핸들러 등록"""
    
    # 접속 중인 사용자 관리 (sid: nickname)
    connected_users = {}

    @sio.event
    async def connect(sid, environ):
        """
        클라이언트 접속 시 호출
        
        Args:
            sid: Socket ID (고유 식별자)
            environ: 연결 환경 정보
        """
        connected_users[sid] = f"User_{sid[:4]}"
        print(f"✅ 사용자 접속 (SID: {sid})")

    @sio.on('identify')
    async def handle_identify(sid, data):
        """
        클라이언트가 자신의 닉네임을 서버에 알림
        서버는 이 닉네임을 기반으로 과거 메시지 30개를 전송
        
        Args:
            sid: Socket ID
            data: {'nickname': '사용자_닉네임'} 형식
        """
        nickname = data.get('nickname', f"User_{sid[:4]}")
        connected_users[sid] = nickname
        print(f"👤 사용자 식별됨 - {nickname} (SID: {sid})")
        
        db = SessionLocal()
        try:
            # DB에서 최근 30개 메시지 조회 (역순)
            prev_messages = db.query(models.ChatLog)\
                .order_by(models.ChatLog.id.desc())\
                .limit(30)\
                .all()
            
            # 과거 메시지를 오래된 것부터 전송
            for msg in reversed(prev_messages):
                await sio.emit('receive_message', {
                    'nickname': msg.nickname,
                    'message': msg.message
                }, to=sid)
                
        except SQLAlchemyError as e:
            print(f"❌ DB 조회 오류 (identify): {e}")
        finally:
            db.close()

    @sio.on('send_message')
    async def handle_send_message(sid, data):
        """
        클라이언트가 메시지 전송
        
        1. 메시지를 DB에 저장
        2. 모든 클라이언트에게 broadcast
        
        Args:
            sid: Socket ID
            data: {'message': '메시지 내용'} 형식
        """
        # 현재 사용자 닉네임 조회
        nickname = connected_users.get(sid, "Unknown")
        message = data.get('message', '').strip()
        
        # 빈 메시지 필터링
        if not message:
            print(f"⚠️ {nickname}에서 빈 메시지 수신")
            return

        db = SessionLocal()
        try:
            # 📝 DB에 메시지 저장
            new_log = models.ChatLog(nickname=nickname, message=message)
            db.add(new_log)
            db.commit()
            print(f"💾 메시지 저장 완료 - {nickname}: {message}")
            
        except SQLAlchemyError as e:
            print(f"❌ DB 저장 오류 (send_message): {e}")
            db.rollback()
            return
            
        finally:
            db.close()

        # 🔑 핵심 수정: await 추가하고 broadcast (모든 클라이언트에게 전송)
        try:
            await sio.emit('receive_message', {
                'nickname': nickname,
                'message': message
            })
            print(f"📤 메시지 broadcast 완료 - {nickname}")
            
        except Exception as e:
            print(f"❌ 메시지 전송 오류: {e}")

    @sio.on('set_nickname')
    async def handle_set_nickname(sid, new_nickname):
        """
        클라이언트가 닉네임을 변경
        
        Args:
            sid: Socket ID
            new_nickname: 새로운 닉네임 (문자열)
        """
        old_nickname = connected_users.get(sid, "Unknown")
        new_nickname = new_nickname.strip() if isinstance(new_nickname, str) else str(new_nickname)
        
        # 빈 닉네임 필터링
        if not new_nickname:
            print(f"⚠️ {old_nickname}에서 빈 닉네임 수신")
            return
        
        # 닉네임 변경
        connected_users[sid] = new_nickname
        print(f"📝 닉네임 변경 - {old_nickname} → {new_nickname} (SID: {sid})")
        
        # (선택사항) 다른 사용자들에게 닉네임 변경 알림
        try:
            await sio.emit('user_renamed', {
                'old_nickname': old_nickname,
                'new_nickname': new_nickname,
                'sid': sid
            })
        except Exception as e:
            print(f"⚠️ user_renamed 이벤트 전송 실패: {e}")

    @sio.event
    async def disconnect(sid):
        """
        클라이언트 연결 해제
        
        Args:
            sid: Socket ID
        """
        nickname = connected_users.pop(sid, "Unknown")
        print(f"❌ 사용자 퇴장 - {nickname} (SID: {sid})")


# ============================================================================
# 사용 방법 (main.py에서)
# ============================================================================
#
# from flask import Flask
# from flask_socketio import SocketIO
# from chat_server import register_socket_events
#
# app = Flask(__name__)
# sio = SocketIO(app, cors_allowed_origins="*")
#
# # 소켓 이벤트 등록
# register_socket_events(sio)
#
# if __name__ == "__main__":
#     sio.run(app, host="0.0.0.0", port=5000, debug=True)
#
# ============================================================================
