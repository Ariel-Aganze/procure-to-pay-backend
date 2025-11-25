import ollama

res = ollama.chat(model='llama3.1', messages=[
    {"role": "user", "content": "Hello!"}
])

print(res['message']['content'])
