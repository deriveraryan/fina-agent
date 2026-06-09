"""Notification scheduled tasks and orchestration.

Aggregates recent AgentScanLog database records since a run timestamp
and dispatches beautifully structured summary reports to administrators.
"""

from datetime import datetime
from typing import Any
from features.shared.graphql_client import execute_graphql_operation
from features.shared.observability import BackendObservability
from features.notifications.email import send_email
from features.notifications.memory import execute_agent_memory_loop

import re


def convert_markdown_to_html(md_text: str) -> str:
    """Converts a basic markdown subset (bullets, bold, code, links, paragraphs) into styled HTML."""
    if not md_text:
        return ""

    # 1. Strip the ```json ... ``` programmatic block if present in the text
    md_text = re.sub(r"```json\s*.*?\s*```", "", md_text, flags=re.DOTALL)
    md_text = md_text.strip()

    # 2. Escape HTML special characters
    escaped = md_text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

    # 3. Parse inline code: `code`
    escaped = re.sub(
        r"`([^`\n]+)`",
        r'<code style="font-family: monospace; background-color: #FAF8FC; border: 1px solid #7A5CBA; padding: 2px 4px; border-radius: 4px; color: #4C2A75; font-size: 85%; font-weight: 600;">\1</code>',
        escaped
    )

    # 4. Parse bold text: **bold**
    escaped = re.sub(
        r"\*\*([^\*\n]+)\*\*",
        r'<strong style="color: #4C2A75; font-weight: 700;">\1</strong>',
        escaped
    )

    # 5. Parse links: [text](url)
    escaped = re.sub(
        r"\[([^\]\n]+)\]\(([^)\n]+)\)",
        r'<a href="\2" style="color: #7A5CBA; text-decoration: none; font-weight: 600; border-bottom: 1px dashed #7A5CBA;">\1</a>',
        escaped
    )

    # 6. Parse bullet lists line-by-line
    lines = escaped.split("\n")
    processed_lines = []
    in_list = False

    for line in lines:
        line_stripped = line.strip()
        match = re.match(r"^[\*\-]\s+(.+)$", line_stripped)
        if match:
            if not in_list:
                processed_lines.append('<ul style="margin: 8px 0; padding-left: 20px; color: #1E132A; font-family: \'Inter\', sans-serif; font-size: 13px; line-height: 1.6;">')
                in_list = True
            item_text = match.group(1)
            processed_lines.append(f'<li style="margin-bottom: 6px;">{item_text}</li>')
        else:
            if in_list:
                processed_lines.append('</ul>')
                in_list = False

            if line_stripped:
                processed_lines.append(f'<p style="margin: 12px 0; color: #1E132A; font-family: \'Inter\', sans-serif; font-size: 13px; line-height: 1.6;">{line_stripped}</p>')

    if in_list:
        processed_lines.append('</ul>')

    return "\n".join(processed_lines)


async def send_summary_email(
    recipient_email: str, run_start_time: datetime, agent: Any = None
) -> bool:
    """Queries AgentScanLog records since run_start_time, compiles metrics, and emails a summary."""
    BackendObservability.info(
        f"Compiling post-run summary email for {recipient_email} since {run_start_time}."
    )

    # Format timezone-aware or naive datetimes correctly for standard ISO 8601 UTC format.
    since_timestamp = run_start_time.isoformat()
    if since_timestamp.endswith("+00:00"):
        since_timestamp = since_timestamp[:-6] + "Z"
    elif not since_timestamp.endswith("Z"):
        since_timestamp += "Z"

    try:
        response = await execute_graphql_operation(
            operation_name="ListScansSince", variables={"since": since_timestamp}
        )
        logs = ((response or {}).get("data") or {}).get("agentScanLogs") or []
    except Exception as exc:
        BackendObservability.error(
            "Failed to load recent agent scan logs for summary report.", exception=exc
        )
        logs = []

    try:
        listings_response = await execute_graphql_operation(
            operation_name="ListRecentListings", variables={"since": since_timestamp}
        )
        recent_listings = ((listings_response or {}).get("data") or {}).get("listings") or []
    except Exception as exc:
        BackendObservability.error(
            "Failed to load recent listings for category breakdown.", exception=exc
        )
        recent_listings = []

    # Category breakdown accumulation
    category_counts: dict[str, dict[str, int]] = {
        "RESTAURANT": {"created": 0, "updated": 0},
        "CAFE": {"created": 0, "updated": 0},
        "SHOP": {"created": 0, "updated": 0},
        "CHURCH": {"created": 0, "updated": 0},
        "SERVICES": {"created": 0, "updated": 0},
    }

    for l in recent_listings:
        cats = l.get("categories") or ["UNKNOWN"]
        created_at_str = l.get("createdAt") or ""
        updated_at_str = l.get("updatedAt") or ""

        for cat_raw in cats:
            cat = cat_raw.upper()
            if cat not in category_counts:
                category_counts[cat] = {"created": 0, "updated": 0}

            if created_at_str >= since_timestamp:
                category_counts[cat]["created"] += 1
            elif updated_at_str >= since_timestamp:
                category_counts[cat]["updated"] += 1


    insights = None
    if agent is not None:
        try:
            insights = await execute_agent_memory_loop(agent, run_start_time, logs)
        except Exception as exc:
            BackendObservability.error(
                "Failed to execute agent memory loop for summary email.", exception=exc
            )
            insights = f"Memory loop error: {exc}"

    # Aggregated metrics
    total_scans = len(logs)
    total_found = 0
    total_created = 0
    total_updated = 0
    total_flagged = 0
    total_duration_ms = 0
    success_count = 0
    failure_count = 0

    cities_scanned: set[str] = set()
    sources_scanned: set[str] = set()
    failures: list[dict[str, Any]] = []

    city_breakdown: dict[str, dict[str, int]] = {}

    for log in logs:
        city = log.get("city", "UNKNOWN")
        source = log.get("source", "UNKNOWN")
        scan_type = log.get("scanType", "UNKNOWN")
        status = log.get("status", "UNKNOWN")

        found = log.get("listingsFound", 0)
        created = log.get("listingsCreated", 0)
        updated = log.get("listingsUpdated", 0)
        flagged = log.get("listingsFlagged", 0)
        duration = log.get("durationMs", 0)

        total_found += found
        total_created += created
        total_updated += updated
        total_flagged += flagged
        total_duration_ms += duration

        cities_scanned.add(city)
        sources_scanned.add(source)

        if status == "SUCCESS":
            success_count += 1
        else:
            failure_count += 1
            failures.append({
                "city": city,
                "source": source,
                "scan_type": scan_type,
                "error": log.get("errorMessage") or "Unknown execution failure",
            })

        # Compile city-by-city breakdown
        if city not in city_breakdown:
            city_breakdown[city] = {
                "found": 0,
                "created": 0,
                "updated": 0,
                "flagged": 0,
                "scans": 0,
            }
        city_breakdown[city]["found"] += found
        city_breakdown[city]["created"] += created
        city_breakdown[city]["updated"] += updated
        city_breakdown[city]["flagged"] += flagged
        city_breakdown[city]["scans"] += 1

    total_duration_sec = total_duration_ms / 1000.0

    # Constructing beautiful, premium HTML Email Body
    html_content = f"""<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <title>Fina Scraper Run Summary</title>
  <style>
    body {{
      font-family: 'Outfit', 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
      background-color: #FAF8FC;
      color: #1E132A;
      margin: 0;
      padding: 0;
      -webkit-font-smoothing: antialiased;
    }}
    .container {{
      max-width: 850px;
      margin: 40px auto;
      background: #FFFFFF;
      border: 1px solid #EAE5F0;
      border-radius: 16px;
      overflow: hidden;
      box-shadow: 0 10px 30px -5px rgba(76, 42, 117, 0.08);
    }}
    .header {{
      background: linear-gradient(135deg, #4C2A75 0%, #7A5CBA 100%);
      padding: 40px 24px;
      text-align: center;
    }}
    .header h1 {{
      margin: 0;
      color: #FFFFFF;
      font-size: 26px;
      font-weight: 800;
      letter-spacing: -0.5px;
    }}
    .header p {{
      margin: 8px 0 0 0;
      color: #FFF3D6;
      font-size: 13px;
      letter-spacing: 1px;
      text-transform: uppercase;
      font-weight: 700;
    }}
    .content {{
      padding: 32px 24px;
    }}
    .card-table {{
      width: 100%;
      border-collapse: collapse;
      margin-bottom: 16px;
    }}
    .card {{
      background: #FAF8FC;
      border: 1px solid #EAE5F0;
      border-radius: 12px;
      padding: 18px;
      text-align: center;
      box-shadow: 0 2px 6px rgba(76, 42, 117, 0.02);
    }}
    .card-label {{
      font-size: 11px;
      text-transform: uppercase;
      letter-spacing: 1px;
      color: #7A5CBA;
      margin-bottom: 6px;
      font-weight: 700;
    }}
    .card-value {{
      font-size: 22px;
      font-weight: 800;
      color: #4C2A75;
    }}
    .success-text {{
      color: #C67B00; /* Caramelized Leche Flan Gold */
    }}
    .warning-text {{
      color: #7A5CBA; /* Vibrant Ube Light */
    }}
    .danger-text {{
      color: #D4380D; /* Warm Coral Red */
    }}
    h2 {{
      font-size: 15px;
      font-weight: 800;
      color: #4C2A75;
      text-transform: uppercase;
      letter-spacing: 1px;
      border-bottom: 2px solid #FFF3D6;
      padding-bottom: 8px;
      margin-top: 36px;
      margin-bottom: 16px;
    }}
    table.data-table {{
      width: 100%;
      border-collapse: collapse;
      margin-bottom: 24px;
      background: #FFFFFF;
      border-radius: 8px;
      overflow: hidden;
    }}
    table.data-table th {{
      text-align: left;
      font-size: 11px;
      text-transform: uppercase;
      letter-spacing: 0.5px;
      color: #7A5CBA;
      padding: 12px 14px;
      background: #FFF3D6;
      border-bottom: 2px solid #EAE5F0;
      font-weight: 700;
    }}
    table.data-table td {{
      padding: 14px;
      font-size: 13.5px;
      border-bottom: 1px solid #FAF8FC;
      color: #1E132A;
    }}
    table.data-table tr:hover td {{
      background: #FAF8FC;
    }}
    .error-log {{
      background: #FFF5F5;
      border: 1px solid #FCA5A5;
      border-left: 4px solid #D4380D;
      border-radius: 8px;
      padding: 16px;
      margin-bottom: 12px;
    }}
    .error-title {{
      font-weight: 700;
      font-size: 13.5px;
      color: #D4380D;
      margin-bottom: 4px;
    }}
    .error-desc {{
      font-family: monospace;
      font-size: 11.5px;
      color: #7F1D1D;
      white-space: pre-wrap;
    }}
    .footer {{
      text-align: center;
      padding: 24px;
      font-size: 11px;
      color: #7A5CBA;
      border-top: 1px solid #EAE5F0;
    }}
  </style>
</head>
<body>
  <div class="container">
    <div class="header">
      <h1>Fina Scraper Run Summary</h1>
      <p>Local Agent Pipeline Diagnostics & Results</p>
    </div>

    <div class="content">
      
      <!-- Metrics row 1 -->
      <table class="card-table">
        <tr>
          <td style="width: 50%; padding-right: 8px;">
            <div class="card">
              <div class="card-label">Run Status</div>
              <div class="card-value {'success-text' if failure_count == 0 else 'warning-text'}">
                {"COMPLETED" if failure_count == 0 else "PARTIAL FAILURE"}
              </div>
            </div>
          </td>
          <td style="width: 50%; padding-left: 8px;">
            <div class="card">
              <div class="card-label">Total Duration</div>
              <div class="card-value">{total_duration_sec:.2f}s</div>
            </div>
          </td>
        </tr>
      </table>

      <!-- Metrics row 2 -->
      <table class="card-table" style="margin-bottom: 32px;">
        <tr>
          <td style="width: 50%; padding-right: 8px;">
            <div class="card">
              <div class="card-label">Total Cities Scanned</div>
              <div class="card-value">{len(cities_scanned)}</div>
            </div>
          </td>
          <td style="width: 50%; padding-left: 8px;">
            <div class="card">
              <div class="card-label">Total Scans Executed</div>
              <div class="card-value">{total_scans}</div>
            </div>
          </td>
        </tr>
      </table>

      <h2>Scraped Data Aggregation</h2>
      
      <!-- Data Aggregation row 1 -->
      <table class="card-table">
        <tr>
          <td style="width: 50%; padding-right: 8px;">
            <div class="card">
              <div class="card-label">Listings Found</div>
              <div class="card-value">{total_found}</div>
            </div>
          </td>
          <td style="width: 50%; padding-left: 8px;">
            <div class="card">
              <div class="card-label">Listings Created</div>
              <div class="card-value success-text">{total_created}</div>
            </div>
          </td>
        </tr>
      </table>

      <!-- Data Aggregation row 2 -->
      <table class="card-table" style="margin-bottom: 32px;">
        <tr>
          <td style="width: 50%; padding-right: 8px;">
            <div class="card">
              <div class="card-label">Listings Updated</div>
              <div class="card-value warning-text">{total_updated}</div>
            </div>
          </td>
          <td style="width: 50%; padding-left: 8px;">
            <div class="card">
              <div class="card-label">Listings Flagged</div>
              <div class="card-value danger-text">{total_flagged}</div>
            </div>
          </td>
        </tr>
      </table>

      <h2>City-by-City Breakdown</h2>
      <table class="data-table">
        <thead>
          <tr>
            <th>City</th>
            <th>Scans</th>
            <th>Found</th>
            <th>Created</th>
            <th>Updated</th>
            <th>Flagged</th>
          </tr>
        </thead>
        <tbody>
        """

    for city, stats in sorted(city_breakdown.items()):
        html_content += f"""
          <tr>
            <td style="font-weight: 700; color: #4C2A75;">{city}</td>
            <td>{stats["scans"]}</td>
            <td>{stats["found"]}</td>
            <td class="success-text" style="font-weight: 700;">{stats["created"]}</td>
            <td class="warning-text">{stats["updated"]}</td>
            <td class="danger-text">{stats["flagged"]}</td>
          </tr>
        """

    html_content += """
        </tbody>
      </table>

      <h2>Category Breakdown</h2>
      <table class="data-table">
        <thead>
          <tr>
            <th>Category</th>
            <th>Created</th>
            <th>Updated</th>
          </tr>
        </thead>
        <tbody>
    """

    for cat, stats in sorted(category_counts.items()):
        html_content += f"""
          <tr>
            <td style="font-weight: 700; color: #4C2A75;">{cat.title()}</td>
            <td class="success-text" style="font-weight: 700;">{stats["created"]}</td>
            <td class="warning-text">{stats["updated"]}</td>
          </tr>
        """

    html_content += """
        </tbody>
      </table>
    """

    if failures:
        html_content += """
          <h2 class="danger-text">Execution Error Log</h2>
        """
        for fail in failures:
            html_content += f"""
              <div class="error-log">
                <div class="error-title">[{fail["city"]} - {fail["source"]} - {fail["scan_type"]}] Scan Failure</div>
                <div class="error-desc">{fail["error"]}</div>
              </div>
            """

    html_content += f"""
      <p style="font-size: 11px; color: #7A5CBA; margin-top: 36px; text-align: center;">
        Run started: {run_start_time.strftime('%Y-%m-%d %H:%M:%S UTC')}
      </p>
    </div>
"""

    if insights:
        html_insights = convert_markdown_to_html(insights)
        html_content += f"""
      <div style="padding: 0 24px 32px 24px;">
        <div style="padding: 20px; background: #FFF3D6; border: 1px solid #FFE4A0; border-left: 4px solid #C67B00; border-radius: 8px;">
          <div style="color: #4C2A75; font-weight: 800; margin-bottom: 12px; font-size: 12px; text-transform: uppercase; letter-spacing: 1px;">🧠 Agent Insights & System Memory</div>
          <div style="font-size: 13.5px; color: #1E132A;">
            {html_insights}
          </div>
        </div>
      </div>
        """

    html_content += f"""
    <div class="footer">
      This is an automated operational report generated by the Google Antigravity Fina local scraping agent.<br>
      © 2026 Fina AU Services.
    </div>
  </div>
</body>
</html>
"""

    # Plain text email body
    text_content = f"""FINA SCRAPER RUN SUMMARY
=========================
Run Status: {"COMPLETED" if failure_count == 0 else "PARTIAL FAILURE"}
Duration: {total_duration_sec:.2f} seconds
Scans Executed: {total_scans}
Cities Scanned: {len(cities_scanned)} ({', '.join(sorted(cities_scanned))})
Sources Scanned: {', '.join(sorted(sources_scanned))}

METRICS SUMMARY:
- Listings Found: {total_found}
- Listings Created: {total_created}
- Listings Updated: {total_updated}
- Listings Flagged: {total_flagged}

CITY BREAKDOWN:
"""
    for city, stats in sorted(city_breakdown.items()):
        text_content += f"- {city}: {stats['scans']} scans | {stats['found']} found | {stats['created']} created | {stats['updated']} updated | {stats['flagged']} flagged\n"

    text_content += "\nCATEGORY BREAKDOWN:\n"
    for cat, stats in sorted(category_counts.items()):
        text_content += f"- {cat.title()}: {stats['created']} created | {stats['updated']} updated\n"

    if failures:
        text_content += "\nEXECUTION ERROR LOG:\n"
        for fail in failures:
            text_content += f"- [{fail['city']} - {fail['source']} - {fail['scan_type']}]: {fail['error']}\n"

    if insights:
        text_content += f"\n🧠 AGENT INSIGHTS & SYSTEM MEMORY:\n==================================\n{insights}\n"

    text_content += f"\nRun started: {run_start_time.strftime('%Y-%m-%d %H:%M:%S UTC')}"

    # Dispatch email
    subject = f"Fina Scraper Run Summary - {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')} [Status: {'SUCCESS' if failure_count == 0 else 'PARTIAL FAILURE'}]"

    return await send_email(
        to_email=recipient_email,
        subject=subject,
        html_content=html_content,
        text_content=text_content,
    )
