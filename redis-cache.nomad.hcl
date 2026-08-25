job "redis-cache" {
  datacenters = ["dc1"]
  type        = "service"

  group "cache" {
    count = 1

    network {
      port "redis" {
        to = 6379
      }
    }

    task "redis" {
      driver = "docker"

      config {
        image = "redis:7"
        ports = ["redis"]
      }

      resources {
        cpu    = 300
        memory = 256
      }
    }
  }
}
