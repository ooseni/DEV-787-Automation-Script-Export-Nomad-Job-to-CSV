job "example" {
  datacenters = ["dc1"]
  type        = "service"

  group "web" {
    count = 1

    network {
      port "http" {
        static = 8080
        to     = 80
      }
    }

    task "server" {
      driver = "docker"

      config {
        image = "hashicorp/http-echo:latest"
        args  = ["-text", "hello from nomad", "-listen", ":80"]
        ports = ["http"]
      }

      resources {
        cpu    = 200
        memory = 128
      }
    }
  }
}
