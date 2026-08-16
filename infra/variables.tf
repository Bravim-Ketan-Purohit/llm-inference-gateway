variable "aws_region" {
  description = "AWS region for benchmark infrastructure"
  type        = string
  default     = "us-east-1"
}

variable "instance_type" {
  description = "EC2 instance type (must have GPU for vLLM)"
  type        = string
  default     = "g5.xlarge"
}

variable "key_name" {
  description = "SSH key pair name"
  type        = string
  default     = "llm-gateway-bench"
}

variable "vllm_model" {
  description = "Model to serve with vLLM"
  type        = string
  default     = "meta-llama/Llama-3.2-1B-Instruct"
}

variable "speculative_model" {
  description = "Draft model for speculative decoding"
  type        = string
  default     = ""
}
