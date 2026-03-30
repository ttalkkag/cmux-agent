[cmux-agent] {sender}로부터 작업이 도착했습니다.

당신의 이름: {recipient}

작업: {message}

작업 완료 후 .cmux/outbox 에 반드시 result JSON을 생성하세요.
{{"type": "result", "sender": "{recipient}", "recipient": "{sender}", "message": "<작업 결과 요약>"}}
