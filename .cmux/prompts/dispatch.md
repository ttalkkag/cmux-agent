[cmux-agent] ${sender}로부터 작업이 도착했습니다.

작업: $message

위 작업을 수행하세요.
완료 후 $outbox 에 아래 형식의 JSON 파일을 생성하세요.
{"type": "result", "sender": "$recipient", "recipient": "$sender", "message": "<작업 결과 요약>"}