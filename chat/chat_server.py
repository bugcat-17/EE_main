# chat_server.py 수정
@sio.on('identify')
async def handle_identify(sid, data):
    nickname = data.get('nickname', f"User_{sid[:4]}")
    connected_users[sid] = nickname
    print(f"📢 사용자 확인: {nickname}")

    # 닉네임이 확인된 이 시점에 과거 메시지 30개를 불러와서 해당 유저에게만 전송 
    db = SessionLocal()
    prev_messages = db.query(models.ChatLog).order_by(models.ChatLog.id.desc()).limit(30).all()
    db.close()

    # 과거 메시지 전송 (이벤트명을 receive_message로 통일) [cite: 3]
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

    # DB 저장 [cite: 4]
    db = SessionLocal()
    new_log = models.ChatLog(nickname=nickname, message=message)
    db.add(new_log)
    db.commit()
    db.close()

    # 모두에게 브로드캐스트 [cite: 5]
    await sio.emit('receive_message', {'nickname': nickname, 'message': message})