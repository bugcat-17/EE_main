"""
chat_server.py - Socket.IO 이벤트 핸들러 (1:1 매칭 지원 버전)

주요 수정 사항:
1. ✅ 유저별 상태 관리 (역할, 접속 방 번호 추가)
2. ✅ 대기 중인 환자 목록을 상담사에게 실시간 브로드캐스트
3. ✅ 1:1 매칭(Room) 생성 및 방 내부 메시지 전송 로직 추가
"""

import socketio
from database import SessionLocal
import models
from sqlalchemy.exc import SQLAlchemyError

def register_socket_events(sio):
    """Socket.IO 이벤트 핸들러 등록"""
    
    # 딕셔너리 구조 변경: sid: {'nickname': '..', 'role': '..', 'room': '..'}
    connected_users = {}

    async def broadcast_patient_list():
        """대기 중인(방이 없는) 환자 목록을 모든 상담사에게 전송하는 헬퍼 함수"""
        # 1. 대기 중인 환자 목록 추출
        waiting_patients = [
            {'sid': sid, 'nickname': info['nickname']}
            for sid, info in connected_users.items()
            if info['role'] == 'patient' and info['room'] is None
        ]
        
        # 2. 접속 중인 모든 상담사에게 목록 전송
        for sid, info in connected_users.items():
            if info['role'] == 'therapist':
                try:
                    await sio.emit('update_patient_list', waiting_patients, to=sid)
                except Exception as e:
                    print(f"⚠️ 환자 목록 전송 실패 (SID: {sid}): {e}")

    @sio.event
    async def connect(sid, environ):
        # 초기 접속 시에는 역할과 방이 없는 상태로 등록
        connected_users[sid] = {'nickname': f"User_{sid[:4]}", 'role': None, 'room': None}
        print(f"✅ 사용자 접속 (SID: {sid})")

    @sio.on('identify')
    async def handle_identify(sid, data):
        """클라이언트 역할 및 닉네임 식별"""
        nickname = data.get('nickname', f"User_{sid[:4]}")
        role = data.get('role', 'patient') # 기본값 환자
        
        connected_users[sid]['nickname'] = nickname
        connected_users[sid]['role'] = role
        
        print(f"👤 사용자 식별됨 - {nickname} (Role: {role}, SID: {sid})")
        
        # 식별 완료 후 환자 목록 갱신 (누군가 새로 들어왔으므로)
        await broadcast_patient_list()
        
        # ⚠️ 참고: 1:1 채팅이므로 글로벌 과거 메시지를 불러오는 로직은 
        # 나중에 DB에 'room_id' 컬럼을 추가한 뒤 해당 방의 메시지만 불러오도록 수정해야 합니다.
        # 일단 기존 DB 로직은 유지합니다.
        db = SessionLocal()
        try:
            prev_messages = db.query(models.ChatLog)\
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
        """상담사가 특정 환자와의 1:1 매칭을 요청"""
        target_patient_sid = data.get('target_sid')
        therapist_info = connected_users.get(sid)
        patient_info = connected_users.get(target_patient_sid)

        # 유효성 검사
        if not therapist_info or not patient_info:
            await sio.emit('error', {'message': '유효하지 않은 대상입니다.'}, to=sid)
            return

        if therapist_info['role'] != 'therapist':
            await sio.emit('error', {'message': '상담사만 매칭을 요청할 수 있습니다.'}, to=sid)
            return

        # 고유 방 번호 생성 (상담사SID_환자SID)
        room_id = f"room_{sid}_{target_patient_sid}"
        
        # 1. 두 사람을 상태 테이블에서 방에 할당
        therapist_info['room'] = room_id
        patient_info['room'] = room_id

        # 2. Socket.io 가상 Room에 조인
        sio.enter_room(sid, room_id)
        sio.enter_room(target_patient_sid, room_id)

        print(f"🤝 1:1 매칭 성사 - 방: {room_id} (상담사: {therapist_info['nickname']}, 환자: {patient_info['nickname']})")

        # 3. 양측에 매칭 성공 알림
        await sio.emit('match_success', {
            'room_id': room_id,
            'partner_nickname': patient_info['nickname'],
            'message': f"{patient_info['nickname']} 환자님과 연결되었습니다."
        }, to=sid)
        
        await sio.emit('match_success', {
            'room_id': room_id,
            'partner_nickname': therapist_info['nickname'],
            'message': f"{therapist_info['nickname']} 상담사님과 연결되었습니다."
        }, to=target_patient_sid)

        # 4. 환자가 매칭되었으므로 남은 대기 목록을 다시 뿌림
        await broadcast_patient_list()

    @sio.on('send_message')
    async def handle_send_message(sid, data):
        """특정 방(Room)으로 메시지 전송"""
        user_info = connected_users.get(sid)
        if not user_info:
            return

        nickname = user_info['nickname']
        room_id = user_info['room']
        message = data.get('message', '').strip()
        
        if not message:
            return

        # (기존 DB 저장 로직 - 향후 모델에 room_id 컬럼 추가 권장)
        db = SessionLocal()
        try:
            new_log = models.ChatLog(nickname=nickname, message=message)
            db.add(new_log)
            db.commit()
        except SQLAlchemyError as e:
            print(f"❌ DB 저장 오류: {e}")
            db.rollback()
        finally:
            db.close()

        # 🔑 핵심 수정: 전체 브로드캐스트가 아닌, 해당 '방(Room)'에만 전송
        if room_id:
            try:
                await sio.emit('receive_message', {
                    'nickname': nickname,
                    'message': message
                }, room=room_id)  # <-- to= 대신 room= 사용
                print(f"📤 [방: {room_id}] 메시지 전송 - {nickname}: {message}")
            except Exception as e:
                print(f"❌ 메시지 전송 오류: {e}")
        else:
            # 방에 입장하지 않은 상태에서 보낸 메시지 (대기실 전체 채팅 - 원치 않으면 삭제 가능)
            await sio.emit('receive_message', {
                'nickname': nickname,
                'message': f"[대기실] {message}"
            })

    @sio.on('set_nickname')
    async def handle_set_nickname(sid, new_nickname):
        if sid in connected_users:
            old_nickname = connected_users[sid]['nickname']
            connected_users[sid]['nickname'] = new_nickname
            print(f"📝 닉네임 변경 - {old_nickname} → {new_nickname}")
            # 닉네임이 바뀌었으니 상담사 화면의 환자 목록도 갱신
            if connected_users[sid]['role'] == 'patient':
                await broadcast_patient_list()

    @sio.event
    async def disconnect(sid):
        user_info = connected_users.pop(sid, None)
        if user_info:
            nickname = user_info['nickname']
            room_id = user_info['room']
            role = user_info['role']
            
            print(f"❌ 사용자 퇴장 - {nickname} (SID: {sid})")
            
            # 채팅 중이었다면 상대방에게 알림
            if room_id:
                await sio.emit('receive_message', {
                    'nickname': '📡 시스템',
                    'message': f'{nickname}님이 대화방을 나갔습니다.'
                }, room=room_id)
                sio.leave_room(sid, room_id)
            
            # 대기 중이던 환자가 나갔다면 목록 갱신
            if role == 'patient' and not room_id:
                await broadcast_patient_list()