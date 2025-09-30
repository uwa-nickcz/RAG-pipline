import requests
import json

url = "https://bisheng.dataelem.com/api/v2/assistant/chat/completions"

payload = json.dumps({
   "model": "6dc3ea0233a24748901e2cf15ae38710",
   "messages": [
      {
         "role": "user",
         "content": "今年的缺陷数量是多少"
      }
   ],
   "temperature": 0,
   "stream": True
})
headers = {
   'User-Agent': 'Apifox/1.0.0 (https://apifox.com)',
   'Content-Type': 'application/json'
}

response = requests.request("POST", url, headers=headers, data=payload)

print(response.text)