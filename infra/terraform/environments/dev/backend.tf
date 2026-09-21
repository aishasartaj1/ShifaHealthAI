# Local state for this DEV-only portfolio deployment. If this project ever needs multiple
# contributors or Stage/Prod environments, switch this block to a "gcs" backend pointing at a
# dedicated state bucket (create that bucket outside Terraform first, to avoid the chicken-and-egg
# problem of Terraform managing the bucket it stores its own state in).
terraform {
  backend "local" {
    path = "terraform.tfstate"
  }
}
