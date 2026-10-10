terraform {
  required_version = ">= 1.5"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

provider "aws" {
  region = var.aws_region
}

module "vpc" {
  source  = "terraform-aws-modules/vpc/aws"
  version = "~> 5.0"

  name = "${var.cluster_name}-vpc"
  cidr = "10.0.0.0/16"

  azs             = var.availability_zones
  private_subnets = [for index in range(length(var.availability_zones)) : cidrsubnet("10.0.0.0/16", 8, index + 1)]
  public_subnets  = [for index in range(length(var.availability_zones)) : cidrsubnet("10.0.0.0/16", 8, index + 101)]

  enable_nat_gateway   = true
  single_nat_gateway   = true # cost-conscious default; set false for HA in prod
  enable_dns_hostnames = true

  # Required tags for the EKS/ALB controller to discover subnets
  public_subnet_tags = {
    "kubernetes.io/role/elb" = "1"
  }
  private_subnet_tags = {
    "kubernetes.io/role/internal-elb" = "1"
  }
}

module "eks" {
  source  = "terraform-aws-modules/eks/aws"
  version = "~> 20.0"

  cluster_name    = var.cluster_name
  cluster_version = var.kubernetes_version
  cluster_endpoint_public_access_cidrs = [var.cluster_admin_cidr]
  cluster_addons = {
    coredns    = { most_recent = true }
    kube-proxy = { most_recent = true }
    vpc-cni    = { most_recent = true }
  }

  vpc_id     = module.vpc.vpc_id
  subnet_ids = module.vpc.private_subnets

  cluster_endpoint_public_access = true

  eks_managed_node_groups = {
    default = {
      min_size       = var.node_min_size
      max_size       = var.node_max_size
      desired_size   = var.node_desired_size
      instance_types = [var.node_instance_type]
      capacity_type  = "ON_DEMAND"
    }
  }

  # Cuts environment setup time by removing manual click-ops for cluster,
  # node group, and networking — this is the automation the resume bullet
  # about setup-time reduction refers to.
  tags = {
    Environment = var.environment
    ManagedBy   = "terraform"
    Project     = "microdep"
  }
}
