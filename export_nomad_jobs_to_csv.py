#!/usr/bin/env python3
"""
export_nomad_jobs_to_csv.py

Export HashiCorp Nomad job configurations to a CSV file for
auditing, reporting, and documentation purposes, without needing
direct access to the Nomad UI.

For every job registered in Nomad, this script pulls the full job
specification from the Nomad HTTP API and writes one row per task
(fields like docker image, CPU, memory, and ports are defined at the
task level, so a job with multiple task groups/tasks produces
multiple rows, all sharing the same job id/name).

No third-party dependencies required - only the Python standard
library (Python 3.7+).

------------------------------------------------------------------
USAGE
------------------------------------------------------------------
    python3 export_nomad_jobs_to_csv.py [options]

Environment variables (standard Nomad CLI conventions - any of
these can also be passed as CLI flags, which take precedence):

    NOMAD_ADDR          Nomad API address (default: http://127.0.0.1:4646)
    NOMAD_TOKEN         ACL token, if ACLs are enabled
    NOMAD_NAMESPACE     Namespace to query (default: "*" = all namespaces)
    NOMAD_CACERT        Path to CA certificate for TLS verification
    NOMAD_CLIENT_CERT   Path to client certificate (mTLS)
    NOMAD_CLIENT_KEY    Path to client key (mTLS)
    NOMAD_SKIP_VERIFY   Set to "true" to skip TLS verification (not recommended)

------------------------------------------------------------------
EXAMPLES
------------------------------------------------------------------
    # Basic export using a local Nomad agent
    python3 export_nomad_jobs_to_csv.py

    # Export from a remote cluster with an ACL token, custom output path
    NOMAD_ADDR=https://nomad.example.com:4646 NOMAD_TOKEN=xxxx \\
        python3 export_nomad_jobs_to_csv.py -o jobs_report.csv

    # Export a single namespace only
    python3 export_nomad_jobs_to_csv.py --namespace production

    # Only currently running jobs
    python3 export_nomad_jobs_to_csv.py --status running

------------------------------------------------------------------
OUTPUT COLUMNS
------------------------------------------------------------------
    id, job_name, namespace, type, status, task_group, task_name,
    driver, image, cpu, memory, memory_max, ports, datacenters
"""

import argparse
import csv
import json
import os
import ssl
import sys
import urllib.error
import urllib.parse
import urllib.request

FIELDNAMES = [
    "id",
    "job_name",
    "namespace",
    "type",
    "status",
    "task_group",
    "task_name",
    "driver",
    "image",
    "cpu",
    "memory",
    "memory_max",
    "ports",
    "datacenters",
]


def env(name, default=None):
    return os.environ.get(name, default)


def parse_args():
    parser = argparse.ArgumentParser(
        description="Export Nomad job data (id, name, image, ports, cpu, memory, ...) to a CSV file.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "-o", "--output", default="nomad_jobs_export.csv",
        help="Path to output CSV file (default: nomad_jobs_export.csv)",
    )
    parser.add_argument(
        "--addr", default=env("NOMAD_ADDR", "http://127.0.0.1:4646"),
        help="Nomad API address (env: NOMAD_ADDR)",
    )
    parser.add_argument(
        "--token", default=env("NOMAD_TOKEN"),
        help="Nomad ACL token (env: NOMAD_TOKEN)",
    )
    parser.add_argument(
        "--namespace", default=env("NOMAD_NAMESPACE", "*"),
        help="Namespace to query, or '*' for all namespaces (default: *)",
    )
    parser.add_argument(
        "--cacert", default=env("NOMAD_CACERT"),
        help="Path to CA certificate for TLS verification (env: NOMAD_CACERT)",
    )
    parser.add_argument(
        "--client-cert", default=env("NOMAD_CLIENT_CERT"),
        help="Path to client certificate for mTLS (env: NOMAD_CLIENT_CERT)",
    )
    parser.add_argument(
        "--client-key", default=env("NOMAD_CLIENT_KEY"),
        help="Path to client key for mTLS (env: NOMAD_CLIENT_KEY)",
    )
    parser.add_argument(
        "--insecure", action="store_true",
        default=env("NOMAD_SKIP_VERIFY", "false").lower() == "true",
        help="Skip TLS certificate verification (env: NOMAD_SKIP_VERIFY). Not recommended.",
    )
    parser.add_argument(
        "--timeout", type=int, default=30,
        help="HTTP request timeout in seconds (default: 30)",
    )
    parser.add_argument(
        "--status", choices=["running", "pending", "dead", "all"], default="all",
        help="Filter jobs by status before exporting (default: all)",
    )
    return parser.parse_args()


def build_ssl_context(args):
    if not args.addr.lower().startswith("https"):
        return None
    if args.insecure:
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        return ctx
    ctx = ssl.create_default_context(cafile=args.cacert) if args.cacert else ssl.create_default_context()
    if args.client_cert and args.client_key:
        ctx.load_cert_chain(certfile=args.client_cert, keyfile=args.client_key)
    return ctx


def api_request(args, path, params=None):
    """GET a JSON endpoint from the Nomad HTTP API."""
    url = args.addr.rstrip("/") + path
    if params:
        clean = {k: v for k, v in params.items() if v is not None}
        if clean:
            url += "?" + urllib.parse.urlencode(clean)

    req = urllib.request.Request(url)
    if args.token:
        req.add_header("X-Nomad-Token", args.token)

    ctx = build_ssl_context(args)
    try:
        with urllib.request.urlopen(req, timeout=args.timeout, context=ctx) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")
        print(f"ERROR: HTTP {e.code} requesting {url}: {body}", file=sys.stderr)
        raise
    except urllib.error.URLError as e:
        print(f"ERROR: could not reach Nomad at {url}: {e.reason}", file=sys.stderr)
        raise


def format_ports(task_group):
    """Summarize the reserved/dynamic ports declared on a task group's networks."""
    parts = []
    for net in task_group.get("Networks") or []:
        for p in net.get("ReservedPorts") or []:
            label, value, to = p.get("Label", ""), p.get("Value", ""), p.get("To")
            if to and to not in (0, -1):
                parts.append(f"{label}:{value}->{to}")
            else:
                parts.append(f"{label}:{value}")
        for p in net.get("DynamicPorts") or []:
            label, to = p.get("Label", ""), p.get("To")
            if to and to not in (0, -1):
                parts.append(f"{label}:dynamic->{to}")
            else:
                parts.append(f"{label}:dynamic")
    return "; ".join(parts)


def extract_image(task):
    """Best-effort image/identifier extraction across driver types."""
    driver = task.get("Driver", "")
    config = task.get("Config") or {}
    image = config.get("image") or config.get("Image")
    if image:
        return image
    if driver == "docker":
        return ""
    command = config.get("command") or config.get("Command") or ""
    return f"(driver={driver}) {command}".strip() if driver else ""


def extract_rows(job):
    """Flatten one Nomad job spec into one CSV row per task."""
    job_id = job.get("ID", "")
    job_name = job.get("Name", "")
    namespace = job.get("Namespace", "default")
    job_type = job.get("Type", "")
    status = job.get("Status", "")
    datacenters = ",".join(job.get("Datacenters") or [])

    rows = []
    for tg in job.get("TaskGroups") or []:
        tg_name = tg.get("Name", "")
        ports = format_ports(tg)
        tasks = tg.get("Tasks") or []

        if not tasks:
            rows.append({
                "id": job_id, "job_name": job_name, "namespace": namespace,
                "type": job_type, "status": status, "task_group": tg_name,
                "task_name": "", "driver": "", "image": "",
                "cpu": "", "memory": "", "memory_max": "",
                "ports": ports, "datacenters": datacenters,
            })
            continue

        for task in tasks:
            resources = task.get("Resources") or {}
            rows.append({
                "id": job_id,
                "job_name": job_name,
                "namespace": namespace,
                "type": job_type,
                "status": status,
                "task_group": tg_name,
                "task_name": task.get("Name", ""),
                "driver": task.get("Driver", ""),
                "image": extract_image(task),
                "cpu": resources.get("CPU", ""),
                "memory": resources.get("MemoryMB", ""),
                "memory_max": resources.get("MemoryMaxMB", ""),
                "ports": ports,
                "datacenters": datacenters,
            })
    return rows


def main():
    args = parse_args()

    print(f"Connecting to Nomad at {args.addr} (namespace={args.namespace}) ...", file=sys.stderr)
    try:
        jobs = api_request(args, "/v1/jobs", {"namespace": args.namespace})
    except Exception:
        print("Failed to list jobs. Check --addr/--token (or NOMAD_ADDR/NOMAD_TOKEN) and connectivity.",
              file=sys.stderr)
        sys.exit(1)

    if args.status != "all":
        jobs = [j for j in jobs if j.get("Status") == args.status]

    if not jobs:
        print("No jobs found matching the given filters.", file=sys.stderr)
        sys.exit(0)

    print(f"Found {len(jobs)} job(s). Fetching full job specs ...", file=sys.stderr)

    rows = []
    for i, job_summary in enumerate(jobs, start=1):
        job_id = job_summary.get("ID")
        namespace = job_summary.get("Namespace", "default")
        print(f"  [{i}/{len(jobs)}] {job_id} (namespace={namespace})", file=sys.stderr)
        try:
            detail = api_request(
                args,
                f"/v1/job/{urllib.parse.quote(job_id, safe='')}",
                {"namespace": namespace},
            )
        except Exception:
            print(f"    WARNING: could not fetch details for job '{job_id}', skipping.", file=sys.stderr)
            continue
        rows.extend(extract_rows(detail))

    if not rows:
        print("No job data extracted; nothing to write.", file=sys.stderr)
        sys.exit(1)

    with open(args.output, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDNAMES)
        writer.writeheader()
        writer.writerows(rows)

    print(f"Done. Wrote {len(rows)} row(s) across {len(jobs)} job(s) to {args.output}", file=sys.stderr)


if __name__ == "__main__":
    main()
