from itertools import chain
from todoist_api_python.api import TodoistAPI
import os


api_key = os.getenv("TODOIST_API_KEY")

todoist_client = TodoistAPI(api_key)

if __name__ == "__main__":

    all_tasks = list(chain.from_iterable(todoist_client.get_tasks()))

    for task in all_tasks:
        print(task)