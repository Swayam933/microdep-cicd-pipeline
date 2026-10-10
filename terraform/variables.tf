variable "aws_region" {
  description = "AWS region to deploy into"
  type        = string
  default     = "us-east-1"
}

variable "availability_zones" {
  description = "At least two availability zones in the selected AWS region"
  type        = list(string)
  default     = ["us-east-1a", "us-east-1b"]

  validation {
    condition     = length(var.availability_zones) >= 2
    error_message = "Provide at least two availability zones for the EKS VPC."
  }
}

variable "cluster_name" {
  description = "EKS cluster name"
  type        = string
  default     = "microdep-cluster"
}

variable "kubernetes_version" {
  description = "EKS Kubernetes version"
  type        = string
  default     = "1.37"
}

variable "cluster_admin_cidr" {
  description = "Public IPv4 CIDR allowed to connect to the EKS Kubernetes API, for example 203.0.113.10/32"
  type        = string

  validation {
    condition     = can(cidrnetmask(var.cluster_admin_cidr))
    error_message = "cluster_admin_cidr must be a valid IPv4 CIDR block."
  }
}

variable "node_instance_type" {
  description = "EC2 instance type for worker nodes"
  type        = string
  default     = "t3.medium"
}

variable "node_min_size" {
  type    = number
  default = 1
}

variable "node_max_size" {
  type    = number
  default = 4

  validation {
    condition     = var.node_max_size >= var.node_min_size
    error_message = "node_max_size must be greater than or equal to node_min_size."
  }
}

variable "node_desired_size" {
  type    = number
  default = 2

  validation {
    condition     = var.node_desired_size >= var.node_min_size && var.node_desired_size <= var.node_max_size
    error_message = "node_desired_size must be between node_min_size and node_max_size."
  }
}

variable "environment" {
  description = "Environment name (dev/staging/prod)"
  type        = string
  default     = "dev"
}
