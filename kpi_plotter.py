def generate_report(jql, graphs_to_generate):
    import requests
    import os
    import pandas as pd
    import matplotlib.pyplot as plt
    import json

    # =========================
    # JIRA API CONFIG
    # =========================

    JIRA_URL = "https://jira.tandemdiabetes.com:8443"
    STORY_POINTS_FIELD = "customfield_10006"

    SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
    PAT_FILE = os.path.join(SCRIPT_DIR, "JIRA_PAT.json")

    if not os.path.exists(PAT_FILE):
        raise FileNotFoundError(f"PAT file not found: {PAT_FILE}")

    with open(PAT_FILE, "r") as f:
        config = json.load(f)

    PAT = config.get("pat")

    if not PAT:
        raise ValueError("No 'pat' field found in JIRA_PAT.json")

    headers = {
        "Authorization": f"Bearer {PAT}",
        "Accept": "application/json"
    }

    # =========================
    # DOWNLOAD JIRA ISSUES WITH PAGINATION
    # =========================

    all_issues = []
    start_at = 0
    page_size = 1000
    total_issues = None

    while True:
        response = requests.get(
            f"{JIRA_URL}/rest/api/2/search",
            headers=headers,
            params={
                "jql": jql,
                "startAt": start_at,
                "maxResults": page_size,
                "fields": f"summary,status,created,resolutiondate,{STORY_POINTS_FIELD}"
            }
        )

        response.raise_for_status()
        data = response.json()

        issues = data.get("issues", [])
        total_issues = data.get("total", 0)

        all_issues.extend(issues)

        print(f"Downloaded {len(all_issues)} of {total_issues} issues")

        if len(issues) == 0:
            break

        if start_at + len(issues) >= total_issues:
            break

        start_at += len(issues)

    print(f"Total matching issues: {total_issues}")
    print(f"Total issues retrieved: {len(all_issues)}")

    # =========================
    # BUILD DATAFRAME
    # =========================

    rows = []

    for issue in all_issues:
        fields = issue["fields"]

        rows.append({
            "Key": issue["key"],
            "Summary": fields.get("summary"),
            "Status": fields.get("status", {}).get("name"),
            "Created": fields.get("created"),
            "Resolved": fields.get("resolutiondate"),
            "StoryPoints": fields.get(STORY_POINTS_FIELD)
        })

    df = pd.DataFrame(rows)

    if df.empty:
        print("No issues found for this JQL.")
        return

    df["Created"] = pd.to_datetime(
        df["Created"],
        errors="coerce",
        utc=True
    ).dt.tz_localize(None)

    df["Resolved"] = pd.to_datetime(
        df["Resolved"],
        errors="coerce",
        utc=True
    ).dt.tz_localize(None)

    df["StoryPoints"] = pd.to_numeric(
        df["StoryPoints"],
        errors="coerce"
    ).fillna(0)

    print(f"Downloaded {len(df)} issues from Jira")
    print(df.head())
    print(df.columns)
    print(df["Status"].value_counts())
    print(df[["Key", "StoryPoints"]].head(20))
    print(f"Total Story Points in Downloaded Issues: {df['StoryPoints'].sum()}")

    # Remove rows with invalid created dates
    df = df[df["Created"].notna()].copy()

    if df.empty:
        print("No issues have valid Created dates.")
        return

    # =========================
    # CONFIG
    # =========================

    BUCKETS = [
        (0, 30),
        (31, 60),
        (61, 90),
        (91, 120)
    ]

    BUCKET_LABELS = [
        "0-30 Days since Opened",
        "31-60 Days since Opened",
        "61-90 Days since Opened",
        "91-120 Days since Opened"
    ]

    # =========================
    # BASIC COUNTS
    # =========================

    created_quantity = int(df["Created"].notna().sum())
    resolved_quantity = int(df["Resolved"].notna().sum())

    print(f"Total stories created in CSV: {created_quantity}")
    print(f"Total stories resolved in CSV: {resolved_quantity}")

    valid_created = df["Created"].dropna()
    valid_resolved = df["Resolved"].dropna()

    all_valid_dates = pd.concat([valid_created, valid_resolved])

    if not all_valid_dates.empty:
        csv_range_start = all_valid_dates.min().normalize()
        csv_range_end = all_valid_dates.max().normalize()
        month_count = (
            (csv_range_end.year - csv_range_start.year) * 12
            + (csv_range_end.month - csv_range_start.month)
            + 1
        )
    else:
        csv_range_start = df["Created"].min().normalize()
        csv_range_end = pd.Timestamp.today().normalize()
        month_count = 1

    month_count = max(month_count, 1)

    avg_created_per_month = created_quantity / month_count
    avg_resolved_per_month = resolved_quantity / month_count

    print(f"Average stories created per month: {avg_created_per_month:.2f}")
    print(f"Average stories resolved per month: {avg_resolved_per_month:.2f}")

    # =========================
    # MONTHLY CREATED AND RESOLVED ROLLING AVERAGES
    # =========================

    created_monthly = (
        df["Created"]
        .dropna()
        .dt.to_period("M")
        .value_counts()
        .sort_index()
    )

    resolved_monthly = (
        df["Resolved"]
        .dropna()
        .dt.to_period("M")
        .value_counts()
        .sort_index()
    )

    if created_monthly.empty and resolved_monthly.empty:
        month_index = pd.period_range(
            start=df["Created"].min().to_period("M"),
            end=pd.Timestamp.today().to_period("M"),
            freq="M"
        )
    elif created_monthly.empty:
        month_index = pd.period_range(
            start=resolved_monthly.index.min(),
            end=resolved_monthly.index.max(),
            freq="M"
        )
    elif resolved_monthly.empty:
        month_index = pd.period_range(
            start=created_monthly.index.min(),
            end=created_monthly.index.max(),
            freq="M"
        )
    else:
        month_index = pd.period_range(
            start=min(created_monthly.index.min(), resolved_monthly.index.min()),
            end=max(created_monthly.index.max(), resolved_monthly.index.max()),
            freq="M"
        )

    created_monthly = created_monthly.reindex(month_index, fill_value=0).astype(int)
    resolved_monthly = resolved_monthly.reindex(month_index, fill_value=0).astype(int)

    created_roll = created_monthly.rolling(window=3, min_periods=1).mean()
    resolved_roll = resolved_monthly.rolling(window=3, min_periods=1).mean()

    # =========================
    # BUILD DAILY DATE RANGE FOR OPEN STORY AGING
    # =========================

    start_date = df["Created"].min().normalize()
    end_date = pd.Timestamp.today().normalize()

    all_dates = pd.date_range(
        start=start_date,
        end=end_date,
        freq="D"
    )

    # =========================
    # OPEN STORY AGE BUCKETS
    # =========================

    results = []

    for current_date in all_dates:
        bucket_counts = [0] * len(BUCKETS)

        open_stories = df[
            (df["Created"] <= current_date)
            &
            (
                df["Resolved"].isna()
                |
                (df["Resolved"] > current_date)
            )
        ]

        for _, story in open_stories.iterrows():
            age_days = (current_date - story["Created"]).days

            for bucket_index, (min_age, max_age) in enumerate(BUCKETS):
                if min_age <= age_days <= max_age:
                    bucket_counts[bucket_index] += 1
                    break

        results.append([
            current_date,
            bucket_counts
        ])

    plot_dates = []
    bucket_series = [[] for _ in range(len(BUCKETS))]

    for date_value, bucket_values in results:
        plot_dates.append(date_value)

        for i in range(len(BUCKETS)):
            bucket_series[i].append(bucket_values[i])

    # =========================
    # SHARED DATA FOR CLOSURE AGE AND BUG GRAPHS
    # =========================

    resolved_age_df = df[
        df["Created"].notna() & df["Resolved"].notna()
    ].copy()

    if not resolved_age_df.empty:
        resolved_age_df["AgeAtResolutionDays"] = (
            resolved_age_df["Resolved"] - resolved_age_df["Created"]
        ).dt.days

        daily_avg_age = (
            resolved_age_df
            .assign(CloseDate=resolved_age_df["Resolved"].dt.normalize())
            .groupby("CloseDate", as_index=False)["AgeAtResolutionDays"]
            .mean()
            .sort_values("CloseDate")
        )

        daily_avg_age["RollingAvgAge"] = (
            daily_avg_age["AgeAtResolutionDays"]
            .rolling(window=7, min_periods=1)
            .mean()
        )
    else:
        daily_avg_age = pd.DataFrame(
            columns=["CloseDate", "AgeAtResolutionDays", "RollingAvgAge"]
        )

    bug_df = df.loc[
        df["Summary"].fillna("").str.contains("bug", case=False, na=False),
        ["Created", "Resolved", "Summary"]
    ].copy()

    bug_df = bug_df[bug_df["Created"].notna()].copy()

    bug_resolved_age_df = bug_df[
        bug_df["Created"].notna() & bug_df["Resolved"].notna()
    ].copy()

    if not bug_resolved_age_df.empty:
        bug_resolved_age_df["AgeAtResolutionDays"] = (
            bug_resolved_age_df["Resolved"] - bug_resolved_age_df["Created"]
        ).dt.days

        bug_daily_avg_age = (
            bug_resolved_age_df
            .assign(CloseDate=bug_resolved_age_df["Resolved"].dt.normalize())
            .groupby("CloseDate", as_index=False)["AgeAtResolutionDays"]
            .mean()
            .sort_values("CloseDate")
        )

        bug_daily_avg_age["BugRollingAvgAge"] = (
            bug_daily_avg_age["AgeAtResolutionDays"]
            .rolling(window=7, min_periods=1)
            .mean()
        )
    else:
        bug_daily_avg_age = pd.DataFrame(
            columns=["CloseDate", "AgeAtResolutionDays", "BugRollingAvgAge"]
        )

    # =========================
    # PLOTS
    # =========================

    saved_figures = []

    # =========================
    # GRAPH 1: STORY THROUGHPUT AND AGING
    # =========================

    if "throughput" in graphs_to_generate:
        fig1 = plt.figure(figsize=(14, 8))
        saved_figures.append(("story_throughput_and_aging", fig1))

        for i in range(len(BUCKETS)):
            plt.plot(
                plot_dates,
                bucket_series[i],
                label=BUCKET_LABELS[i]
            )

        plt.plot(
            month_index.to_timestamp(),
            created_roll,
            linestyle="--",
            linewidth=2,
            label="Rolling Avg Stories Created/Month"
        )

        plt.plot(
            month_index.to_timestamp(),
            resolved_roll,
            linestyle=":",
            linewidth=2,
            label="Rolling Avg Stories Resolved/Month"
        )

        plt.title("Number of Open Stories, and Throughput of Stories Created vs Resolved")
        plt.xlabel("Date")
        plt.ylabel("Number of Stories")
        plt.legend()
        plt.grid(True)
        plt.tight_layout()

    # =========================
    # GRAPH 2: AVERAGE AGE AT CLOSURE
    # =========================

    if "closure_age" in graphs_to_generate:
        if daily_avg_age.empty:
            print("No resolved issues found for Average Age at Closure graph.")
        else:
            fig2 = plt.figure(figsize=(14, 6))
            saved_figures.append(("average_age_closed_per_day", fig2))

            plt.plot(
                daily_avg_age["CloseDate"],
                daily_avg_age["RollingAvgAge"],
                linewidth=2.5,
                color="darkorange",
                label="All Stories"
            )

            if not bug_daily_avg_age.empty:
                plt.plot(
                    bug_daily_avg_age["CloseDate"],
                    bug_daily_avg_age["BugRollingAvgAge"],
                    linewidth=2.5,
                    color="forestgreen",
                    label="Only Bugs"
                )

            plt.title("Age of Tickets When Closed; 7 Day Rolling Average")
            plt.xlabel("Date")
            plt.ylabel("Average Age at Closure (Days)")
            plt.legend()
            plt.grid(True)
            plt.tight_layout()

    # =========================
    # GRAPH 3: BUG STORIES CREATED VS OPEN
    # =========================

    if "bugs" in graphs_to_generate:
        if bug_df.empty:
            print("No bug-related stories found for Bug Stories graph.")
        else:
            for _, row in bug_df.sort_values("Created").iterrows():
                created_str = row["Created"].strftime("%Y-%m-%d %H:%M:%S") if pd.notna(row["Created"]) else "NA"
                resolved_str = row["Resolved"].strftime("%Y-%m-%d %H:%M:%S") if pd.notna(row["Resolved"]) else "NA"
                summary = row["Summary"] if pd.notna(row["Summary"]) else ""
                print(f"- Created: {created_str} | Resolved: {resolved_str} | Summary: {summary}")

            bug_story_counts = (
                bug_df
                .assign(CreatedDate=lambda x: x["Created"].dt.normalize())
                .groupby("CreatedDate", as_index=False)
                .size()
                .rename(columns={"size": "BugStoriesCreated"})
                .sort_values("CreatedDate")
            )

            bug_date_range = pd.date_range(
                start=csv_range_start,
                end=csv_range_end,
                freq="D"
            )

            bug_daily_series = pd.DataFrame({"CreatedDate": bug_date_range})

            bug_daily_series = bug_daily_series.merge(
                bug_story_counts,
                on="CreatedDate",
                how="left"
            )

            bug_daily_series["BugStoriesCreated"] = (
                bug_daily_series["BugStoriesCreated"]
                .fillna(0)
                .astype(int)
            )

            bug_open_counts = []

            for current_date in bug_date_range:
                open_bug_stories = bug_df[
                    (bug_df["Created"] <= current_date)
                    &
                    (
                        bug_df["Resolved"].isna()
                        |
                        (bug_df["Resolved"] > current_date)
                    )
                ]

                bug_open_counts.append(int(open_bug_stories.shape[0]))

            bug_daily_series["BugStoriesOpen"] = bug_open_counts

            positive_open_days = int((bug_daily_series["BugStoriesOpen"] > 0).sum())
            zero_open_days = int((bug_daily_series["BugStoriesOpen"] == 0).sum())

            total_days = max((csv_range_end - csv_range_start).days, 1)

            if zero_open_days == 0:
                uptime_ratio = 0.0
            else:
                uptime_ratio = zero_open_days / total_days

            print(f"%Uptime (% of days with 0 bugs open): {uptime_ratio:.4f}")

            fig3 = plt.figure(figsize=(14, 6))
            saved_figures.append(("bug_stories_created_vs_open", fig3))

            plt.plot(
                bug_daily_series["CreatedDate"],
                bug_daily_series["BugStoriesCreated"],
                marker="o",
                linewidth=2,
                color="crimson",
                label="Bug Stories Created"
            )

            plt.plot(
                bug_daily_series["CreatedDate"],
                bug_daily_series["BugStoriesOpen"],
                marker="s",
                linewidth=2,
                color="royalblue",
                label="Bug Stories Open"
            )

            plt.title("Bug-Related Stories Created vs Open per Day")
            plt.xlabel("Date")
            plt.ylabel("Number of Bug Stories")
            plt.legend()
            plt.grid(True)

            plt.text(
                0.02,
                0.98,
                f"% of days with no bugs open: {uptime_ratio:.2%}",
                transform=plt.gca().transAxes,
                fontsize=11,
                verticalalignment="top",
                bbox=dict(boxstyle="round,pad=0.3", facecolor="white", alpha=0.8)
            )

            plt.tight_layout()

    # =========================
    # GRAPH 4: STORY POINTS COMPLETED PER WEEK
    # =========================

    if "story_points_biweekly" in graphs_to_generate:
        completed_points_df = df[
            df["Resolved"].notna()
        ].copy()

        if completed_points_df.empty:
            print("No resolved issues found for Story Points Completed Per Week graph.")
        else:
            completed_points_weekly = (
                completed_points_df
                .set_index("Resolved")
                .resample("2W")["StoryPoints"]
                .sum()
            )

            completed_points_weekly = completed_points_weekly.sort_index()

            completed_points_weekly_df = completed_points_weekly.reset_index()
            completed_points_weekly_df.columns = ["2WeekEnding", "StoryPointsCompleted"]

            completed_points_weekly_df["RollingAvgStoryPoints"] = (
                completed_points_weekly_df["StoryPointsCompleted"]
                .rolling(window=3, min_periods=1)
                .mean()
            )

            print("Story Points Completed Per Sprint (2 Weeks):")
            print(completed_points_weekly_df)

            fig4 = plt.figure(figsize=(14, 6))
            saved_figures.append(("story_points_completed_per_2week", fig4))

            plt.bar(
                completed_points_weekly_df["2WeekEnding"],
                completed_points_weekly_df["StoryPointsCompleted"],
                color="steelblue",
                label="Story Points Completed Per Sprint (2 Weeks)"
            )

            plt.plot(
                completed_points_weekly_df["2WeekEnding"],
                completed_points_weekly_df["RollingAvgStoryPoints"],
                color="darkorange",
                linewidth=2.5,
                marker="o",
                label="3-Sprint Rolling Average"
            )

            plt.title("Story Points Completed Per Sprint Over Time")
            plt.xlabel("Sprint Ending")
            plt.ylabel("Story Points Completed")
            plt.legend()
            plt.grid(True)
            plt.tight_layout()

    # =========================
    # SAVE PLOTS OPTION
    # =========================

    save_plots = "n"

    if save_plots in {"yes", "y"}:
        output_dir = os.path.join(SCRIPT_DIR, "KPI Plots")
        os.makedirs(output_dir, exist_ok=True)

        for filename, figure in saved_figures:
            output_path = os.path.join(output_dir, f"{filename}.png")
            figure.savefig(output_path, dpi=300, bbox_inches="tight")
            print(f"Saved plot: {output_path}")

    if saved_figures:
        plt.show()
    else:
        print("No graphs were selected.")


if __name__ == "__main__":
    generate_report(
        """
        issuetype = Story
        AND project = ECCO
        AND created >= -365d
        AND assignee in (rcheesman, ejuric, tcao, jtiu, awalsh, msaiger)
        """,
        [
            "throughput",
            "closure_age",
            "bugs",
            "story_points_weekly"
        ]
    )