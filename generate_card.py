#!/usr/bin/env python3
"""
GitHub Profile Stats Card SVG Generator
Theme: Storm Flow Pro (#004e92 -> #000428)
Zero external dependencies.
Fetches all-time contributions across all active years.
"""

import os
import sys
import json
import urllib.request
import urllib.error
import datetime
from xml.sax.saxutils import escape

# --- Default Config & Demo Data ---
DEFAULT_OUTPUT = "stats-card.svg"
DEFAULT_USERNAME = os.environ.get("GITHUB_REPOSITORY_OWNER", "mohanraj9342")

DEMO_STATS = {
    "name": "Mohanraj V",
    "login": "mohanraj9342",
    "total_contributions": 1428,
    "current_streak": 24,
    "longest_streak": 89,
    "total_stars": 156,
    "total_prs": 42,
    "total_issues": 19,
    "total_commits": 1180,
    "languages": [
        {"name": "Python", "color": "#3572A5", "percent": 42.5},
        {"name": "TypeScript", "color": "#3178c6", "percent": 28.0},
        {"name": "JavaScript", "color": "#f1e05a", "percent": 15.2},
        {"name": "HTML", "color": "#e34c26", "percent": 8.5},
        {"name": "CSS", "color": "#563d7c", "percent": 5.8},
    ]
}

LANGUAGE_FALLBACK_COLORS = {
    "Python": "#3572A5", "TypeScript": "#3178c6", "JavaScript": "#f1e05a",
    "HTML": "#e34c26", "CSS": "#563d7c", "C++": "#f34b7d", "C": "#555555",
    "Go": "#00ADD8", "Rust": "#dea584", "Java": "#b07219", "Shell": "#89e051",
    "Vue": "#41b883", "React": "#61dafb", "Dart": "#00B4AB",
}

# --- GraphQL Queries ---
INIT_QUERY = """
query($login: String!) {
  user(login: $login) {
    name
    login
    createdAt
    repositories(first: 100, ownerAffiliations: OWNER, isFork: false, orderBy: {field: PUSHED_AT, direction: DESC}) {
      nodes {
        name
        stargazerCount
        languages(first: 10, orderBy: {field: SIZE, direction: DESC}) {
          edges {
            size
            node {
              name
              color
            }
          }
        }
      }
    }
  }
}
"""

INIT_VIEWER_QUERY = """
query {
  viewer {
    name
    login
    createdAt
    repositories(first: 100, ownerAffiliations: OWNER, isFork: false, orderBy: {field: PUSHED_AT, direction: DESC}) {
      nodes {
        name
        stargazerCount
        languages(first: 10, orderBy: {field: SIZE, direction: DESC}) {
          edges {
            size
            node {
              name
              color
            }
          }
        }
      }
    }
  }
}
"""

YEAR_QUERY = """
query($login: String!, $from: DateTime!, $to: DateTime!) {
  user(login: $login) {
    contributionsCollection(from: $from, to: $to) {
      totalCommitContributions
      totalIssueContributions
      totalPullRequestContributions
      totalRepositoryContributions
      contributionCalendar {
        totalContributions
        weeks {
          contributionDays {
            contributionCount
            date
          }
        }
      }
    }
  }
}
"""

def graphql_request(token, query, variables=None):
    url = "https://api.github.com/graphql"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "User-Agent": "GitHub-Stats-Card-Generator"
    }
    payload_dict = {"query": query}
    if variables:
        payload_dict["variables"] = variables
        
    payload = json.dumps(payload_dict).encode('utf-8')
    req = urllib.request.Request(url, data=payload, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req) as response:
            res_data = json.loads(response.read().decode('utf-8'))
            if "errors" in res_data:
                print(f"GraphQL Errors: {res_data['errors']}", file=sys.stderr)
                return None
            return res_data.get("data")
    except Exception as e:
        print(f"Error fetching data from GitHub API: {e}", file=sys.stderr)
        return None

def fetch_all_time_stats(token, username=None):
    # 1. Fetch initial user info (createdAt and repos)
    print("Fetching user base info and repositories...", file=sys.stderr)
    if username:
        init_data = graphql_request(token, INIT_QUERY, {"login": username})
        if init_data: user_node = init_data.get("user")
        else: user_node = None
    else:
        init_data = graphql_request(token, INIT_VIEWER_QUERY)
        if init_data: user_node = init_data.get("viewer")
        else: user_node = None

    if not user_node:
        return None

    created_at = user_node.get("createdAt")
    if not created_at:
        start_year = datetime.datetime.utcnow().year
    else:
        # e.g., "2020-10-10T10:10:10Z"
        start_year = int(created_at[:4])
        
    current_year = datetime.datetime.utcnow().year

    # Base aggregate
    agg = {
        "name": user_node.get("name") or user_node.get("login") or "GitHub User",
        "login": user_node.get("login") or "",
        "total_contributions": 0,
        "total_commits": 0,
        "total_issues": 0,
        "total_prs": 0,
        "days": [],
        "repositories": user_node.get("repositories")
    }

    # 2. Fetch contributions for every year
    login = user_node.get("login") # Need actual login for YEAR_QUERY
    if not login:
        print("Could not determine user login.", file=sys.stderr)
        return None

    for year in range(start_year, current_year + 1):
        print(f"Fetching contributions for {year}...", file=sys.stderr)
        from_date = f"{year}-01-01T00:00:00Z"
        to_date = f"{year}-12-31T23:59:59Z"
        
        y_data = graphql_request(token, YEAR_QUERY, {"login": login, "from": from_date, "to": to_date})
        
        if y_data and y_data.get("user") and y_data["user"].get("contributionsCollection"):
            contribs = y_data["user"]["contributionsCollection"]
            agg["total_commits"] += contribs.get("totalCommitContributions", 0)
            agg["total_issues"] += contribs.get("totalIssueContributions", 0)
            agg["total_prs"] += contribs.get("totalPullRequestContributions", 0)
            
            cal = contribs.get("contributionCalendar", {})
            agg["total_contributions"] += cal.get("totalContributions", 0)
            
            for week in cal.get("weeks", []):
                for day in week.get("contributionDays", []):
                    agg["days"].append(day)

    return agg

def process_stats(agg_data):
    if not agg_data:
        return DEMO_STATS

    # Calculate streaks
    days = agg_data["days"]
    # Sort strictly by date across all years
    days.sort(key=lambda d: d["date"])
    
    # Filter out duplicate dates if any boundary overlaps occurred
    unique_days = {}
    for d in days:
        unique_days[d["date"]] = d
        
    sorted_unique_days = [unique_days[k] for k in sorted(unique_days.keys())]

    current_streak = 0
    longest_streak = 0
    temp_streak = 0

    today_str = datetime.datetime.utcnow().strftime("%Y-%m-%d")

    # Longest streak calculation
    for day in sorted_unique_days:
        if day["contributionCount"] > 0:
            temp_streak += 1
            if temp_streak > longest_streak:
                longest_streak = temp_streak
        else:
            temp_streak = 0

    # Current streak calculation (scan backwards from latest)
    idx = len(sorted_unique_days) - 1
    while idx >= 0:
        day = sorted_unique_days[idx]
        d_date = day["date"]
        d_count = day["contributionCount"]

        if d_date > today_str:
            # Future days
            idx -= 1
            continue

        if d_date == today_str and d_count == 0:
            idx -= 1
            continue

        if d_count > 0:
            current_streak += 1
            idx -= 1
        else:
            if d_date != today_str and d_date < today_str:
                break
            idx -= 1

    # Total Stars & Languages
    repos = agg_data.get("repositories", {}).get("nodes", [])
    total_stars = 0
    lang_sizes = {}
    lang_colors = {}

    for repo in repos:
        total_stars += repo.get("stargazerCount", 0)
        langs = repo.get("languages", {}).get("edges", [])
        for edge in langs:
            l_size = edge.get("size", 0)
            l_node = edge.get("node", {})
            l_name = l_node.get("name")
            l_color = l_node.get("color")

            if l_name:
                lang_sizes[l_name] = lang_sizes.get(l_name, 0) + l_size
                if l_color and l_name not in lang_colors:
                    lang_colors[l_name] = l_color

    total_lang_bytes = sum(lang_sizes.values())
    sorted_langs = sorted(lang_sizes.items(), key=lambda x: x[1], reverse=True)[:5]

    languages = []
    for l_name, l_bytes in sorted_langs:
        pct = round((l_bytes / total_lang_bytes * 100), 1) if total_lang_bytes > 0 else 0
        color = lang_colors.get(l_name) or LANGUAGE_FALLBACK_COLORS.get(l_name, "#888888")
        languages.append({
            "name": l_name,
            "color": color,
            "percent": pct
        })

    return {
        "name": agg_data["name"],
        "login": agg_data["login"],
        "total_contributions": agg_data["total_contributions"],
        "current_streak": current_streak,
        "longest_streak": longest_streak,
        "total_stars": total_stars,
        "total_prs": agg_data["total_prs"],
        "total_issues": agg_data["total_issues"],
        "total_commits": agg_data["total_commits"],
        "languages": languages
    }

def generate_svg(stats):
    name = escape(str(stats["name"]))
    login = escape(str(stats["login"]))
    total_contribs = f"{stats['total_contributions']:,}"
    current_streak = f"{stats['current_streak']:,}"
    longest_streak = f"{stats['longest_streak']:,}"
    stars = f"{stats['total_stars']:,}"
    prs = f"{stats['total_prs']:,}"
    commits = f"{stats['total_commits']:,}"

    langs = stats.get("languages", [])

    lang_labels_svg = []
    y_pos = 50
    for lang in langs:
        color = escape(lang["color"])
        l_name = escape(lang["name"])
        pct = lang["percent"]

        lang_labels_svg.append(f"""
        <g transform="translate(20, {y_pos})">
            <circle cx="6" cy="6" r="5" fill="{color}" />
            <text x="18" y="10" class="lang-name">{l_name}</text>
            <text x="245" y="10" class="lang-pct" text-anchor="end">{pct}%</text>
            <rect x="0" y="18" width="245" height="7" rx="3.5" fill="rgba(255,255,255,0.08)"/>
            <rect x="0" y="18" width="{int(245 * (pct / 100))}" height="7" rx="3.5" fill="{color}"/>
        </g>
        """)
        y_pos += 36

    lang_labels_content = "\n".join(lang_labels_svg)

    svg = f"""<svg xmlns="http://www.w3.org/2000/svg" width="800" height="360" viewBox="0 0 800 360" fill="none">
    <defs>
        <!-- Storm Flow Pro Gradient -->
        <linearGradient id="bg-grad" x1="0%" y1="0%" x2="100%" y2="100%">
            <stop offset="0%" stop-color="#004e92" />
            <stop offset="100%" stop-color="#000428" />
        </linearGradient>

        <!-- Glassmorphic Border Gradient -->
        <linearGradient id="glass-stroke" x1="0%" y1="0%" x2="100%" y2="100%">
            <stop offset="0%" stop-color="rgba(255, 255, 255, 0.25)" />
            <stop offset="100%" stop-color="rgba(255, 255, 255, 0.05)" />
        </linearGradient>
    </defs>

    <style>
        .title {{ font-family: 'Segoe UI', -apple-system, BlinkMacSystemFont, Roboto, sans-serif; font-size: 22px; font-weight: 700; fill: #ffffff; letter-spacing: 0.5px; }}
        .subtitle {{ font-family: 'Segoe UI', -apple-system, BlinkMacSystemFont, Roboto, sans-serif; font-size: 12px; font-weight: 500; fill: rgba(255, 255, 255, 0.6); text-transform: uppercase; letter-spacing: 1.5px; }}
        .stat-label {{ font-family: 'Segoe UI', -apple-system, BlinkMacSystemFont, Roboto, sans-serif; font-size: 13px; font-weight: 500; fill: rgba(255, 255, 255, 0.7); }}
        .stat-value {{ font-family: 'Segoe UI', -apple-system, BlinkMacSystemFont, Roboto, sans-serif; font-size: 20px; font-weight: 700; fill: #ffffff; }}
        .stat-unit {{ font-family: 'Segoe UI', -apple-system, BlinkMacSystemFont, Roboto, sans-serif; font-size: 11px; font-weight: 400; fill: rgba(255, 255, 255, 0.5); }}
        .section-header {{ font-family: 'Segoe UI', -apple-system, BlinkMacSystemFont, Roboto, sans-serif; font-size: 15px; font-weight: 600; fill: #ffffff; letter-spacing: 0.5px; }}
        .lang-name {{ font-family: 'Segoe UI', -apple-system, BlinkMacSystemFont, Roboto, sans-serif; font-size: 12px; font-weight: 600; fill: #e6f1ff; }}
        .lang-pct {{ font-family: 'Segoe UI', -apple-system, BlinkMacSystemFont, Roboto, sans-serif; font-size: 12px; font-weight: 500; fill: rgba(255, 255, 255, 0.7); }}
        
        .card-bg {{ fill: url(#bg-grad); rx: 16px; }}
        .panel {{ fill: rgba(255, 255, 255, 0.05); stroke: url(#glass-stroke); stroke-width: 1.2px; rx: 12px; }}
        .icon {{ fill: #00c6ff; }}
    </style>

    <!-- Main Card Frame -->
    <rect width="800" height="360" class="card-bg" />

    <!-- Header Block -->
    <g transform="translate(35, 45)">
        <text class="title">{name}</text>
        <text y="20" class="subtitle">@{login} • GitHub Analytics (All-Time)</text>
        <rect x="0" y="32" width="730" height="1" fill="rgba(255, 255, 255, 0.12)" />
    </g>

    <!-- Left Panel: Key Stats Grid -->
    <g transform="translate(35, 100)">
        <rect width="430" height="225" class="panel" />
        
        <!-- Total Contributions -->
        <g transform="translate(25, 25)">
            <circle cx="16" cy="16" r="16" fill="rgba(0, 198, 255, 0.15)" />
            <path class="icon" d="M19 4h-1V2h-2v2H8V2H6v2H5c-1.11 0-1.99.9-1.99 2L3 20c0 1.1.89 2 2 2h14c1.1 0 2-.9 2-2V6c0-1.1-.9-2-2-2zm0 16H5V9h14v11z" transform="translate(3, 3) scale(0.8)"/>
            <text x="45" y="14" class="stat-label">Total Contributions</text>
            <text x="45" y="34" class="stat-value">{total_contribs}</text>
        </g>

        <!-- Current Streak -->
        <g transform="translate(230, 25)">
            <circle cx="16" cy="16" r="16" fill="rgba(255, 154, 0, 0.15)" />
            <path fill="#ff9a00" d="M13.5 1.5s0 3-2.5 5.5c-2.5 2.5-3.5 3.5-3.5 5.5 0 2.21 1.79 4 4 4s4-1.79 4-4c0-3.5-2-6-2-11z" transform="translate(5, 4) scale(0.9)"/>
            <text x="45" y="14" class="stat-label">Current Streak</text>
            <text x="45" y="34" class="stat-value">{current_streak} <tspan class="stat-unit">days</tspan></text>
        </g>

        <!-- Longest Streak -->
        <g transform="translate(25, 95)">
            <circle cx="16" cy="16" r="16" fill="rgba(255, 215, 0, 0.15)" />
            <path fill="#ffd700" d="M7 2v11h3v9l7-12h-4l4-8z" transform="translate(6, 4) scale(0.9)"/>
            <text x="45" y="14" class="stat-label">Longest Streak</text>
            <text x="45" y="34" class="stat-value">{longest_streak} <tspan class="stat-unit">days</tspan></text>
        </g>

        <!-- Stars -->
        <g transform="translate(230, 95)">
            <circle cx="16" cy="16" r="16" fill="rgba(255, 230, 0, 0.15)" />
            <path fill="#ffe600" d="M12 17.27L18.18 21l-1.64-7.03L22 9.24l-7.19-.61L12 2 9.19 8.63 2 9.24l5.46 4.73L5.82 21z" transform="translate(4, 4) scale(0.8)"/>
            <text x="45" y="14" class="stat-label">Total Stars</text>
            <text x="45" y="34" class="stat-value">{stars}</text>
        </g>

        <!-- Pull Requests -->
        <g transform="translate(25, 165)">
            <circle cx="16" cy="16" r="16" fill="rgba(168, 85, 247, 0.15)" />
            <path fill="#a855f7" d="M6 2a2 2 0 00-2 2v12a2 2 0 002 2h2a2 2 0 002-2V4a2 2 0 00-2-2H6zm10 0a2 2 0 00-2 2v12a2 2 0 002 2h2a2 2 0 002-2V4a2 2 0 00-2-2h-2z" transform="translate(4, 4) scale(0.8)"/>
            <text x="45" y="14" class="stat-label">Pull Requests</text>
            <text x="45" y="34" class="stat-value">{prs}</text>
        </g>

        <!-- Total Commits -->
        <g transform="translate(230, 165)">
            <circle cx="16" cy="16" r="16" fill="rgba(52, 211, 153, 0.15)" />
            <path fill="#34d399" d="M12 6a6 6 0 00-5.65 4H2v4h4.35A6 6 0 0017.65 14H22v-4h-4.35A6 6 0 0012 6zm0 8a2 2 0 110-4 2 2 0 010 4z" transform="translate(2, 4) scale(0.8)"/>
            <text x="45" y="14" class="stat-label">Total Commits</text>
            <text x="45" y="34" class="stat-value">{commits}</text>
        </g>
    </g>

    <!-- Right Panel: Top Languages -->
    <g transform="translate(485, 100)">
        <rect width="280" height="225" class="panel" />
        <text x="20" y="30" class="section-header">Most Used Languages</text>
        {lang_labels_content}
    </g>
</svg>"""
    return svg

def main():
    token = os.environ.get("CARD_TOKEN") or os.environ.get("GITHUB_TOKEN")
    is_demo = "--demo" in sys.argv or not token

    if is_demo:
        print("Note: Running in demo mode (no token detected or --demo flag passed). Using demo stats.", file=sys.stderr)
        stats = DEMO_STATS
    else:
        username = os.environ.get("CARD_USERNAME", DEFAULT_USERNAME)
        print(f"Fetching All-Time GitHub statistics for user: {username}...", file=sys.stderr)
        agg_data = fetch_all_time_stats(token, username)
        if agg_data:
            stats = process_stats(agg_data)
        else:
            print("Failed to fetch GitHub API data. Falling back to demo data.", file=sys.stderr)
            stats = DEMO_STATS

    svg_content = generate_svg(stats)
    
    output_filename = DEFAULT_OUTPUT
    if "--output" in sys.argv:
        idx = sys.argv.index("--output")
        if idx + 1 < len(sys.argv):
            output_filename = sys.argv[idx + 1]

    with open(output_filename, "w", encoding="utf-8") as f:
        f.write(svg_content)

    print(f"Successfully generated GitHub Stats SVG: {output_filename}", file=sys.stderr)

if __name__ == "__main__":
    main()
