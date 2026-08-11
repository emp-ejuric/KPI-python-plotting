import tkinter as tk
from tkinter import ttk
from kpi_plotter import generate_report
import threading



#================================
# GENERATE TKINTER WINDOW
#================================
root = tk.Tk()
root.title("Jira KPI Report Generator")
root.geometry("600x500")


status_label = tk.Label(root, text="Ready")
status_label.grid(row=99, column=0, columnspan=2, pady=5)


#================================
# INPUT FIELDS
#================================

#JQL Text box
tk.Label(
    root,
    text="JQL"
).grid(row=1, column=0)

jql_text = tk.Text(
    root,
    height=8,
    width=60
)

jql_text.grid(
    row=7,
    column=0,
    columnspan=3,
    padx=8,
    pady=4
)

#Date Created
tk.Label(root, text="Days since created").grid(row=0, column=0, padx=8, pady=4)
date_entry = tk.Entry(root)
date_entry.insert(0, "365")
date_entry.grid(row=0, column=1, padx=8, pady=4)

# Project
tk.Label(root, text="Project").grid(row=1, column=0, padx=8, pady=4)
project_entry = tk.Entry(root)
project_entry.insert(0, "ECCO")
project_entry.grid(row=1, column=1, padx=8, pady=4)

# Issue Type
tk.Label(root, text="Issue Type").grid(row=2, column=0, padx=8, pady=4)

issue_type = ttk.Combobox(
    root,
    values=["All","Story", "Epic"]
)
issue_type.current(0)
issue_type.grid(row=2, column=1)

#Assignee selection
tk.Label(root, text="Assignees").grid(
    row=3,
    column=0,
    padx=8,
    pady=4
)

assignee_entry = tk.Entry(root, width=40)

assignee_entry.grid(
    row=3,
    column=1,
    padx=8,
    pady=4
)

#Graph selection
graph_frame = ttk.LabelFrame(root, text="Graph Selection")
graph_canvas = tk.Canvas(graph_frame, height=150)
scrollbar = ttk.Scrollbar(graph_frame, orient="vertical")

story_throughput_var = tk.BooleanVar(value=False)
closure_age_var = tk.BooleanVar(value=False)
bug_story_var = tk.BooleanVar(value=False)
story_points_weekly_var = tk.BooleanVar(value=False)


ttk.Checkbutton(
    graph_frame,
    text="Story Throughput and Aging",
    variable=story_throughput_var
).pack(anchor="w", padx=5, pady=2)

ttk.Checkbutton(
    graph_frame,
    text="Average Age at Closure",
    variable=closure_age_var
).pack(anchor="w", padx=5, pady=2)

ttk.Checkbutton(
    graph_frame,
    text="Bug Stories Created vs Open",
    variable=bug_story_var
).pack(anchor="w", padx=5, pady=2)


ttk.Checkbutton(
    graph_frame,
    text="Story Points Completed Per Sprint",
    variable=story_points_weekly_var
).pack(anchor="w", padx=5, pady=2)

graphs_visible = False

def toggle_graphs():
    global graphs_visible

    if graphs_visible:
        graph_frame.grid_remove()
        graph_button.config(text="▶ Graph Options")
        graphs_visible = False
    else:
        graph_frame.grid(row=5, column=0, columnspan=2, sticky="ew", padx=8)
        graph_button.config(text="▼ Graph Options")
        graphs_visible = True

graph_button = ttk.Button(
    root,
    text="▶ Graph Options",
    command=toggle_graphs
)

graph_button.grid(row=4, column=0, padx=8, pady=4)

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

    if issue != "All":
        conditions.append(f"issuetype = {issue}")

    assignees = assignee_entry.get().strip()
    if assignees:
        assignee_list = [
            user.strip()
            for user in assignees.split(",")
            if user.strip()
        ]
        quoted_assignees = [
            f'"{user}"' if " " in user or "," in user else user
            for user in assignee_list
        ]
        conditions.append(
            f"assignee in ({', '.join(quoted_assignees)})"
        )

    for condition in conditions:
        jql += "\nAND " + condition

    jql_text.delete("1.0", tk.END)
    jql_text.insert("1.0", jql)
    print(jql + "\n")
    return jql

#Generate JQL button
build_jql_button = tk.Button(
    root,
    text="Build JQL",
    command=generate_jql
)

build_jql_button.grid(
    row=6,
    column=0,
    pady=4
)
generate_jql()
    
def run_report():
    #jql = generate_jql()
    status_label.config(text="Loading...")
    progress.start(10)
    generate_button.config(state="disabled")
    selected_graphs = []

    if story_throughput_var.get():
        selected_graphs.append("throughput")

    if closure_age_var.get():
        selected_graphs.append("closure_age")

    if bug_story_var.get():
        selected_graphs.append("bugs")

    if story_points_weekly_var.get():
        selected_graphs.append("story_points_weekly")

    

    threading.Thread(
        target=generate_report_thread,
        daemon=True
    ).start()

    #generate_report(jql, selected_graphs)

#Generate Report Button
generate_button = tk.Button(
    root,
    text="Generate Report",
    command=run_report
)

generate_button.grid(
    row=0,
    column=2,
    columnspan=2,
    pady=20
)

def generate_report_thread():

    try:
        jql = jql_text.get(
            "1.0",
            tk.END
        ).strip()

        selected_graphs = []

        if story_throughput_var.get():
            selected_graphs.append("throughput")

        if closure_age_var.get():
            selected_graphs.append("closure_age")

        if bug_story_var.get():
            selected_graphs.append("bugs")

        if story_points_weekly_var.get():
                selected_graphs.append("story_points_biweekly")

        generate_report(jql, selected_graphs)

        root.after(
            0,
            lambda: status_label.config(text="Report completed")
        )

    except Exception as e:
        root.after(
            0,
            lambda: status_label.config(text=f"Error: {e}")
        )

    finally:
        root.after(
            0,
            lambda: generate_button.config(state="normal")
        )
        root.after(
            0,
            progress.stop
        )

progress = ttk.Progressbar(
    root,
    mode="indeterminate"
)

progress.grid(row=100, column=0, columnspan=2, sticky="ew")

root.mainloop()