import json
import time
from datetime import datetime, timedelta
from termcolor import cprint
import random
import os

def clear_screen():
    """Clears the terminal screen."""
    # For Windows
    if os.name == 'nt':
        _ = os.system('cls')
    # For macOS and Linux
    else:
        _ = os.system('clear')

def load_tasks():
    """
    Loads tasks from a JSON file.
    It's good practice to handle potential errors, like the file not existing.
    """
    # NOTE: Make sure this file path is correct for your system!
    file_path = r'C:\Users\ixis1\Desktop\DEV\productivity\MOON DEV projects\task.json'
    try:
        with open(file_path, 'r') as f:
            tasks = json.load(f)
        return tasks
    except FileNotFoundError:
        print(f"Error: The file '{file_path}' was not found.")
        print("Please create the file and add your tasks.")
        return None # Return None to indicate failure
    except json.JSONDecodeError:
        print(f"Error: The file '{file_path}' is not a valid JSON file.")
        return None

def get_task_schedule(tasks):
    """
    Creates a schedule with start and end times for each task.
    """
    task_start_time = datetime.now()
    schedule = []
    for task, minutes in tasks.items():
        end_time = task_start_time + timedelta(minutes=minutes)
        schedule.append((task, task_start_time, end_time))
        task_start_time = end_time
    return schedule

def main():
    """
    Main function to run the task scheduler.
    """
    tasks = load_tasks()
    # If tasks failed to load, exit the program
    if not tasks:
        return

    # This list is now defined only once, outside the main loop for efficiency.
    list_of_reminders = [
        "i have a 1000 percent algo",
        "time is irrelevant, keep swimming",
        "everyday I get better",
        "rest at the end",
        "kpbs not finished",
        "deal was already made",
        "best algo trader in the world",
    ]

    schedule = get_task_schedule(tasks)
    current_index = 0

    while True:
        # Prevents a crash if all tasks are completed
        if current_index >= len(schedule):
            cprint('All tasks completed! Great work.', 'white', 'on_green')
            break

        now = datetime.now()
        clear_screen() # Clears the screen for a cleaner display each update
        print(f"--- RBI Trading Schedule --- {now.strftime('%Y-%m-%d %H:%M:%S')} ---\n")

        # --- MAJOR LOGIC FIX ---
        # This loop correctly displays the status of every task on each update.
        for index, (task, s_time, e_time) in enumerate(schedule):
            if index < current_index:
                # This task is completed
                cprint(f"[DONE] {task} - finished at {e_time.strftime('%H:%M')}", 'green')
            elif index == current_index:
                # This is the current task
                remaining_time = e_time - now
                remaining_minutes = int(remaining_time.total_seconds() // 60)

                if remaining_minutes < 2:
                    cprint(f"-> {task.upper()} <- {remaining_minutes}m left! FINISH STRONG!", 'white', 'on_red', attrs=['blink'])
                elif remaining_minutes < 5:
                    cprint(f"-> {task.upper()} <- {remaining_minutes}m left", 'white', 'on_yellow')
                else:
                    cprint(f"-> {task.upper()} <- {remaining_minutes}m left", 'white', 'on_blue')
            else:
                # This is an upcoming task
                print(f"[NEXT] {task} - starts at {s_time.strftime('%H:%M')}")
        
        # --- End of Logic Fix ---

        # Display a random motivational reminder
        random_reminder = random.choice(list_of_reminders)
        print('\n' + '✨ ' + random_reminder + ' ✨')

        # Check if the current task is finished and move to the next one
        if now >= schedule[current_index][2]: # Index 2 is the end_time
            current_index += 1
            
        time.sleep(15) # Refresh every 15 seconds

# This is the standard and correct way to run a Python script.
if __name__ == "__main__":
    main()