terraform {
  required_version = ">= 1.4"
  backend "s3" {
    region         = "us-east-1"
    bucket         = "wagtailspace02-terraform-state"
    key            = "wagtailspace02.sandbox.json"
    encrypt        = true
    dynamodb_table = "wagtailspace02-terraform-state"
  }
}

module "global_variables" {
  source = "../modules/global_variables"
}
