from ollama import chat

response = chat(
    model = "gemma4", 
    messages= [
        {
            "role": "user", 
            "content": "Exaplain what an IT ticket is in one sentence."}
    ]
)
print(response["message"]["content"])
