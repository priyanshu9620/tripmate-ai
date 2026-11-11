variable "region" {
  default = "ap-southeast-2" # the only region the free-plan SCP allows for EC2/ELB
}
variable "profile" {
  default = "shopease" # ~/.aws/credentials profile (same free-plan account as ShopEase)
}
variable "instance_type" {
  default = "t3.micro"
}
variable "image_tag" {
  description = "ECR tag the instance starts with; CI deploys :<sha> afterwards"
  default     = "latest"
}
variable "llm_provider" {
  default = "google_genai"
}
variable "llm_model" {
  default = "gemini-3.5-flash-lite"
}
variable "tools_mode" {
  default = "live" # real Nominatim / Open-Meteo / Overpass on AWS (fixture fallback stays)
}
variable "google_api_key" {
  sensitive = true
  default   = ""
}
variable "langsmith_api_key" {
  sensitive = true
  default   = ""
}
