# DEV-787: Automation Script – Export Nomad Job to CSV

## Overview
This repository contains a standalone Python script designed to extract key configurations from running HashiCorp Nomad jobs and export them into a structured CSV format. 

The exported fields include `id`, `job_name`, `image`, `ports` (both static and dynamic), `cpu`, and `memory`. Having this job data in CSV format facilitates auditing, reporting, and sharing Nomad job configurations without requiring direct access to the Nomad UI or API.

## Features
- **Zero Dependencies:** Pure Python 3.7+ standard library (`urllib.request`, `json`, `csv`, `argparse`, etc.). Runs anywhere `python3` is installed.
- **Detailed Task Extraction:** Writes one CSV row per task, successfully handling both Docker jobs (pulls `image` from task config) and non-Docker drivers.
- **Port Mapping:** Accurately captures both reserved (static) and dynamic port mappings from the task group's network stanza (e.g., `http:8080->80`).
- **Flexible Authentication:** Supports Nomad auth/TLS conventions via env vars or flags (`NOMAD_ADDR`, `NOMAD_TOKEN`, `NOMAD_CACERT`, `NOMAD_SKIP_VERIFY`).
- **Targeted Exports:** Includes `--namespace` and `--status` filters.

## Usage

You can run the script against a local Nomad agent or a remote cluster.

```bash
# Against a local Nomad agent (default: http://127.0.0.1:4646)
python3 export_nomad_jobs_to_csv.py

# Remote cluster with ACL token and custom output path
NOMAD_ADDR=https://nomad.example.com:4646 NOMAD_TOKEN=xxxx \
    python3 export_nomad_jobs_to_csv.py -o jobs_report.csv
```

## Local Testing Environment (Vagrant)

A full local testing environment is included to quickly spin up a Nomad dev agent and validate the script.

### Prerequisites
- VirtualBox
- Vagrant

### Setup Steps
1. Boot the environment:
   ```bash
   vagrant up
   ```
   *This provisions an Ubuntu VM, installs Docker and Nomad, starts Nomad in dev mode, and registers a sample job (`example-job.nomad.hcl`).*

2. View the Nomad UI:
   Open `http://localhost:4646` in your browser.

3. Run the export script from your host (Vagrant automatically forwards port 4646):
   ```bash
   python export_nomad_jobs_to_csv.py --addr http://localhost:4646 -o jobs.csv
   ```

4. You can also register a secondary job to test multi-job exports:
   ```bash
   vagrant ssh
   nomad job run /vagrant/redis-cache.nomad.hcl
   ```

## Troubleshooting
- **VirtualBox Boot Timeouts / "Invalid State" on Windows:** Ensure Hyper-V, WSL2, or Credential Guard are not conflicting with VirtualBox's VT-x extensions. You may need to enable "Windows Hypervisor Platform" or temporarily disable Hyper-V.
- **Path Issues inside VM:** If you SSH into the VM, the script is located in the synced directory `/vagrant/export_nomad_jobs_to_csv.py`.

## Directory Structure
- `export_nomad_jobs_to_csv.py`: The core automation script.
- `Vagrantfile`: Configuration for the local testing VM.
- `provision.sh`: Bootstraps Docker and Nomad on the guest VM.
- `*.nomad.hcl`: Sample jobs for testing static and dynamic port allocations.
- `Screenshots/`: Contains visual documentation of the Nomad UI, script execution, and Vagrant provisioning.

## License

Released under the [MIT License](LICENSE).
