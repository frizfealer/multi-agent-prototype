import requests


def main():
    conversation_id = None
    while True:
        message = input("You: ")
        if message.lower() == "exit":
            break

        response = requests.post(
            "http://127.0.0.1:8000/chat", json={"message": message, "conversation_id": conversation_id}
        )

        if response.status_code == 200:
            print(f"Agent: {response.json()['response']}")
            conversation_id = response.json()["conversation_id"]
        else:
            print(f"Error: {response.text}")


if __name__ == "__main__":
    main()
