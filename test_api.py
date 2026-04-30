import os
import google.generativeai as genai
from dotenv import load_dotenv

# 1. .env 파일 안에 있는 변수들을 파이썬으로 불러옵니다.
load_dotenv()

# 2. 환경 변수에서 GEMINI_API_KEY 값을 가져옵니다.
API_KEY = os.environ.get("GEMINI_API_KEY")

if not API_KEY:
    print("경고: .env 파일에서 GEMINI_API_KEY를 찾을 수 없습니다!")
    exit()

# 3. 가져온 키로 AI 설정
genai.configure(api_key=API_KEY)

print("AI와 연결 중...")

try:
    # 모델 지정 (최신 1.5 플래시 모델)
    model = genai.GenerativeModel('gemini-2.5-flash')
    
    # 테스트 질문
    response = model.generate_content("안녕? 넌 어떤 모델이니? 1문장으로 짧게 대답해줘.")
    
    print("=========================")
    print("연결 성공! AI의 답변:")
    print(response.text)
    print("=========================")

except Exception as e:
    print("에러 발생:", e)