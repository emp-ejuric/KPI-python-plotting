import tkinter as tk
from tkinter import ttk
from kpi_plotter import generate_report



#================================
# GENERATE TKINTER WINDOW
#================================
root = tk.Tk()
root.title("Jira KPI Report Generator")
root.geometry("500x250")

#================================
# INPUT FIELDS
#================================

#Date Created
tk.Label(root, text="Days since created").grid(row=0, column=0, padx=10, pady=10)
date_entry = tk.Entry(root)
date_entry.insert(0, "365")
date_entry.grid(row=0, column=1)

# Project
tk.Label(root, text="Project").grid(row=1, column=0, padx=10, pady=10)
project_entry = tk.Entry(root)
project_entry.insert(0, "ECCO")
project_entry.grid(row=1, column=1)

# Issue Type
tk.Label(root, text="Issue Type").grid(row=2, column=0, padx=10, pady=10)

issue_type = ttk.Combobox(
    root,
    values=["All","Story", "Epic"]
)
issue_type.current(0)
issue_type.grid(row=2, column=1)


#================================
# GENERATE JQL
#================================
def generate_jql():
    jql = ""
    conditions = []

    days_since_created = date_entry.get()
    project = project_entry.get()
    issue = issue_type.get()

    if days_since_created:
        jql = "created >= -" + days_since_created + "d"
    else:        
        jql = "created >= -7300d"

    if project:
        conditions.append(f"project = {project}")

    if issue_type.get() != "All":
        conditions.append(f"issuetype = {issue}")

    
    for condition in conditions:
        jql += "\nAND " + condition
    
    

    print(jql + "\n")
    return(jql)
    conditions.clear()
    jql = ""
    

def run_report():
    jql = generate_jql()
    generate_report(jql)

generate_button = tk.Button(
    root,
    text="Generate Report",
    command=run_report
)

generate_button.grid(
    row=3,
    column=0,
    columnspan=2,
    pady=20
)

root.mainloop()