import time

def execute_agent(agent_name):
    print(f"[RUNNING] Agent '{agent_name}' is now executing tasks...")
    time.sleep(2)  # Simulate task execution
    print(f"[COMPLETED] Agent '{agent_name}' has completed its tasks.")

if __name__ == "__main__":
    agents = ["Dashboard Agent", "Testing Agent", "ML Tasks Handler", "Inter-Agent Communicator"]
    for agent in agents:
        execute_agent(agent)