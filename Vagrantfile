# -*- mode: ruby -*-
# vi: set ft=ruby :

Vagrant.configure("2") do |config|
  config.vm.box = "ubuntu/jammy64"
  config.vm.hostname = "nomad-dev"
  config.vm.boot_timeout = 600

  # Forward Nomad's HTTP API / Web UI to the host so the export
  # script (and a browser) can reach it at http://localhost:4646
  config.vm.network "forwarded_port", guest: 4646, host: 4646, auto_correct: true

  config.vm.provider "virtualbox" do |vb|
    vb.name   = "nomad-dev"
    vb.memory = 2048
    vb.cpus   = 2
    # Known workaround for VirtualBox 7.x NAT/DNS boot hangs
    vb.customize ["modifyvm", :id, "--natdnshostresolver1", "on"]
    # Uncomment to watch the actual boot screen if it stalls again:
    # vb.gui = true
  end

  # Installs Docker + Nomad, starts a Nomad dev agent, and
  # registers the sample job in example-job.nomad.hcl
  config.vm.provision "shell", path: "provision.sh"
end
