import dspy

# Configure DSPy to talk to your local Ollama instance
dspy.configure(lm=dspy.LM(
    model="ollama_chat/qwen2.5:3b-instruct",
    api_base="http://127.0.0.1:11434",
    temperature=0.2,
    max_tokens=256,
))

class TaskPlanner(dspy.Module):
    def __init__(self):
        super().__init__()
        self.predict = dspy.Predict("prompt:str -> tasks_json:str")

    def forward(self, prompt):
        return self.predict(prompt=prompt).tasks_json


if __name__ == "__main__":
    agent = TaskPlanner()

    prompt = """You are an automation assistant.
Convert this calendar into todos (JSON array of {"title","due","notes","list"}):
10:00-10:30 1:1 with Sam (prep: review Q3 OKRs)
13:00-14:00 Vendor demo (Acme Boards)
16:30-17:00 Team standup
"""

    print(agent(prompt))
