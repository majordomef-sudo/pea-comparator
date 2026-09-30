import os, json, requests

# Read the prompt
with open('/home/ubuntu/.openclaw/workspace/web/kakeibo_prompt.txt', 'r') as f:
    prompt = f.read()

# Get API key from env
api_key = os.environ.get('OPENROUTER_API_KEY', '')

print(f'Prompt length: {len(prompt)} chars')
print(f'API key found: {bool(api_key)}')

if not api_key:
    print('ERROR: No API key found')
    exit(1)

# Call deepseek v4 pro
headers = {
    'Authorization': f'Bearer {api_key}',
    'Content-Type': 'application/json'
}

payload = {
    'model': 'deepseek/deepseek-v4-pro',
    'messages': [
        {'role': 'user', 'content': prompt}
    ],
    'max_tokens': 16000,
    'temperature': 0.3
}

print('Calling deepseek v4 pro API...')

try:
    response = requests.post(
        'https://openrouter.ai/api/v1/chat/completions',
        headers=headers,
        json=payload,
        timeout=120
    )
    
    print(f'Status: {response.status_code}')
    
    if response.status_code == 200:
        result = response.json()
        content = result['choices'][0]['message']['content']
        
        with open('/home/ubuntu/.openclaw/workspace/web/kakeibo_analysis.json', 'w') as f:
            json.dump(result, f, indent=2)
        
        with open('/home/ubuntu/.openclaw/workspace/web/kakeibo_analysis.txt', 'w') as f:
            f.write(content)
        
        print(f'Result saved ({len(content)} chars)')
        print(content[:2000])
    else:
        print(f'API Error: {response.text[:1000]}')
except Exception as e:
    print(f'Exception: {e}')
