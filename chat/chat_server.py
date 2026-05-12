"""
chat_server.py - Socket.IO 이벤트 핸들러 (1:1 매칭 & DB 분리 완벽 지원)
"""

import socketio
from database import SessionLocal
import models
from sqlalchemy.exc import SQLAlchemyError

def register_socket_events(sio):
    connected_users = {}

    async def broadcast_patient_list():
        """대기 중인 환자 목록 브로드캐스트"""
        waiting_patients = [
            {'sid': sid, 'nickname': info['nickname']}
            for sid, info in connected_users.items()
            if info['role'] == 'patient' and info['room'] is None
        ]
        for sid, info in connected_users.items():
            if info['role'] == 'therapist':
                try:
                    await sio.emit('update_patient_list', waiting_patients, to=sid)
                except:
                    pass

    @sio.event
    async def connect(sid, environ):
        connected_users[sid] = {'nickname': f"User_{sid[:4]}", 'role': None, 'room': None}
        print(f"✅ 사용자 접속 (SID: {sid})")

    @sio.on('identify')
    async def handle_identify(sid, data):
        nickname = data.get('nickname', f"User_{sid[:4]}")
        role = data.get('role', 'patient')
        
        connected_users[sid]['nickname'] = nickname
        connected_users[sid]['role'] = role
        
        await broadcast_patient_list()
        
        # 🔑 전체 채팅(로비) 기록만 불러오기 (room_id == None 인 것만)
        db = SessionLocal()
        try:
            prev_messages = db.query(models.ChatLog)\
                .filter(models.ChatLog.room_id == None)\
                .order_by(models.ChatLog.id.desc())\
                .limit(30)\
                .all()
            
            for msg in reversed(prev_messages):
                await sio.emit('receive_message', {
                    'nickname': msg.nickname,
                    'message': msg.message
                }, to=sid)
        except SQLAlchemyError as e:
            print(f"❌ DB 조회 오류: {e}")
        finally:
            db.close()

    @sio.on('request_match')
    async def handle_request_match(sid, data):
        target_sid = data.get('target_sid')
        if not target_sid or target_sid not in connected_users:
            return

        # 방 번호 생성 및 두 사람 배정
        room_id = f"room_{sid}_{target_sid}"
        connected_users[sid]['room'] = room_id
        connected_users[target_sid]['room'] = room_id

        sio.enter_room(sid, room_id)
        sio.enter_room(target_sid, room_id)

        # 양측에 매칭 알림
        await sio.emit('match_success', {'room_id': room_id, 'target_nickname': connected_users[target_sid]['nickname']}, to=sid)
        await sio.emit('match_success', {'room_id': room_id, 'target_nickname': connected_users[sid]['nickname']}, to=target_sid)
        
        await broadcast_patient_list()

    @sio.on('send_message')
    async def handle_send_message(sid, data):
        user_info = connected_users.get(sid)
        if not user_info: return

        nickname = user_info['nickname']
        room_id = user_info['room']
        message = data.get('message', '').strip()
        if not message: return

        # 🔑 DB 저장 시 room_id를 반드시 함께 저장합니다!
        db = SessionLocal()
        try:
            new_log = models.ChatLog(nickname=nickname, message=message, room_id=room_id)
            db.add(new_log)
            db.commit()
        except SQLAlchemyError as e:
            print(f"❌ DB 저장 오류: {e}")
            db.rollback()
        finally:
            db.close()

        # 메시지 화면에 띄우기 (본인 포함)
        if room_id:
            await sio.emit('receive_message', {'nickname': nickname, 'message': message}, room=room_id)
        else:
            await sio.emit('receive_message', {'nickname': f"[대기실] {nickname}", 'message': message})

    @sio.on('leave_room')
    async def handle_leave_room(sid, data):
        """방 나가기 로직 (대기실로 복귀)"""
        user_info = connected_users.get(sid)
        if not user_info or not user_info['room']: return
        
        old_room = user_info['room']
        
        # 방에 남은 사람에게 알림
        await sio.emit('receive_message', {'nickname': '📡 시스템', 'message': '상담이 종료되었습니다. (대기실로 복귀합니다)'}, room=old_room)
        
        # 방에 있는 두 사람 모두 방에서 해제시키고 로비로 보냄
        for u_sid, u_info in connected_users.items():
            if u_info.get('room') == old_room:
                sio.leave_room(u_sid, old_room)
                u_info['room'] = None
                
        await broadcast_patient_list()

    @sio.on('clear_chat')
    async def handle_clear_chat(sid, data):
        """1:1 방의 채팅 기록 삭제"""
        room_id = connected_users[sid].get('room')
        if not room_id: return
        
        db = SessionLocal()
        try:
            db.query(models.ChatLog).filter(models.ChatLog.room_id == room_id).delete()
            db.commit()
            await sio.emit('receive_message', {'nickname': '📡 시스템', 'message': '이 방의 대화 기록이 삭제되었습니다.'}, room=room_id)
        except SQLAlchemyError as e:
            db.rollback()
        finally:
            db.close()

    @sio.on('set_nickname')
    async def handle_set_nickname(sid, new_nickname):
        if sid in connected_users:
            connected_users[sid]['nickname'] = new_nickname
            if connected_users[sid]['role'] == 'patient':
                await broadcast_patient_list()

    @sio.event
    async def disconnect(sid):
        user_info = connected_users.pop(sid, None)
        if user_info:
            room_id = user_info['room']
            # 채팅 중 나간 경우
            if room_id:
                await sio.emit('receive_message', {'nickname': '📡 시스템', 'message': '상대방의 연결이 끊어졌습니다.'}, room=room_id)
                for u_sid, u_info in list(connected_users.items()):
                    if u_info.get('room') == room_id:
                        u_info['room'] = None
                        sio.leave_room(u_sid, room_id)

            if user_info['role'] == 'patient' and not room_id:
                await broadcast_patient_list()