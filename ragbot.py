import sys

import chromadb
from ollama import chat, embeddings

from tickets import tickets

EMBEDDING_MODEL = "nomic-embed-text"
CHAT_MODEL = "gemma4"

RELEVANCE_THRESHOLD = 1.0  # 350.0

sys_prompt = """"You are WHT_RBT, the White Rabbit - the IT helpdesk assistant
for this ticketing system. You are efficient and a little frantic, but you always get people the
right answer. Keep responses brief and professional, but never let the
personality get in the way of the actual fix - the IT answer always comes
first.
 
Answer using ONLY the resolved tickets provided as context below. Never use
outside knowledge. If the tickets don't contain the answer, say so plainly -
don't guess, and don't let personality dress up a wrong answer as a
confident one.
 
Resolved tickets:
{context}"""

def get_collection():
    client = chromadb.PersistentClient(path="./chroma_db")
    return client.get_or_create_collection(name="resolved_tickets",
                                           metadata= {"hnsw:space": "cosine"})

def embedding_text(text: str) -> list[float]:
    response = embeddings(
        model=EMBEDDING_MODEL,
        prompt = text
    )
    return response["embedding"]

def ticket_to_text(ticket: dict) -> str:
    return (
        f"Title: {ticket['title']}\n"
        f"Description: {ticket['description']}\n"
        f"Category: {ticket['category']}\n"
        f"Resolution: {ticket['resolution']}\n"
        f"Tags: {ticket['tags']}"   
    )

def load_tickets():
    collection = get_collection()
    documents, ids, metadatas, vectors = [], [], [], []

    for ticket in tickets:
        text = ticket_to_text(ticket)
        documents.append(text)
        ids.append(ticket["id"])
        metadatas.append({
            "title": ticket["title"],
            "category": ticket["category"]
        })
        vectors.append(embedding_text(text))

    collection.upsert(
        documents=documents,
        ids=ids,
        metadatas=metadatas,
        embeddings=vectors
    )
    print(f"{len(documents)} tickets loaded.")

def ask(question: str, collection) -> str:
    results = collection.query(
        query_embeddings=[embedding_text(question)], 
        n_results=3
        )
    # print("DEBUG distances:", results["distances"][0])
    documents = results["documents"][0]
    distances = results["distances"][0]

    if not documents or min(distances) > RELEVANCE_THRESHOLD:
        return "I could not find enough information in the resolved tickets to answer that."    
    context = "\n".join(documents)
    response = chat(
        model=CHAT_MODEL,
        messages=[
            {
                "role": "system",
                "content": sys_prompt.format(context=context)
            },
            {
                "role": "user",
                "content": question
            },
        ],
        options = {"temperature": 0.8},
    )
    return response["message"]["content"]

def ask_loop():
    collection = get_collection()
    if collection.count() == 0:
        print("there is no tickets loaded.")
        return
    print("WHT_RBT is ready. type your question below. Type 'end' to stop.")
    running = True
    while running:
        question = input("\nYour question: ").strip()
        if question.lower() in ("end"):
            running = False
        elif question: 
            print(f"\nWHTRBT: \n{ask(question, collection)}\n")

if __name__ == "__main__":
    if "--load" in sys.argv:
        load_tickets()
    else:
        ask_loop()
