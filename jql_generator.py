import tkinter as tk
from tkinter import ttk
from kpi_plotter import generate_report
import threading
import json
import os
import requests

JIRA_API_URL = "https://jira.tandemdiabetes.com:8443/rest/api/2"


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

#Date Created
tk.Label(root, text="Days since created").grid(row=0, column=0, padx=8, pady=4)
date_entry = tk.Entry(root)
date_entry.insert(0, "365")
date_entry.grid(row=0, column=1, padx=8, pady=4)

# Project
tk.Label(root, text="Project").grid(row=1, column=0, padx=8, pady=4)
project_entry = ttk.Combobox(root, width=37)
project_entry.insert(0, "ECCO")
project_entry.grid(row=1, column=1, padx=8, pady=4)
project_options = []
component_options = []
assignee_options = []
default_issue_options = ["All", "Story", "Epic"]
issue_options = default_issue_options.copy()
all_issue_options = default_issue_options.copy()


def jira_headers():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    pat_file = os.path.join(script_dir, "JIRA_PAT.json")

    with open(pat_file, "r") as file:
        pat = json.load(file).get("pat")

    if not pat:
        raise ValueError("No 'pat' field found in JIRA_PAT.json")

    return {
        "Authorization": f"Bearer {pat}",
        "Accept": "application/json"
    }


def load_projects():
    status_label.config(text="Loading Jira projects...")
    threading.Thread(target=load_projects_thread, daemon=True).start()


def load_projects_thread():
    try:
        response = requests.get(
            f"{JIRA_API_URL}/project",
            headers=jira_headers(),
            timeout=30
        )
        response.raise_for_status()

        projects = sorted(
            (
                project["key"],
                project.get("name", "")
            )
            for project in response.json()
            if project.get("key")
        )

        root.after(0, lambda: set_project_values(projects))
    except Exception as error:
        root.after(0, lambda: status_label.config(text=f"Project load error"))


def set_project_values(projects):
    global project_options

    project_options = [
        f"{key} - {name}" if name else key
        for key, name in projects
    ]
    project_entry["values"] = project_options
    status_label.config(text=f"Loaded {len(projects)} Jira projects")
    load_components()
    load_assignees()


def filter_projects(_event):
    search_text = project_entry.get().strip().lower()

    if not search_text:
        matching_projects = project_options
    else:
        matching_projects = [
            project
            for project in project_options
            if search_text in project.lower()
        ]

    project_entry["values"] = matching_projects


def select_project(_event):
    selected_project = project_entry.get().split(" - ", 1)[0]
    project_entry.set(selected_project)
    load_components()
    load_assignees()


project_entry.bind("<KeyRelease>", filter_projects)
project_entry.bind("<<ComboboxSelected>>", select_project)

# Team
tk.Label(root, text="Team (Component)").grid(row=2, column=0, padx=8, pady=4)
team_entry = ttk.Combobox(root, width=37)
team_entry.grid(row=2, column=1, padx=8, pady=4)

# Issue Type
tk.Label(root, text="Issue Type").grid(row=3, column=0, padx=8, pady=4)
issue_type = ttk.Combobox(
    root,
    values=issue_options
)
issue_type.current(0)
issue_type.grid(row=3, column=1, padx=8, pady=4)
show_all_issue_types_var = tk.BooleanVar(value=False)

#Assignee selection
tk.Label(root, text="Assignees").grid(row=4, column=0, padx=8, pady=4)
assignee_entry = ttk.Combobox(root, width=37)
assignee_entry.grid(row=4, column=1, padx=8, pady=4)


def selected_project_keys():
    return [
        project.strip().split(" - ", 1)[0]
        for project in project_entry.get().split(",")
        if project.strip()
    ]


def filter_options(entry, options):
    search_text = entry.get().strip().lower()
    entry["values"] = [
        option
        for option in options
        if not search_text or search_text in option.lower()
    ]


def load_components():
    status_label.config(text="Loading Jira components...")
    threading.Thread(
        target=load_components_thread,
        args=(selected_project_keys(),),
        daemon=True
    ).start()


def load_components_thread(project_keys):
    try:
        if not project_keys:
            raise ValueError("Enter a project before loading components")

        components = set()
        for project_key in project_keys:
            response = requests.get(
                f"{JIRA_API_URL}/project/{project_key}/components",
                headers=jira_headers(),
                timeout=30
            )
            response.raise_for_status()
            components.update(
                component["name"]
                for component in response.json()
                if component.get("name")
            )

        root.after(0, lambda: set_component_values(sorted(components)))
    except Exception as error:
        root.after(0, lambda: status_label.config(text=f"Component load error"))


def set_component_values(components):
    component_options[:] = components
    team_entry["values"] = component_options
    status_label.config(text=f"Loaded {len(components)} Jira components")


def load_assignees():
    status_label.config(text="Loading Jira assignees...")
    threading.Thread(
        target=load_assignees_thread,
        args=(selected_project_keys(),),
        daemon=True
    ).start()


def load_assignees_thread(project_keys):
    try:
        if not project_keys:
            raise ValueError("Enter a project before loading assignees")

        assignees = {}
        for project_key in project_keys:
            response = requests.get(
                f"{JIRA_API_URL}/user/assignable/search",
                headers=jira_headers(),
                params={"project": project_key, "maxResults": 1000},
                timeout=30
            )
            response.raise_for_status()

            for user in response.json():
                username = user.get("name") or user.get("key")
                if username:
                    display_name = user.get("displayName", username)
                    assignees[username] = f"{username} - {display_name}"

        root.after(0, lambda: set_assignee_values(sorted(assignees.values())))
    except Exception as error:
        root.after(0, lambda: status_label.config(text=f"Assignee load error"))


def set_assignee_values(assignees):
    assignee_options[:] = assignees
    assignee_entry["values"] = assignee_options
    status_label.config(text=f"Loaded {len(assignees)} Jira assignees")


def load_issue_types():
    status_label.config(text="Loading Jira issue types...")
    threading.Thread(target=load_issue_types_thread, daemon=True).start()


def load_issue_types_thread():
    try:
        response = requests.get(
            f"{JIRA_API_URL}/issuetype",
            headers=jira_headers(),
            timeout=30
        )
        response.raise_for_status()

        issue_types = sorted(
            issue["name"]
            for issue in response.json()
            if issue.get("name")
        )
        root.after(0, lambda: set_issue_type_values(issue_types))
    except Exception as error:
        root.after(0, lambda: status_label.config(text=f"Issue type load error"))


def set_issue_type_values(issue_types):
    all_issue_options[:] = ["All", *sorted(set(issue_types))]
    update_issue_type_options()
    status_label.config(text=f"Loaded {len(issue_types)} Jira issue types")


def update_issue_type_options():
    visible_options = (
        all_issue_options
        if show_all_issue_types_var.get()
        else default_issue_options
    )
    issue_options[:] = visible_options
    issue_type["values"] = issue_options

    if issue_type.get() not in visible_options:
        issue_type.set("All")


ttk.Checkbutton(
    root,
    text="Show all issue types",
    variable=show_all_issue_types_var,
    command=update_issue_type_options
).grid(row=3, column=2, padx=8, pady=4, sticky="w")


def select_assignee(_event):
    assignee_entry.set(assignee_entry.get().split(" - ", 1)[0])


team_entry.bind(
    "<KeyRelease>",
    lambda event: filter_options(event.widget, component_options)
)
assignee_entry.bind(
    "<KeyRelease>",
    lambda event: filter_options(event.widget, assignee_options)
)
assignee_entry.bind("<<ComboboxSelected>>", select_assignee)
issue_type.bind(
    "<KeyRelease>",
    lambda event: filter_options(event.widget, issue_options)
)

root.after(100, load_projects)
root.after(100, load_issue_types)

#JQL Text box
tk.Label(root, text="JQL").grid(row=8, column=0, padx=8, pady=4)
jql_text = tk.Text(
    root,
    height=8,
    width=60
)
jql_text.grid(
    row=9,
    column=0,
    columnspan=3,
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
        graph_frame.grid(row=6, column=0, columnspan=2, sticky="ew", padx=8)
        graph_button.config(text="▼ Graph Options")
        graphs_visible = True

graph_button = ttk.Button(
    root,
    text="▶ Graph Options",
    command=toggle_graphs
)

graph_button.grid(row=5, column=0, padx=8, pady=4)

#================================
# GENERATE JQL
#================================
def generate_jql():
    jql = ""
    conditions = []

    days_since_created = date_entry.get()
    project = project_entry.get().strip()
    team = team_entry.get().strip()
    issue = issue_type.get()

    if days_since_created:
        jql = f"created >= -{days_since_created}d"
    else:
        jql = "created >= -7300d"

    # Projects (single or comma-separated)
    if project:
        projects = [
            p.strip()
            for p in project.split(",")
            if p.strip()
        ]

        if len(projects) == 1:
            conditions.append(
                f"project = {projects[0]}"
            )
        else:
            conditions.append(
                f"project in ({', '.join(projects)})"
            )

    # Components / Teams (single or comma-separated)
    if team:
        teams = [
            t.strip()
            for t in team.split(",")
            if t.strip()
        ]

        quoted_teams = [
            f'"{t}"'
            for t in teams
        ]

        if len(quoted_teams) == 1:
            conditions.append(
                f"component = {quoted_teams[0]}"
            )
        else:
            conditions.append(
                f"component in ({', '.join(quoted_teams)})"
            )

    if issue != "All":
        conditions.append(
            f"issuetype = {issue}"
        )

    # Assignees (single or comma-separated)
    assignees = assignee_entry.get().strip()

    if assignees:
        assignee_list = [
            user.strip()
            for user in assignees.split(",")
            if user.strip()
        ]

        quoted_assignees = [
            f'"{user}"'
            if " " in user or "," in user
            else user
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
    row=7,
    column=0,
    padx=8,
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